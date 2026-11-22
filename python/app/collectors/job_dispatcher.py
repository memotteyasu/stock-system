"""DBの起動要求を1件ずつ安全にPythonワーカーへ渡す常駐ディスパッチャー。"""

import argparse
import logging
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from collectors.bulk_prices import get_connection
from collectors.job_lock import JobLock, JobLockLostError


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", stream=sys.stdout)

DISPATCHER_LOCK_NAME = "stock_job_dispatcher"
POLL_INTERVAL_SECONDS = 10
LOCK_CHECK_INTERVAL_SECONDS = 5
CHILD_INTERRUPT_GRACE_SECONDS = 30
CHILD_TERM_GRACE_SECONDS = 10

shutdown_requested = False


def request_shutdown(_signum, _frame):
    """新しい要求の取得を止め、実行中の子ワーカーを安全に終了させる。"""
    global shutdown_requested
    shutdown_requested = True


def worker_command(run_id, limit=None):
    command = [sys.executable, "-u", "-m", "collectors.daily_update_worker_v2", "--resume", str(run_id)]
    if limit is not None:
        command.extend(["--limit", str(limit)])
    return command


def start_worker(run_id, limit=None):
    """子を別プロセスグループで開始し、停止信号をまとめて送れるようにする。"""
    logging.info("日次更新ワーカーを起動: run_id=%s", run_id)
    return subprocess.Popen(worker_command(run_id, limit), start_new_session=True)


def wait_for_exit(process, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.2)
    return process.poll() is not None


def signal_worker_group(process, signal_number):
    try:
        os.killpg(process.pid, signal_number)
    except ProcessLookupError:
        pass


def stop_worker(process):
    """SIGINTから段階的に子プロセスグループを停止する。強制終了時はTrue。"""
    if process.poll() is not None:
        return False

    logging.info("子ワーカーへSIGINTを送信 pid=%s", process.pid)
    signal_worker_group(process, signal.SIGINT)
    if wait_for_exit(process, CHILD_INTERRUPT_GRACE_SECONDS):
        return False

    logging.warning("子ワーカーが終了しないためSIGTERMを送信 pid=%s", process.pid)
    signal_worker_group(process, signal.SIGTERM)
    if wait_for_exit(process, CHILD_TERM_GRACE_SECONDS):
        return True

    logging.error("子ワーカーをSIGKILLで強制終了 pid=%s", process.pid)
    signal_worker_group(process, signal.SIGKILL)
    process.wait()
    return True


def is_expected_worker_alive(pid, run_id):
    """PID再利用を避けるため、/procの起動引数まで照合する。"""
    if not pid:
        return False
    try:
        command_line = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
    except (FileNotFoundError, PermissionError, ProcessLookupError):
        return False

    arguments = [argument.decode("utf-8", errors="replace") for argument in command_line if argument]
    return "-m" in arguments and "collectors.daily_update_worker_v2" in arguments and "--resume" in arguments and str(run_id) in arguments


def recovery_action(run_status, worker_alive):
    """再起動時のdispatching要求をどう扱うかを一意に決める。"""
    if worker_alive:
        return "keep"
    if run_status == "pending":
        return "retry"
    return "fail"


def recover_interrupted_requests(conn):
    """子の不在を確認してから、停止中要求を復旧または失敗として確定する。"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT q.id, q.stock_job_run_id, q.worker_pid, r.status
                FROM stock_job_launch_requests q
                JOIN stock_job_runs r ON r.id = q.stock_job_run_id
                WHERE q.status = 'dispatching'
                FOR UPDATE SKIP LOCKED
            """)
            requests = cursor.fetchall()
            for request_id, run_id, worker_pid, run_status in requests:
                action = recovery_action(run_status, is_expected_worker_alive(worker_pid, run_id))
                if action == "keep":
                    logging.warning("既存ワーカーを検出したため起動要求を維持: request_id=%s run_id=%s pid=%s", request_id, run_id, worker_pid)
                    continue
                if action == "retry":
                    cursor.execute("""
                        UPDATE stock_job_launch_requests
                        SET status = 'pending', worker_pid = NULL, worker_started_at = NULL,
                            dispatched_at = NULL, error_message = '起動前にディスパッチャーが停止したため再試行します',
                            updated_at = UTC_TIMESTAMP(6)
                        WHERE id = %s
                    """, (request_id,))
                    continue

                cursor.execute("""
                    UPDATE stock_job_launch_requests
                    SET status = 'failed', completed_at = UTC_TIMESTAMP(6), worker_finished_at = UTC_TIMESTAMP(6),
                        error_message = 'ディスパッチャー再起動時に子ワーカーの不在を確認しました',
                        updated_at = UTC_TIMESTAMP(6)
                    WHERE id = %s
                """, (request_id,))
                if run_status == "running":
                    cursor.execute("""
                        UPDATE stock_job_runs
                        SET status = 'stopped', finished_at = UTC_TIMESTAMP(6),
                            error_message = 'ディスパッチャー再起動時にワーカー不在を検出しました', updated_at = UTC_TIMESTAMP(6)
                        WHERE id = %s AND status = 'running'
                    """, (run_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def claim_next_request(conn):
    """未処理要求を行ロックして取得し、同一runの重複要求を失敗として確定する。"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT q.id, q.stock_job_run_id
                FROM stock_job_launch_requests q
                JOIN stock_job_runs r ON r.id = q.stock_job_run_id
                JOIN stock_jobs j ON j.id = r.stock_job_id
                WHERE q.status = 'pending' AND j.job_key = 'daily_update' AND j.enabled = 1
                ORDER BY q.requested_at ASC, q.id ASC
                LIMIT 1 FOR UPDATE SKIP LOCKED
            """)
            request = cursor.fetchone()
            if request is None:
                conn.commit()
                return None

            request_id, run_id = request
            cursor.execute("""
                UPDATE stock_job_launch_requests
                SET status = 'failed', completed_at = UTC_TIMESTAMP(6),
                    error_message = '同一ジョブの重複起動要求として破棄しました', updated_at = UTC_TIMESTAMP(6)
                WHERE stock_job_run_id = %s AND status = 'pending' AND id <> %s
            """, (run_id, request_id))
            cursor.execute("""
                UPDATE stock_job_launch_requests
                SET status = 'dispatching', dispatched_at = UTC_TIMESTAMP(6), updated_at = UTC_TIMESTAMP(6)
                WHERE id = %s
            """, (request_id,))
        conn.commit()
        return request_id, run_id
    except Exception:
        conn.rollback()
        raise


def record_worker_started(conn, request_id, worker_pid):
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_launch_requests
                SET worker_pid = %s, worker_started_at = UTC_TIMESTAMP(6), updated_at = UTC_TIMESTAMP(6)
                WHERE id = %s AND status = 'dispatching'
            """, (worker_pid, request_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def mark_running_run_stopped(conn, run_id, reason):
    with conn.cursor() as cursor:
        cursor.execute("""
            UPDATE stock_job_runs
            SET status = 'stopped', finished_at = UTC_TIMESTAMP(6), error_message = %s, updated_at = UTC_TIMESTAMP(6)
            WHERE id = %s AND status = 'running'
        """, (reason, run_id))


def complete_request(conn, request_id, run_id, return_code, forced_stop=False):
    status = "completed" if return_code == 0 and not forced_stop else "failed"
    error_message = None
    if forced_stop:
        error_message = "ディスパッチャー停止時に子ワーカーを強制終了しました"
    elif return_code != 0:
        error_message = f"ワーカーが終了コード{return_code}で終了しました"
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_launch_requests
                SET status = %s, completed_at = UTC_TIMESTAMP(6), worker_finished_at = UTC_TIMESTAMP(6),
                    error_message = %s, updated_at = UTC_TIMESTAMP(6)
                WHERE id = %s
            """, (status, error_message, request_id))
        if forced_stop or return_code != 0:
            mark_running_run_stopped(conn, run_id, error_message)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def monitor_worker(process, lock):
    """停止要求・ロック喪失を監視しながら子ワーカーの終了を待つ。"""
    while process.poll() is None:
        if shutdown_requested:
            forced_stop = stop_worker(process)
            return process.wait(), forced_stop
        lock.check()
        time.sleep(LOCK_CHECK_INTERVAL_SECONDS)
    return process.returncode, False


def close_connection(conn):
    if conn is not None and conn.open:
        conn.close()


def main(limit=None):
    lock_conn = conn = lock = None
    process = None
    try:
        lock_conn = get_connection()
        lock = JobLock(lock_conn, name=DISPATCHER_LOCK_NAME)
        if not lock.acquire():
            logging.warning("別のディスパッチャーが実行中です")
            return 4

        conn = get_connection()
        recover_interrupted_requests(conn)
        while not shutdown_requested:
            lock.check()
            request = claim_next_request(conn)
            if request is None:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            request_id, run_id = request
            try:
                process = start_worker(run_id, limit)
                record_worker_started(conn, request_id, process.pid)
                return_code, forced_stop = monitor_worker(process, lock)
                complete_request(conn, request_id, run_id, return_code, forced_stop)
            except JobLockLostError:
                if process is not None and process.poll() is None:
                    forced_stop = stop_worker(process)
                    complete_request(conn, request_id, run_id, process.wait(), forced_stop)
                raise
            except Exception:
                logging.exception("ワーカー起動または監視に失敗: run_id=%s", run_id)
                if process is not None and process.poll() is None:
                    stop_worker(process)
                complete_request(conn, request_id, run_id, 1, forced_stop=True)
                raise
            finally:
                process = None
        return 0
    except JobLockLostError as error:
        logging.error("ディスパッチャーロック喪失: %s", error)
        return 4
    except Exception:
        logging.exception("ディスパッチャーが異常終了しました")
        return 3
    finally:
        if lock is not None:
            try:
                if lock_conn is not None and lock_conn.open:
                    lock.release()
            except Exception:
                logging.exception("ディスパッチャーロック解放失敗")
        close_connection(conn)
        close_connection(lock_conn)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="テスト用の銘柄処理上限。本番では指定しない。")
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limitには1以上を指定してください")
    signal.signal(signal.SIGINT, request_shutdown)
    signal.signal(signal.SIGTERM, request_shutdown)
    sys.exit(main(args.limit))

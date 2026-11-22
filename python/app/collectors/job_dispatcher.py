"""DBの起動要求を1件ずつPythonワーカーへ渡す常駐ディスパッチャー。"""

import logging
import signal
import subprocess
import sys
import time

from collectors.bulk_prices import get_connection


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

POLL_INTERVAL_SECONDS = 10
running = True


def stop_dispatcher(_signum, _frame):
    global running
    running = False


def claim_next_request(conn):
    """未処理要求を行ロックして、二重ディスパッチを防ぐ。"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT q.id, q.stock_job_run_id
                FROM stock_job_launch_requests q
                JOIN stock_job_runs r ON r.id = q.stock_job_run_id
                JOIN stock_jobs j ON j.id = r.stock_job_id
                WHERE q.status = 'pending'
                  AND j.job_key = 'daily_update'
                  AND j.enabled = 1
                ORDER BY q.requested_at ASC, q.id ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            """)
            request = cursor.fetchone()

            if request is None:
                conn.commit()
                return None

            request_id, run_id = request
            cursor.execute("""
                UPDATE stock_job_launch_requests
                SET status = 'dispatching',
                    dispatched_at = UTC_TIMESTAMP(6),
                    updated_at = UTC_TIMESTAMP(6)
                WHERE id = %s
            """, (request_id,))

        conn.commit()
        return request_id, run_id
    except Exception:
        conn.rollback()
        raise


def recover_interrupted_requests(conn):
    """前回のディスパッチャー停止時に残った要求を再試行可能に戻す。"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_launch_requests
                SET status = 'pending',
                    dispatched_at = NULL,
                    error_message = 'ディスパッチャー再起動後に再試行します',
                    updated_at = UTC_TIMESTAMP(6)
                WHERE status = 'dispatching'
            """)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def complete_request(conn, request_id, return_code):
    status = 'completed' if return_code == 0 else 'failed'
    error_message = None
    if return_code != 0:
        error_message = f"ワーカーが終了コード{return_code}で終了しました"

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_launch_requests
                SET status = %s,
                    completed_at = UTC_TIMESTAMP(6),
                    error_message = %s,
                    updated_at = UTC_TIMESTAMP(6)
                WHERE id = %s
            """, (status, error_message, request_id))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def run_worker(run_id):
    command = [
        sys.executable,
        "collectors/daily_update_worker_v2.py",
        "--resume",
        str(run_id),
    ]
    logging.info("日次更新ワーカーを起動: run_id=%s", run_id)
    return subprocess.run(command, check=False).returncode


def main():
    signal.signal(signal.SIGINT, stop_dispatcher)
    signal.signal(signal.SIGTERM, stop_dispatcher)

    conn = get_connection()
    try:
        recover_interrupted_requests(conn)
        while running:
            request = claim_next_request(conn)
            if request is None:
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            request_id, run_id = request
            return_code = run_worker(run_id)
            complete_request(conn, request_id, return_code)
    finally:
        conn.close()


if __name__ == "__main__":
    main()

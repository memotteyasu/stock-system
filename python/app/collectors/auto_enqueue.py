"""営業日の日次更新要求を既存のディスパッチャーキューに登録する。"""
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from collectors.bulk_prices import get_connection
from collectors.market_calendar import can_run_daily_update


def enqueue(conn, target_date):
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM stock_jobs WHERE job_key = %s AND enabled = 1 FOR UPDATE", ("daily_update",))
            job = cursor.fetchone()
            if not job:
                raise RuntimeError("日次更新ジョブが未登録または無効です")
            job_id = job[0]
            cursor.execute("SELECT id FROM stock_job_runs WHERE stock_job_id = %s AND target_date = %s LIMIT 1", (job_id, target_date))
            if cursor.fetchone():
                conn.commit()
                return "already_exists"
            cursor.execute("SELECT id FROM stock_job_runs WHERE stock_job_id = %s AND status IN ('pending', 'running') LIMIT 1", (job_id,))
            if cursor.fetchone():
                raise RuntimeError("日次更新ジョブが実行待ちまたは実行中です")
            cursor.execute("""SELECT q.id FROM stock_job_launch_requests q
                JOIN stock_job_runs r ON r.id = q.stock_job_run_id
                WHERE r.stock_job_id = %s AND q.status IN ('pending', 'dispatching') LIMIT 1""", (job_id,))
            if cursor.fetchone():
                raise RuntimeError("日次更新の起動要求が処理待ちです")
            cursor.execute("""INSERT INTO stock_job_runs
                (stock_job_id, target_date, status, success_count, error_count, created_at, updated_at)
                VALUES (%s, %s, 'pending', 0, 0, UTC_TIMESTAMP(6), UTC_TIMESTAMP(6))""", (job_id, target_date))
            run_id = cursor.lastrowid
            cursor.execute("""INSERT INTO stock_job_launch_requests
                (stock_job_run_id, request_type, status, requested_at, created_at, updated_at)
                VALUES (%s, 'start', 'pending', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6), UTC_TIMESTAMP(6))""", (run_id,))
        conn.commit()
        return run_id
    except Exception:
        conn.rollback()
        raise


def main():
    logging.basicConfig(level=logging.INFO)
    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    if not can_run_daily_update(now.date(), now):
        logging.info("休場日または実行時刻前のためスキップ")
        return
    conn = get_connection()
    try:
        logging.info("日次更新要求: %s", enqueue(conn, now.date()))
    finally:
        conn.close()


if __name__ == "__main__":
    main()

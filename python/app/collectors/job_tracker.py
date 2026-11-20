
from datetime import datetime, timezone


class JobTracker:
    def __init__(self, conn, job_key, auto_commit=True):
        self.conn = conn
        self.job_key = job_key
        self.run_id = None
        self.auto_commit = auto_commit
    def start(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM stock_jobs WHERE job_key = %s AND enabled = 1",
                (self.job_key,)
            )
            job = cursor.fetchone()

            if not job:
                raise ValueError(
                    f"ジョブが未登録または無効です: {self.job_key}"
                )

            job_id = job[0]

            cursor.execute("""
                INSERT INTO stock_job_runs
                    (stock_job_id, status, started_at,
                     success_count, error_count,
                     created_at, updated_at)
                VALUES
                    (%s, 'running', UTC_TIMESTAMP(),
                     0, 0, UTC_TIMESTAMP(), UTC_TIMESTAMP())
            """, (job_id,))

            self.run_id = cursor.lastrowid
        if self.auto_commit:
            self.conn.commit()
        return self.run_id

    def record_success(self, stock_code, message):
        self._record("INFO", stock_code, message, True)

    def record_error(self, stock_code, message):
        self._record("ERROR", stock_code, message, False)

    def _record(self, level, stock_code, message, success):
        if self.run_id is None:
            raise RuntimeError("ジョブが開始されていません")

        with self.conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_runs
                SET success_count = success_count + %s,
                    error_count = error_count + %s,
                    last_stock_code = %s,
                    updated_at = UTC_TIMESTAMP()
                WHERE id = %s
            """, (
                1 if success else 0,
                0 if success else 1,
                stock_code,
                self.run_id
            ))

            cursor.execute("""
                INSERT INTO stock_job_logs
                    (stock_job_run_id, level, stock_code,
                     message, created_at)
                VALUES (%s, %s, %s, %s, UTC_TIMESTAMP())
            """, (
                self.run_id, level, stock_code, message
            ))

        if self.auto_commit:
            self.conn.commit()

    def finish(self, status="success", error_message=None):
        if self.run_id is None:
            return

        if status not in ("success", "failed", "stopped"):
            raise ValueError("終了状態が不正です")

        with self.conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_runs
                SET status = %s,
                    finished_at = UTC_TIMESTAMP(),
                    error_message = %s,
                    updated_at = UTC_TIMESTAMP()
                WHERE id = %s
            """, (status, error_message, self.run_id))

        if self.auto_commit:
            self.conn.commit()

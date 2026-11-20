
class JobItemTracker:
    def __init__(self, conn, run_id, auto_commit=True):
        self.conn = conn
        self.run_id = run_id
        self.auto_commit = auto_commit
    def prepare(self):
        """実行対象の有効銘柄を未処理として登録する"""
        with self.conn.cursor() as cursor:
            cursor.execute("""
                INSERT INTO stock_job_items
                    (stock_job_run_id, stock_id, status,
                     attempt_count, created_at, updated_at)
                SELECT %s, s.id, 'pending', 0,
                       UTC_TIMESTAMP(6), UTC_TIMESTAMP(6)
                FROM stocks s
                WHERE s.is_active = 1
                ON DUPLICATE KEY UPDATE
                    stock_id = stock_job_items.stock_id
            """, (self.run_id,))
        if self.auto_commit:
            self.conn.commit()

    def pending_stocks(self, limit=None):
        """未処理・失敗銘柄を取得する"""
        sql = """
            SELECT s.id, s.code
            FROM stock_job_items i
            JOIN stocks s ON s.id = i.stock_id
            WHERE i.stock_job_run_id = %s
                AND (
                    i.status = 'pending'
                    OR (
                        i.status = 'failed'
                        AND i.attempt_count < 3
                    )
                )              
            ORDER BY
                CASE WHEN i.status = 'failed' THEN 0 ELSE 1 END,
                s.code
        """

        params = [self.run_id]

        if limit is not None:
            if limit < 1:
                raise ValueError("limitには1以上を指定してください")
            sql += " LIMIT %s"
            params.append(limit)

        with self.conn.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            return cursor.fetchall()

    def mark_success(self, stock_id):
        with self.conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_items
                SET status = 'success',
                    attempt_count = attempt_count + 1,
                    processed_at = UTC_TIMESTAMP(6),
                    error_message = NULL,
                    updated_at = UTC_TIMESTAMP(6)
                WHERE stock_job_run_id = %s
                  AND stock_id = %s
            """, (self.run_id, stock_id))
        if self.auto_commit:
            self.conn.commit()

    def mark_failed(self, stock_id, message):
        with self.conn.cursor() as cursor:
            cursor.execute("""
                UPDATE stock_job_items
                SET status = 'failed',
                    attempt_count = attempt_count + 1,
                    processed_at = UTC_TIMESTAMP(6),
                    error_message = %s,
                    updated_at = UTC_TIMESTAMP(6)
                WHERE stock_job_run_id = %s
                  AND stock_id = %s
            """, (message[:1000], self.run_id, stock_id))
        if self.auto_commit:
            self.conn.commit()

    def counts(self):
        with self.conn.cursor() as cursor:
            cursor.execute("""
                SELECT status, COUNT(*)
                FROM stock_job_items
                WHERE stock_job_run_id = %s
                GROUP BY status
            """, (self.run_id,))
            return dict(cursor.fetchall())


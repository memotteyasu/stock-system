class JobLockLostError(RuntimeError):
    """ジョブ実行中にMySQLロックを失った"""
    pass

class JobLock:
    def __init__(self, conn, name="stock_daily_update"):
        self.conn = conn
        self.name = name
        self.acquired = False

    def acquire(self):
        with self.conn.cursor() as cursor:
            cursor.execute(
                "SELECT GET_LOCK(%s, 0)",
                (self.name,)
            )
            result = cursor.fetchone()

        self.acquired = bool(result and result[0] == 1)
        return self.acquired

    def release(self):
        if not self.acquired:
            return

        try:
            with self.conn.cursor() as cursor:
                cursor.execute(
                    "SELECT RELEASE_LOCK(%s)",
                    (self.name,)
                )
                result = cursor.fetchone()

            if result and result[0] == 1:
                self.acquired = False
            else:
                raise RuntimeError(
                    "MySQLロックを解放できませんでした"
                )
        except Exception:
            self.acquired = False
            raise


    def check(self):
        """ロック用接続と所有状態を確認する"""
        if not self.acquired:
            raise JobLockLostError(
                "MySQLロックを保持していません"
            )

        try:
            with self.conn.cursor() as cursor:
                cursor.execute("SELECT CONNECTION_ID()")
                connection_id = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT IS_USED_LOCK(%s)",
                    (self.name,)
                )
                owner_id = cursor.fetchone()[0]

        except Exception as error:
            self.acquired = False
            raise JobLockLostError(
                "ロック用MySQL接続が切断されました"
            ) from error

        if owner_id != connection_id:
            self.acquired = False
            raise JobLockLostError(
                "MySQLロックの所有権を失いました"
            )

        return True



from collectors.bulk_prices import get_connection
from collectors.job_lock import JobLock, JobLockLostError

conn = get_connection()

try:
    lock = JobLock(conn)

    if not lock.acquire():
        raise RuntimeError("ロックを取得できませんでした")

    print("ロック取得:", lock.check())

    # ロックを保持したままMySQL接続を切断
    conn.close()
    print("MySQL接続を切断しました")

    try:
        lock.check()
        raise AssertionError("ロック喪失を検知できませんでした")
    except JobLockLostError as error:
        print("ロック喪失を正常に検知:", error)

finally:
    if conn.open:
        conn.close()



from collectors.bulk_prices import get_connection
from collectors.job_lock import JobLock


conn1 = get_connection()
conn2 = get_connection()

try:
    lock1 = JobLock(conn1)
    lock2 = JobLock(conn2)

    print("1回目のロック取得:", lock1.acquire())
    print("2回目のロック取得:", lock2.acquire())

    lock1.release()
    print("1回目のロック解放: 完了")

    print("解放後のロック取得:", lock2.acquire())
    lock2.release()

finally:
    conn1.close()
    conn2.close()


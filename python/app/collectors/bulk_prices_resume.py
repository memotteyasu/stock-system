
import os
import sys
import time
import random
import logging

import pymysql
from bulk_prices import save_stock, get_connection

logging.basicConfig(
    filename="/app/bulk_prices_errors.log",
    level=logging.ERROR,
    format="%(asctime)s %(levelname)s %(message)s"
)

# 6か月分の初期取得が完了したとみなす最低件数
MIN_PRICE_COUNT = 100


def get_pending_stocks(conn):
    sql = """
        SELECT
            s.id,
            s.code,
            COUNT(d.id) AS price_count
        FROM stocks s
        LEFT JOIN daily_prices d
            ON s.id = d.stock_id
        WHERE s.is_active = 1
        GROUP BY s.id, s.code
        HAVING price_count < %s
        ORDER BY s.code
    """

    with conn.cursor() as cursor:
        cursor.execute(sql, (MIN_PRICE_COUNT,))
        return cursor.fetchall()


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 20

    if limit < 1:
        raise ValueError("取得件数は1以上にしてください")

    conn = get_connection()

    try:
        pending = get_pending_stocks(conn)

        print(f"未取得・不足銘柄: {len(pending)}")
        print(f"今回の処理上限: {limit}銘柄")

        success = 0
        failed = 0
        attempted = 0

        for stock_id, code, existing_count in pending:
            if attempted >= limit:
                break

            attempted += 1

            try:
                conn.ping(reconnect=True)

                count = save_stock(conn, stock_id, code)

                if count == 0:
                    failed += 1
                    logging.error("%s: データなし", code)
                    print(f"[{attempted}] {code}: データなし")
                else:
                    success += 1
                    print(
                        f"[{attempted}] {code}: "
                        f"{count}営業日分を保存"
                    )

            except Exception as e:
                conn.rollback()
                failed += 1

                logging.exception("%s: 取得失敗", code)
                print(f"[{attempted}] {code}: エラー {e}")

                # レート制限時は処理を中断
                message = str(e).lower()
                if any(x in message for x in (
                    "429", "rate limit", "too many requests"
                )):
                    print("アクセス制限の可能性があります。処理を停止します。")
                    break

            time.sleep(random.uniform(2.0, 4.0))

        print("\n処理終了")
        print(f"成功: {success}")
        print(f"失敗・データなし: {failed}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()

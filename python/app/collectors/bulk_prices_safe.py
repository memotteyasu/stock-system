
import os
import sys
import time
import random
import logging

import pymysql
import yfinance as yf
from bulk_prices import get_connection, save_stock

# 設定
MIN_PRICE_COUNT = 100
MAX_CONSECUTIVE_FAILURES = 5
MIN_WAIT_SECONDS = 3
MAX_WAIT_SECONDS = 6

LOG_FILE = "/app/bulk_prices_safe.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)


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


def is_rate_limit_error(error):
    message = str(error).lower()

    keywords = [
        "429",
        "too many requests",
        "rate limit",
        "yfratelimiterror"
    ]

    return any(word in message for word in keywords)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100

    if limit < 1:
        raise ValueError("取得件数は1以上を指定してください")

    conn = get_connection()

    success = 0
    failed = 0
    consecutive_failures = 0

    try:
        pending = get_pending_stocks(conn)
        target = pending[:limit]

        print(f"未取得・不足銘柄: {len(pending)}")
        print(f"今回の取得予定: {len(target)}銘柄")

        logging.info(
            "開始: pending=%s target=%s",
            len(pending),
            len(target)
        )

        for index, (stock_id, code, existing_count) in enumerate(
            target, 1
        ):
            try:
                conn.ping(reconnect=True)

                count = save_stock(conn, stock_id, code)

                if count == 0:
                    failed += 1
                    consecutive_failures += 1

                    print(
                        f"[{index}/{len(target)}] "
                        f"{code}: データなし"
                    )
                    logging.warning(
                        "%s: データなし", code
                    )
                else:
                    success += 1
                    consecutive_failures = 0

                    print(
                        f"[{index}/{len(target)}] "
                        f"{code}: {count}件保存"
                    )

                    logging.info(
                        "%s: %s件保存",
                        code,
                        count
                    )

            except Exception as e:
                conn.rollback()
                failed += 1
                consecutive_failures += 1

                print(
                    f"[{index}/{len(target)}] "
                    f"{code}: エラー {e}"
                )

                logging.exception(
                    "%s: 取得エラー", code
                )

                if is_rate_limit_error(e):
                    print("アクセス制限を検知しました。処理を停止します。")
                    logging.error("アクセス制限により停止")
                    break

            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print(
                    f"{MAX_CONSECUTIVE_FAILURES}銘柄連続で失敗したため停止します。"
                )
                logging.error("連続失敗により停止")
                break

            if index < len(target):
                wait = random.uniform(
                    MIN_WAIT_SECONDS,
                    MAX_WAIT_SECONDS
                )
                time.sleep(wait)

        print("\n処理終了")
        print(f"成功: {success}")
        print(f"失敗・データなし: {failed}")

        logging.info(
            "終了: success=%s failed=%s",
            success,
            failed
        )

    except KeyboardInterrupt:
        print("\nユーザー操作により停止しました。")
        logging.warning("ユーザー操作により停止")

    finally:
        conn.close()


if __name__ == "__main__":
    main()

import os
import sys
import time
import random
import logging

from bulk_prices import get_connection, save_stock

BATCH_SIZE = 100
MAX_FAILURES = 5
WAIT_MIN = 3
WAIT_MAX = 6

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

def pending_stocks(conn):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT s.id, s.code
            FROM stocks s
            LEFT JOIN stock_fetch_status f
              ON f.stock_id = s.id
            WHERE s.is_active = 1
              AND f.stock_id IS NULL
            ORDER BY s.code
            LIMIT %s
        """, (BATCH_SIZE,))
        return cursor.fetchall()

def save_status(conn, stock_id, status, count=0, error=None):
    with conn.cursor() as cursor:
        cursor.execute("""
            INSERT INTO stock_fetch_status
                (stock_id, last_attempt_at,
                 last_success_at, status,
                 fetched_rows, error_message)
            VALUES (
                %s, NOW(),
                IF(%s = 'success', NOW(), NULL),
                %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                last_attempt_at = NOW(),
                last_success_at =
                    IF(VALUES(status) = 'success',
                       NOW(), last_success_at),
                status = VALUES(status),
                fetched_rows = VALUES(fetched_rows),
                error_message = VALUES(error_message)
        """, (stock_id, status, status, count, error))
    conn.commit()

def rate_limited(message):
    msg = str(message).lower()
    return any(x in msg for x in (
        "429", "rate limit", "too many requests",
        "yfratelimiterror"
    ))

def main():
    conn = get_connection()
    successes = 0
    failures = 0
    consecutive = 0

    try:
        while True:
            conn.ping(reconnect=True)
            stocks = pending_stocks(conn)

            if not stocks:
                logging.info(
                    "未処理銘柄なし。初回取得処理を終了"
                )
                return 0

            logging.info("バッチ開始: %d銘柄", len(stocks))

            for stock_id, code in stocks:
                try:
                    conn.ping(reconnect=True)
                    count = save_stock(conn, stock_id, code)

                    if count > 0:
                        save_status(
                            conn, stock_id, "success", count
                        )
                        successes += 1
                        consecutive = 0
                        logging.info(
                            "%s: %d件保存", code, count
                        )
                    else:
                        # 空データはアクセス制限の可能性もある
                        # スキップせず、安全停止する
                        logging.error(
                            "%s: 空データ。取得元の状態確認が必要",
                            code
                        )
                        return 2

                except Exception as e:
                    conn.rollback()
                    failures += 1
                    consecutive += 1
                    logging.exception("%s: 取得失敗", code)

                    if rate_limited(e):
                        logging.error(
                            "アクセス制限を検知。停止"
                        )
                        return 2

                    try:
                        save_status(
                            conn, stock_id, "error",
                            error=str(e)[:1000]
                        )
                    except Exception:
                        conn.rollback()
                        logging.exception("状態記録失敗")
                        return 3

                    if consecutive >= MAX_FAILURES:
                        logging.error(
                            "5銘柄連続失敗。停止"
                        )
                        return 3

                time.sleep(random.uniform(
                    WAIT_MIN, WAIT_MAX
                ))

            logging.info(
                "バッチ終了 成功累計=%d 失敗累計=%d",
                successes, failures
            )

            # バッチ間の休止
            time.sleep(60)

    except KeyboardInterrupt:
        logging.warning("手動停止")
        return 130
    except Exception:
        logging.exception("予期しないエラーで停止")
        return 3
    finally:
        conn.close()

if __name__ == "__main__":
    sys.exit(main())

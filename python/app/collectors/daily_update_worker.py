
import argparse
import logging
import random
import sys
import time

from collectors.bulk_prices import get_connection
from collectors.daily_update import update_stock
from collectors.job_tracker import JobTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

MAX_FAILURES = 5


def get_stocks(conn, limit):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT id, code
            FROM stocks
            WHERE is_active = 1
            ORDER BY code
            LIMIT %s
        """, (limit,))
        return cursor.fetchall()


def is_rate_limited(error):
    message = str(error).lower()
    return any(text in message for text in (
        "429", "rate limit",
        "too many requests", "yfratelimiterror"
    ))


def main(limit):
    price_conn = get_connection()
    tracker_conn = get_connection()
    tracker = JobTracker(tracker_conn, "daily_update")

    result = "failed"
    error_message = None
    failures = 0
    consecutive_failures = 0

    try:
        tracker.start()
        logging.info("日次更新開始 run_id=%s", tracker.run_id)

        stocks = get_stocks(price_conn, limit)

        for stock_id, code in stocks:
            try:
                count = update_stock(price_conn, stock_id, code)

            except Exception as error:
                price_conn.rollback()
                failures += 1
                consecutive_failures += 1
                logging.exception("%s: 株価取得失敗", code)

                try:
                    tracker.record_error(code, str(error)[:1000])
                except Exception:
                    tracker_conn.rollback()
                    logging.exception("ジョブ履歴の記録失敗")
                    error_message = "ジョブ履歴の記録失敗"
                    return 3

                if is_rate_limited(error):
                    error_message = "アクセス制限を検知"
                    return 2

                if consecutive_failures >= MAX_FAILURES:
                    error_message = "5銘柄連続失敗"
                    return 3

                continue

            if count == 0:
                error_message = f"{code}: 空データを検知"
                logging.error(error_message)
                try:
                    tracker.record_error(code, error_message)
                except Exception:
                    tracker_conn.rollback()
                    logging.exception("ジョブ履歴の記録失敗")
                return 2

            try:
                tracker.record_success(code, f"{count}行更新対象")
            except Exception:
                tracker_conn.rollback()
                logging.exception("ジョブ履歴の記録失敗")
                error_message = "ジョブ履歴の記録失敗"
                return 3

            consecutive_failures = 0
            logging.info("%s: %d行更新対象", code, count)

            time.sleep(random.uniform(3, 6))

        if failures:
            error_message = f"{failures}銘柄で取得失敗"
            result = "failed"
            return 3

        result = "success"
        logging.info("日次更新テスト完了")
        return 0

    except KeyboardInterrupt:
        result = "stopped"
        error_message = "手動停止"
        return 130

    except Exception as error:
        error_message = str(error)
        logging.exception("日次更新で予期しないエラー")
        return 3

    finally:
        if tracker.run_id is not None:
            try:
                tracker.finish(result, error_message)
            except Exception:
                logging.exception("終了状態の記録失敗")

        tracker_conn.close()
        price_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit", type=int, required=True
    )
    args = parser.parse_args()

    if args.limit < 1:
        parser.error("--limitには1以上を指定してください")

    sys.exit(main(args.limit))


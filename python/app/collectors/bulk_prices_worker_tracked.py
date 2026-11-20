
import sys
import time
import random
import logging

from collectors.bulk_prices import get_connection, save_stock
from collectors.job_tracker import JobTracker

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
                %s, UTC_TIMESTAMP(),
                IF(%s = 'success', UTC_TIMESTAMP(), NULL),
                %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                last_attempt_at = UTC_TIMESTAMP(),
                last_success_at =
                    IF(VALUES(status) = 'success',
                       UTC_TIMESTAMP(), last_success_at),
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

def record_job_result(tracker, success, code, message):
    try:
        if success:
            tracker.record_success(code, message)
        else:
            tracker.record_error(code, message)
        return True
    except Exception:
        logging.exception(
            "%s: ジョブ履歴の記録に失敗", code
        )
        try:
            tracker.conn.rollback()
        except Exception:
            logging.exception("ジョブ履歴接続の復旧失敗")
        return False
        
class StatusSaveError(Exception):
    pass

def main(max_stocks=None):
    conn = get_connection()

    tracker_conn = get_connection()
    tracker = JobTracker(tracker_conn, "initial_fetch")
    successes = 0
    failures = 0
    consecutive = 0
    processed = 0
    result = "failed"
    error_message = None

    try:
        tracker.start()
        logging.info("ジョブ開始 run_id=%s", tracker.run_id)

        while True:
            conn.ping(reconnect=True)
            stocks = pending_stocks(conn)

            if not stocks:
                logging.info("未処理銘柄なし。正常終了")
                result = "success"
                return 0

            logging.info("バッチ開始: %d銘柄", len(stocks))

            for stock_id, code in stocks:
                if max_stocks is not None and processed >= max_stocks:
                    logging.info(
                        "指定件数に到達: %d銘柄", processed
                    )
                    result = "success"
                    return 0

                processed += 1
                try:
                    conn.ping(reconnect=True)
                    count = save_stock(conn, stock_id, code)

                    if count > 0:
                        try:
                            save_status(conn, stock_id, "success", count)
                        except StatusSaveError:
                            logging.exception(
                                "%s: 取得管理情報の保存失敗。安全停止",
                                code
                            )
                            error_message = (
                                f"{code}: 取得管理情報の保存に失敗"
                            )
                            return 3
                        except Exception as e:
                            conn.rollback()
                            raise StatusSaveError(
                                f"{code}: 株価保存後の取得管理情報更新に失敗"
                            ) from e

                        record_job_result(
                            tracker, True, code, f"{count}件保存"
                        )
                        successes += 1
                        consecutive = 0
                        logging.info("%s: %d件保存", code, count)

                    else:
                        error_message = (
                            f"{code}: 空データ。取得元の確認が必要"
                        )
                        record_job_result(
                            tracker, False, code, error_message
                        )
                        logging.error(error_message)
                        return 2

                except Exception as e:
                    conn.rollback()
                    failures += 1
                    consecutive += 1
                    logging.exception("%s: 取得失敗", code)

                    if rate_limited(e):
                        error_message = f"アクセス制限: {e}"
                        record_job_result(
                            tracker, False, code, error_message
                        )
                        return 2

                    save_status(
                        conn, stock_id, "error",
                        error=str(e)[:1000]
                    )
                    record_job_result(
                        tracker, False, code, str(e)[:1000]
                    )

                    if consecutive >= MAX_FAILURES:
                        error_message = "5銘柄連続失敗"
                        logging.error(error_message)
                        return 3

                time.sleep(random.uniform(
                    WAIT_MIN, WAIT_MAX
                ))

            logging.info(
                "バッチ終了 成功=%d 失敗=%d",
                successes, failures
            )
            time.sleep(60)

    except KeyboardInterrupt:
        result = "stopped"
        error_message = "手動停止"
        return 130

    except Exception as e:
        conn.rollback()
        error_message = str(e)
        logging.exception("予期しないエラー")
        return 3

    finally:
        if tracker.run_id is not None:
            try:
                tracker.finish(result, error_message)
            except Exception:
                logging.exception(
                    "ジョブ終了状態の保存に失敗"
                )

        tracker_conn.close()
        conn.close()
        
if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    if limit is not None and limit < 1:
        raise ValueError("取得件数は1以上を指定してください")

    sys.exit(main(limit))
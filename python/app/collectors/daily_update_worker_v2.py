from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo
from collectors.market_calendar import (
    can_run_daily_update,
    previous_tse_business_day,
)

import argparse
import logging
import random
import sys
import time

from collectors.bulk_prices import get_connection
from collectors.daily_update import update_stock
from collectors.job_tracker import JobTracker
from collectors.job_item_tracker import JobItemTracker
from collectors.job_lock import JobLock, JobLockLostError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)

MAX_FAILURES = 5


def is_rate_limited(error):
    message = str(error).lower()
    return any(text in message for text in (
        "429", "rate limit",
        "too many requests", "yfratelimiterror"
    ))


def resume_run(conn, run_id):
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT r.id
            FROM stock_job_runs r
            JOIN stock_jobs j ON j.id = r.stock_job_id
            WHERE r.id = %s
              AND j.job_key = 'daily_update'
              AND j.enabled = 1
              AND r.status IN ('pending', 'failed', 'stopped', 'running')
        """, (run_id,))

        if cursor.fetchone() is None:
            raise ValueError(
                f"再開できない実行IDです: {run_id}"
            )

        cursor.execute("""
            UPDATE stock_job_runs
            SET status = 'running',
                started_at = COALESCE(started_at, UTC_TIMESTAMP(6)),
                finished_at = NULL,
                error_message = NULL,
                updated_at = UTC_TIMESTAMP(6)
            WHERE id = %s
        """, (run_id,))

    conn.commit()


def check_target_date(conn, target_date, resume_id=None):
    """対象日の重複実行と再開時の日付を確認する"""
    with conn.cursor() as cursor:
        if resume_id is not None:
            cursor.execute("""
                SELECT target_date
                FROM stock_job_runs r
                JOIN stock_jobs j ON j.id = r.stock_job_id
                WHERE r.id = %s
                  AND j.job_key = 'daily_update'
            """, (resume_id,))

            row = cursor.fetchone()

            if row is None:
                raise ValueError("指定した実行IDが存在しません")

            if row[0] is None:
                raise ValueError(
                    "対象日未設定の旧ジョブは再開できません"
                )

            if target_date is not None and row[0] != target_date:
                raise ValueError(
                    "再開対象の日付が一致しません"
                )

        else:
            cursor.execute("""
                SELECT r.id, r.status
                FROM stock_job_runs r
                JOIN stock_jobs j ON j.id = r.stock_job_id
                WHERE j.job_key = 'daily_update'
                AND r.target_date = %s
                ORDER BY r.id DESC
                LIMIT 1
            """, (target_date,))
            row = cursor.fetchone()

            if row:
                raise ValueError(
                    f"対象日{target_date}のジョブが既に存在します。"
                    f"実行ID={row[0]} 状態={row[1]}"
                )


def get_run_target_date(conn, run_id):
    """ジョブに登録されている更新対象日を取得"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT target_date
            FROM stock_job_runs
            WHERE id = %s
        """, (run_id,))
        row = cursor.fetchone()

    if row is None or row[0] is None:
        raise ValueError(
            f"更新対象日が取得できません: run_id={run_id}"
        )

    return row[0]


def find_daily_run(conn, target_date):
    """指定日の既存ジョブを検索する"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT r.id, r.status
            FROM stock_job_runs r
            JOIN stock_jobs j
              ON j.id = r.stock_job_id
            WHERE j.job_key = 'daily_update'
              AND r.target_date = %s
            ORDER BY r.id DESC
            LIMIT 1
        """, (target_date,))

        return cursor.fetchone()

def find_oldest_unfinished_run(conn):
    """最も古い未完了の日次更新ジョブを取得する"""
    with conn.cursor() as cursor:
        cursor.execute("""
            SELECT r.id, r.target_date, r.status
            FROM stock_job_runs r
            JOIN stock_jobs j
              ON j.id = r.stock_job_id
            WHERE j.job_key = 'daily_update'
              AND j.enabled = 1
              AND r.target_date IS NOT NULL
              AND r.status IN ('stopped', 'failed', 'running')
              AND EXISTS (
                  SELECT 1
                  FROM stock_job_items i
                  WHERE i.stock_job_run_id = r.id
                    AND (
                        i.status = 'pending'
                        OR (
                            i.status = 'failed'
                            AND i.attempt_count < 3
                        )
                    )
              )
            ORDER BY r.target_date ASC, r.id ASC
            LIMIT 1
        """)

        return cursor.fetchone()

def main(
    limit,
    resume_id=None,
    target_date=None,
    auto_mode=False,
    retry_previous=False,
    retry_oldest=False
):
    lock_conn = None
    conn = None
    tracker = None
    result = "failed"
    error_message = None
    failures = 0
    consecutive_failures = 0

    try:
        lock_conn = get_connection()
        lock = JobLock(lock_conn)

        if not lock.acquire():
            logging.error("別の日次更新ジョブが実行中です")
            return 4

        conn = get_connection()

        tracker = JobTracker(
            conn, "daily_update", auto_commit=False
        )

        # 古い未完了ジョブを優先して再開
        if retry_oldest:
            oldest = find_oldest_unfinished_run(conn)

            if oldest is None:
                logging.info(
                    "未完了の日次更新ジョブはありません"
                )
                return 0

            resume_id, target_date, old_status = oldest

            logging.info(
                "最古の未完了ジョブを再開: "
                "run_id=%s 対象日=%s 状態=%s",
                resume_id,
                target_date,
                old_status
            )

        # 自動実行時は、同じ対象日の既存ジョブを探す
        if (auto_mode or retry_previous) and resume_id is None:
            existing = find_daily_run(conn, target_date)

            if retry_previous and existing is None:
                logging.info(
                    "前営業日%sのジョブがないため再試行をスキップ",
                    target_date
                )
                return 0
            if existing:
                existing_id, existing_status = existing

                if existing_status == "success":
                    logging.info(
                        "対象日%sは更新完了済みです",
                        target_date
                    )
                    return 0

                if existing_status in (
                    "stopped", "failed", "running"
                ):
                    resume_id = existing_id
                    logging.info(
                        "既存ジョブを再開します run_id=%s",
                        resume_id
                    )

        check_target_date(conn, target_date, resume_id)

        if resume_id is None:
            if target_date is None:
                raise ValueError("更新対象日を指定してください")

            tracker.start()

            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE stock_job_runs
                    SET target_date = %s,
                        updated_at = UTC_TIMESTAMP(6)
                    WHERE id = %s
                """, (target_date, tracker.run_id))

            conn.commit()
        else:
            resume_run(conn, resume_id)
            tracker.run_id = resume_id

        run_target_date = get_run_target_date(
            conn, tracker.run_id
        )

        logging.info(
            "更新対象日: %s", run_target_date
        )
        items = JobItemTracker(
            conn, tracker.run_id, auto_commit=False
        )

        items.prepare()
        conn.commit()

        logging.info(
            "日次更新開始 run_id=%s",
            tracker.run_id
        )

        stocks = items.pending_stocks(limit)


        for stock_id, code in stocks:
            # 銘柄の取得を始める前にロックを確認
            if not lock.check():
                raise JobLockLostError(
                    "MySQLロックを失ったため処理を停止します"
                )

            try:
                count = update_stock(
                    conn, stock_id, code,
                    auto_commit=False,
                    target_date=run_target_date
                )
                if count == 0:
                    raise ValueError("株価データが空です")

                items.mark_success(stock_id)
                tracker.record_success(
                    code, f"{count}行更新対象"
                )

                if not lock.check():
                    raise RuntimeError(
                        "MySQLロックを失ったため保存を中止します"
                    )

                conn.commit()
                consecutive_failures = 0
                logging.info(
                    "%s: %d行更新対象", code, count
                )

            except Exception as error:
                if isinstance(error, JobLockLostError):
                    conn.rollback()
                    raise

                if "MySQLロックを失った" in str(error):
                    conn.rollback()
                    raise JobLockLostError(str(error)) from error

                conn.rollback()

                if is_rate_limited(error):
                    result = "stopped"
                    error_message = (
                        f"{code}: アクセス制限を検知したため一時停止"
                    )
                    logging.warning(error_message)
                    return 2

                failures += 1
                consecutive_failures += 1

                logging.exception(
                    "%s: 更新失敗", code
                )

                items.mark_failed(stock_id, str(error))
                tracker.record_error(
                    code, str(error)[:1000]
                )
                conn.commit()

                if (
                    "株価データが空" in str(error)
                    or "有効な株価データがありません" in str(error)
                ):
                    logging.warning(
                        "%s: 株価データを取得できないため、次の銘柄へ進みます",
                        code
                    )

                if consecutive_failures >= MAX_FAILURES:
                    error_message = "5銘柄連続失敗"
                    return 3

            time.sleep(random.uniform(3, 6))

        counts = items.counts()
        logging.info("進捗: %s", counts)

        pending_count = counts.get("pending", 0)
        failed_count = counts.get("failed", 0)

        remaining = pending_count + failed_count

        if pending_count == 0 and failed_count > 0:
            retryable_count = len(items.pending_stocks())

            if retryable_count == 0:
                result = "failed"
                error_message = (
                    f"再試行上限に達した銘柄が"
                    f"{failed_count}件残っています"
                )
                logging.error(error_message)
                return 3

        if remaining:
            result = "stopped"
            error_message = (
                f"テスト上限に到達。残り{remaining}銘柄"
            )
            logging.info(error_message)
            return 0

        result = "success"
        logging.info("全銘柄の日次更新完了")
        return 0

    except JobLockLostError as error:
        result = "stopped"
        error_message = str(error)
        logging.error("ロック喪失により処理停止: %s", error)
        return 4

    except KeyboardInterrupt:
        result = "stopped"
        error_message = "手動停止"
        logging.warning(error_message)
        return 130

    except Exception as error:
        error_message = str(error)
        logging.exception("日次更新でエラー")
        return 3

    finally:
        if conn is not None:
            try:
                conn.rollback()

                if tracker and tracker.run_id:
                    tracker.finish(
                        result, error_message
                    )
                    conn.commit()
            except Exception:
                logging.exception(
                    "ジョブ終了状態の記録失敗"
                )
            finally:
                conn.close()

        if lock_conn is not None:
            try:
                if lock_conn.open:
                    lock.release()
            except Exception:
                logging.exception("ロック解放失敗")
            finally:
                if lock_conn.open:
                    lock_conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="処理する銘柄数の上限（省略時は全銘柄）"
    )
    parser.add_argument(
        "--resume", type=int
    )
    parser.add_argument(
        "--target-date",
        type=date.fromisoformat,
        help="更新対象日（YYYY-MM-DD）"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="自動実行モード（東証営業日・18時以降のみ実行）"
    )
    parser.add_argument(
        "--retry-previous",
        action="store_true",
        help="前営業日の未完了ジョブを再開"
    )
    parser.add_argument(
        "--retry-oldest",
        action="store_true",
        help="最も古い未完了ジョブを再開"
    )
    args = parser.parse_args()

    if args.retry_oldest:
        if (
            args.auto
            or args.retry_previous
            or args.resume is not None
            or args.target_date is not None
        ):
            parser.error(
                "--retry-oldest は他の実行モードや日付指定と併用できません"
            )

    if args.auto and args.retry_previous:
        parser.error(
            "--auto と --retry-previous は同時指定できません"
        )

    if args.retry_previous:
        if args.resume is not None or args.target_date is not None:
            parser.error(
                "--retry-previous では日付や実行IDを指定できません"
            )

        now = datetime.now(ZoneInfo("Asia/Tokyo"))
        args.target_date = previous_tse_business_day(now.date())

        print(f"前営業日の再試行対象: {args.target_date}")    

    if args.limit is not None and args.limit < 1:
        parser.error(
            "--limitには1以上を指定してください"
        )
        
    if args.auto:
        now = datetime.now(ZoneInfo("Asia/Tokyo"))
        auto_date = now.date()

        if not can_run_daily_update(auto_date, now):
            print("東証休場日または18時前のため自動更新をスキップ")
            sys.exit(0)

        if args.resume is not None:
            parser.error("--auto と --resume は同時指定できません")

        args.target_date = auto_date


    sys.exit(
        main(
            args.limit,
            args.resume,
            args.target_date,
            auto_mode=args.auto,
            retry_previous=args.retry_previous,
            retry_oldest=args.retry_oldest        )
    )



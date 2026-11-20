from datetime import date
from unittest.mock import MagicMock, patch

from collectors import daily_update_worker_v2 as worker


def block_db_connection():
    raise AssertionError("実DBへの接続は禁止されています")


def main():
    fake_lock_conn = MagicMock()
    fake_conn = MagicMock()
    fake_lock = MagicMock()
    fake_lock.acquire.return_value = True
    fake_lock.check.return_value = True

    fake_tracker = MagicMock()
    fake_tracker.run_id = 999999

    fake_items = MagicMock()
    fake_items.pending_stocks.return_value = [(1, "1301")]

    with (
        patch.object(
            worker, "get_connection",
            side_effect=[
                fake_lock_conn,
                fake_conn,
            ],
        ),
        patch.object(worker, "JobLock", return_value=fake_lock),
        patch.object(worker, "JobTracker", return_value=fake_tracker),
        patch.object(worker, "JobItemTracker", return_value=fake_items),
        patch.object(worker, "check_target_date"),
        patch.object(worker, "get_run_target_date", return_value=date(2026, 11, 19)),
        patch.object(
            worker,
            "update_stock",
            side_effect=ValueError(
                "1301: 対象日2026-11-19の有効な株価データがありません"
            ),
        ),
        patch.object(worker.time, "sleep"),
    ):
        result = worker.main(
            limit=1,
            resume_id=None,
            target_date=date(2026, 11, 19),
        )

    assert result == 2, f"終了コードが不正: {result}"

    fake_items.mark_failed.assert_called_once_with(
        1,
        "1301: 対象日2026-11-19の有効な株価データがありません"
    )
    fake_items.mark_success.assert_not_called()
    fake_tracker.record_error.assert_called_once_with(
        "1301",
        "1301: 対象日2026-11-19の有効な株価データがありません"
    )
    fake_tracker.finish.assert_called_once()

    print("株価データ不完全時のテスト成功")
    print("銘柄の失敗処理: 呼び出し確認済み")
    print("終了コード:", result)
    print("ジョブ状態:", fake_tracker.finish.call_args.args[0])


if __name__ == "__main__":
    main()
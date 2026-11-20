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

    fake_items.pending_stocks.return_value = []
    fake_items.counts.return_value = {
        "pending": 0,
        "failed": 1,
        "success": 3692,
    }

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
        patch.object(worker, "update_stock", side_effect=Exception("429 Too Many Requests")),
        patch.object(worker.time, "sleep"),
    ):
        result = worker.main(
            limit=1,
            resume_id=None,
            target_date=date(2026, 11, 19),
        )

    assert result == 3, f"終了コードが不正: {result}"
    fake_items.mark_failed.assert_not_called()
    fake_items.mark_success.assert_not_called()
    fake_tracker.record_error.assert_not_called()
    fake_tracker.finish.assert_called_once()
    assert fake_tracker.finish.call_args.args[0] == "failed"

    print("再試行上限テスト成功")
    print("終了コード:", result)
    print("ジョブ状態:", fake_tracker.finish.call_args.args[0])

if __name__ == "__main__":
    main()
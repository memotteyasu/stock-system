from datetime import date
from unittest.mock import MagicMock, patch

from collectors import daily_update_worker_v2 as worker


def main():
    fake_lock_conn = MagicMock()
    fake_conn = MagicMock()

    fake_lock = MagicMock()
    fake_lock.acquire.return_value = True
    fake_lock.check.return_value = True

    fake_tracker = MagicMock()
    fake_tracker.run_id = None

    fake_items = MagicMock()
    fake_items.pending_stocks.return_value = []
    fake_items.counts.return_value = {
        "pending": 3692,
        "failed": 0,
        "success": 1,
    }
    target_date = date(2026, 11, 16)

    with (
        patch.object(
            worker,
            "get_connection",
            side_effect=[fake_lock_conn, fake_conn],
        ),
        patch.object(worker, "JobLock", return_value=fake_lock),
        patch.object(worker, "JobTracker", return_value=fake_tracker),
        patch.object(worker, "JobItemTracker", return_value=fake_items),
        patch.object(
            worker,
            "find_oldest_unfinished_run",
            return_value=(7, target_date, "stopped"),
        ) as find_oldest,
        patch.object(worker, "check_target_date") as check_date,
        patch.object(worker, "resume_run") as resume,
        patch.object(
            worker,
            "get_run_target_date",
            return_value=target_date,
        ),
        patch.object(
            worker,
            "update_stock",
            return_value=1,
        ) as mock_update,
        patch.object(worker.time, "sleep"),
    ):
        result = worker.main(
            limit=1,
            retry_oldest=True,
        )

    assert result == 0, f"終了コードが不正: {result}"

    find_oldest.assert_called_once_with(fake_conn)
    check_date.assert_called_once_with(fake_conn, target_date, 7)
    resume.assert_called_once_with(fake_conn, 7)

    fake_tracker.start.assert_not_called()
    fake_items.mark_success.assert_not_called()
    fake_items.mark_failed.assert_not_called()

    assert fake_tracker.run_id == 7
    fake_tracker.finish.assert_called_once_with(
        "stopped",
        "テスト上限に到達。残り3692銘柄"
    )

    print("古い未完了ジョブの再開テスト成功")
    print("再開ジョブID:", fake_tracker.run_id)
    print("対象日:", target_date)
    print("終了コード:", result)


if __name__ == "__main__":
    main()
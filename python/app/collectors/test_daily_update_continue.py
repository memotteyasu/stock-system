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

    fake_items.pending_stocks.return_value = [
        (3443, "7523"),
        (1, "1301"),
    ]
    fake_items.counts.return_value = {
        "pending": 3691,
        "failed": 1,
        "success": 1,
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

        patch.object(
            worker,
            "update_stock",
            side_effect=[
                ValueError("株価データが空です"),
                1,
            ],
        ) as mock_update,

        patch.object(worker.time, "sleep"),
    ):
        result = worker.main(
            limit=1,
            resume_id=None,
            target_date=date(2026, 11, 19),
        )

    assert result == 0, f"終了コードが不正: {result}"

    assert mock_update.call_count == 2

    fake_items.mark_failed.assert_called_once_with(
        3443, "株価データが空です"
    )

    fake_items.mark_success.assert_called_once_with(1)

    fake_tracker.record_error.assert_called_once_with(
        "7523", "株価データが空です"
    )

    fake_tracker.record_success.assert_called_once_with(
        "1301", "1行更新対象"
    )

    fake_tracker.finish.assert_called_once()
    assert fake_tracker.finish.call_args.args[0] == "stopped"
    
    print("株価取得失敗後の継続テスト成功")
    print("7523: 失敗を記録")
    print("1301: 正常処理")
    print("終了コード:", result)
    print("ジョブ状態:", fake_tracker.finish.call_args.args[0])

if __name__ == "__main__":
    main()
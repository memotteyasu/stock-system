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
        (101, "1301"),
        (102, "1332"),
        (103, "1605"),
        (104, "1801"),
        (105, "1925"),
        (106, "2502"),
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
                ValueError("株価データが空です")
                for _ in range(5)
            ],
        ) as mock_update,

        patch.object(worker.time, "sleep"),
    ):
        result = worker.main(
            limit=1,
            resume_id=None,
            target_date=date(2026, 11, 19),
        )

    # 5銘柄目で停止する
    assert result == 3, f"終了コードが不正: {result}"

    # 6銘柄目は処理しない
    assert mock_update.call_count == 5

    # 5銘柄すべて失敗として記録
    assert fake_items.mark_failed.call_count == 5
    assert fake_items.mark_success.call_count == 0
    assert fake_tracker.record_error.call_count == 5

    # ジョブの最終状態を確認
    fake_tracker.finish.assert_called_once()

    print("5銘柄連続失敗の安全停止テスト成功")
    print("株価取得回数:", mock_update.call_count)
    print("失敗記録数:", fake_items.mark_failed.call_count)
    print("終了コード:", result)
    print("ジョブ状態:", fake_tracker.finish.call_args.args[0])

if __name__ == "__main__":
    main()
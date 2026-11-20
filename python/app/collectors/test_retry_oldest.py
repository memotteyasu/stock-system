from unittest.mock import MagicMock

from collectors.daily_update_worker_v2 import (
    find_oldest_unfinished_run,
)


def main():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value

    # DBが最も古い未完了ジョブを返した状況を再現
    cursor.fetchone.return_value = (
        7, "2026-11-16", "stopped"
    )

    result = find_oldest_unfinished_run(conn)

    assert result == (7, "2026-11-16", "stopped")

    sql = cursor.execute.call_args.args[0]

    assert "ORDER BY r.target_date ASC" in sql
    assert "r.status IN" in sql
    assert "LIMIT 1" in sql
    assert "AND EXISTS" in sql
    assert "i.status = 'pending'" in sql
    assert "i.attempt_count < 3" in sql

    print("古い未完了ジョブ検索テスト成功")
    print("選択されたジョブ:", result)


if __name__ == "__main__":
    main()
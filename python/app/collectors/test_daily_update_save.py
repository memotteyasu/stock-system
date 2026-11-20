from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from collectors import daily_update


def main():
    target = date(2026, 11, 16)

    # Yahoo Financeから返される株価を模擬
    df = pd.DataFrame(
        {
            "Open": [1000.0],
            "High": [1050.0],
            "Low": [990.0],
            "Close": [1030.0],
            "Volume": [120000],
        },
        index=pd.to_datetime(["2026-11-16"])
    )

    fake_conn = MagicMock()
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = df

    with patch.object(
        daily_update.yf,
        "Ticker",
        return_value=fake_ticker
    ):
        result = daily_update.update_stock(
            fake_conn,
            1,
            "1301",
            auto_commit=False,
            target_date=target
        )

    # 取得期間を確認
    fake_ticker.history.assert_called_once_with(
        start="2026-11-09",
        end="2026-11-17",
        auto_adjust=False
    )

    # 保存処理を確認
    cursor = fake_conn.cursor.return_value.__enter__.return_value
    cursor.executemany.assert_called_once()

    sql, rows = cursor.executemany.call_args.args

    assert sql == daily_update.SAVE_SQL
    assert len(rows) == 1

    assert rows[0] == (
        1,
        target,
        1000.0,
        1050.0,
        990.0,
        1030.0,
        120000,
        "yfinance"
    )

    assert result == 1

    # ワーカー側でコミットするため、ここでは実行しない
    fake_conn.commit.assert_not_called()

    print("株価保存モックテスト成功")
    print("銘柄: 1301")
    print("対象日:", target)
    print("保存対象:", result, "件")
    print("自動コミット: なし")


if __name__ == "__main__":
    main()
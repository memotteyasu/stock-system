from datetime import date
from unittest.mock import MagicMock, patch

import pandas as pd

from collectors import daily_update


def main():
    target = date(2026, 11, 16)

    # 対象日ではない11月13日の株価だけを返す
    df = pd.DataFrame(
        {
            "Open": [1000.0],
            "High": [1050.0],
            "Low": [990.0],
            "Close": [1030.0],
            "Volume": [120000],
        },
        index=pd.to_datetime(["2026-11-13"])
    )

    fake_conn = MagicMock()
    fake_ticker = MagicMock()
    fake_ticker.history.return_value = df

    with patch.object(
        daily_update.yf,
        "Ticker",
        return_value=fake_ticker
    ):
        try:
            daily_update.update_stock(
                fake_conn,
                1,
                "1301",
                auto_commit=False,
                target_date=target
            )
        except ValueError as e:
            assert "2026-11-16" in str(e)
        else:
            raise AssertionError(
                "対象日の株価がないのにエラーになりませんでした"
            )

    # 誤った日付の株価を保存していないことを確認
    fake_conn.cursor.assert_not_called()
    fake_conn.commit.assert_not_called()

    print("対象日欠損テスト成功")
    print("銘柄: 1301")
    print("対象日:", target)
    print("取得データ日: 2026-11-13")
    print("保存処理: 実行なし")


if __name__ == "__main__":
    main()
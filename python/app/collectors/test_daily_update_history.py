from datetime import date
from unittest.mock import MagicMock, patch

from collectors import daily_update


def main():
    target = date(2026, 11, 16)

    fake_conn = MagicMock()
    fake_ticker = MagicMock()

    # 株価データが空だった場合を再現
    fake_ticker.history.return_value.empty = True

    with patch.object(
        daily_update.yf,
        "Ticker",
        return_value=fake_ticker
    ) as mock_ticker:

        result = daily_update.update_stock(
            fake_conn,
            1,
            "1301",
            auto_commit=False,
            target_date=target
        )

    mock_ticker.assert_called_once_with("1301.T")

    fake_ticker.history.assert_called_once_with(
        start="2026-11-09",
        end="2026-11-17",
        auto_adjust=False
    )

    assert result == 0

    print("過去日付の株価取得テスト成功")
    print("対象日:", target)
    print("取得開始日: 2026-11-09")
    print("取得終了日: 2026-11-17")


if __name__ == "__main__":
    main()
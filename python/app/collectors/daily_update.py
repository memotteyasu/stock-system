from datetime import datetime, date, timedelta

import pandas as pd
import yfinance as yf

SAVE_SQL = """
    INSERT INTO daily_prices
        (stock_id, trade_date, open_price,
         high_price, low_price, close_price,
         volume, source)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        open_price = VALUES(open_price),
        high_price = VALUES(high_price),
        low_price = VALUES(low_price),
        close_price = VALUES(close_price),
        volume = VALUES(volume),
        source = VALUES(source)
"""



def update_stock(
    conn, stock_id, code,
    auto_commit=True, target_date=None
):
    symbol = f"{code}.T"

    if target_date is not None:
        target = pd.Timestamp(target_date).date()

        # 対象日の前後を含めて取得する
        start_date = target - timedelta(days=7)
        end_date = target + timedelta(days=1)

        df = yf.Ticker(symbol).history(
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            auto_adjust=False
        )
    else:
        df = yf.Ticker(symbol).history(
            period="5d",
            auto_adjust=False
        )

    if df.empty:
        return 0

    rows = []
    target_found = False

    for date, row in df.iterrows():
        trade_date = date.date()

        prices = [
            row["Open"],
            row["High"],
            row["Low"],
            row["Close"]
        ]

        if any(pd.isna(value) for value in prices):
            continue

        if target_date is not None and trade_date == target_date:
            target_found = True

        rows.append((
            stock_id,
            trade_date,
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            int(row["Volume"]),
            "yfinance"
        ))

    if not rows:
        return 0

    # 対象日のデータがない場合は保存しない
    if target_date is not None and not target_found:
        raise ValueError(
            f"{code}: 対象日{target_date}の有効な株価データがありません"
        )
    with conn.cursor() as cursor:
        cursor.executemany(SAVE_SQL, rows)

    if auto_commit:
        conn.commit()

    return len(rows)

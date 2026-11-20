
import os
import sys
import time
import random

import pandas as pd
import pymysql
import yfinance as yf


def get_connection():
    return pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4",
        autocommit=False
    )


def save_stock(conn, stock_id, code):
    symbol = f"{code}.T"

    df = yf.Ticker(symbol).history(
        period="6mo",
        auto_adjust=False
    )

    if df.empty:
        return 0

    sql = """
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

    rows = []

    for date, row in df.iterrows():
        prices = [
            row["Open"], row["High"],
            row["Low"], row["Close"]
        ]

        if any(pd.isna(v) for v in prices):
            continue

        rows.append((
            stock_id,
            date.date(),
            float(row["Open"]),
            float(row["High"]),
            float(row["Low"]),
            float(row["Close"]),
            int(row["Volume"]),
            "yfinance"
        ))

    if not rows:
        return 0

    with conn.cursor() as cursor:
        cursor.executemany(sql, rows)

    conn.commit()
    return len(rows)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    if limit < 1:
        raise ValueError("取得件数は1以上を指定してください")

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute("""
                SELECT id, code
                FROM stocks
                WHERE is_active = 1
                ORDER BY code
                LIMIT %s
            """, (limit,))
            stocks = cursor.fetchall()

        print(f"取得対象: {len(stocks)}銘柄")

        success = 0
        failed = 0

        for index, (stock_id, code) in enumerate(stocks, 1):
            try:
                count = save_stock(conn, stock_id, code)

                if count:
                    success += 1
                    print(
                        f"[{index}/{len(stocks)}] "
                        f"{code}: {count}件保存"
                    )
                else:
                    failed += 1
                    print(
                        f"[{index}/{len(stocks)}] "
                        f"{code}: データなし"
                    )

            except Exception as e:
                conn.rollback()
                failed += 1
                print(
                    f"[{index}/{len(stocks)}] "
                    f"{code}: エラー {e}"
                )

            # Yahoo Financeへのアクセス集中を避ける
            time.sleep(random.uniform(1.5, 3.0))

        print("\n取得完了")
        print(f"成功: {success}銘柄")
        print(f"失敗・データなし: {failed}銘柄")

    finally:
        conn.close()


if __name__ == "__main__":
    main()

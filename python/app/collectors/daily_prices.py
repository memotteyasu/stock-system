
import os
import sys
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
        charset="utf8mb4"
    )


def save_prices(code="7203", period="6mo"):
    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM stocks WHERE code = %s",
                (code,)
            )
            stock = cursor.fetchone()

            if not stock:
                raise ValueError(f"銘柄が未登録です: {code}")

            stock_id = stock[0]

        symbol = f"{code}.T"
        print(f"{symbol} の株価を取得します")

        df = yf.Ticker(symbol).history(
            period=period,
            auto_adjust=False
        )

        if df.empty:
            print("株価データがありません")
            return

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

        with conn.cursor() as cursor:
            cursor.executemany(sql, rows)

        conn.commit()
        print(f"保存成功: {len(rows)}営業日分")

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    code = sys.argv[1] if len(sys.argv) > 1 else "7203"
    save_prices(code)

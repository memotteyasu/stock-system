
import io
import pandas as pd
import requests
from sqlalchemy import create_engine, text
import os

JPX_URL = (
    "https://www.jpx.co.jp/markets/statistics-equities/"
    "misc/tvdivq0000001vg2-att/data_j.xlsx"
)

def main():
    print("東証上場銘柄一覧を取得します")

    response = requests.get(JPX_URL, timeout=60)
    response.raise_for_status()

    df = pd.read_excel(
        io.BytesIO(response.content),
        dtype={"コード": str},
        engine="openpyxl"
    )

    required = ["コード", "銘柄名", "市場・商品区分"]
    if not set(required).issubset(df.columns):
        raise ValueError(
            f"Excelの列構成が変更されています: {list(df.columns)}"
        )

    print(f"取得件数: {len(df)}")

    engine = create_engine(
        "mysql+pymysql://",
        creator=lambda: __import__("pymysql").connect(
            host=os.environ["DB_HOST"],
            port=int(os.getenv("DB_PORT", "3306")),
            user=os.environ["DB_USER"],
            password=os.environ["DB_PASSWORD"],
            database=os.environ["DB_NAME"],
            charset="utf8mb4"
        )
    )

    sql = text("""
        INSERT INTO stocks
            (code, name, market, yahoo_symbol, is_active)
        VALUES
            (:code, :name, :market, :symbol, :active)
        ON DUPLICATE KEY UPDATE
            name = :name,
            market = :market,
            yahoo_symbol = :symbol,
            is_active = :active,
            updated_at = CURRENT_TIMESTAMP
    """)

    records = []

    for _, row in df.iterrows():
        code = str(row["コード"]).strip()
        market = str(row["市場・商品区分"]).strip()

        if not code or code.lower() == "nan":
            continue

        # 普通株を初期監視対象とする
        active = any(
            market.startswith(prefix)
            for prefix in (
                "プライム（内国株式）",
                "スタンダード（内国株式）",
                "グロース（内国株式）"
            )
        )

        records.append({
            "code": code,
            "name": str(row["銘柄名"]).strip(),
            "market": market,
            "symbol": f"{code}.T",
            "active": active
        })


    # 100件ずつMySQLに登録する
    import pymysql

    connection = pymysql.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_NAME"],
        charset="utf8mb4"
    )

    insert_sql = """
        INSERT INTO stocks
            (code, name, market, yahoo_symbol, is_active)
        VALUES
            (%s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            name = VALUES(name),
            market = VALUES(market),
            yahoo_symbol = VALUES(yahoo_symbol),
            is_active = VALUES(is_active),
            updated_at = CURRENT_TIMESTAMP
    """

    try:
        with connection.cursor() as cursor:
            for i in range(0, len(records), 100):
                batch = records[i:i + 100]

                values = [
                    (
                        r["code"],
                        r["name"],
                        r["market"],
                        r["symbol"],
                        r["active"]
                    )
                    for r in batch
                ]

                cursor.executemany(insert_sql, values)

                print(
                    f"登録処理: {min(i + 100, len(records))}"
                    f"/{len(records)}"
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()

    print(f"登録・更新件数: {len(records)}")
    print("銘柄マスタの登録が完了しました")


if __name__ == "__main__":
    main()

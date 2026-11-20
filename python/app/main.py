import yfinance as yf

def main():
    print("株価監視システム起動")

    ticker = yf.Ticker("7203.T")

    df = ticker.history(period="10d")

    if df.empty:
        print("株価データを取得できませんでした")
        return

    print("\nトヨタ自動車の株価")
    print(df[["Open", "High", "Low", "Close", "Volume"]])

    df["change"] = df["Close"].diff()

    df["direction"] = df["change"].apply(
        lambda x: "上昇" if x > 0 else "下落" if x < 0 else "変化なし"
    )

    print("\n騰落判定")
    print(df[["Close", "direction"]])


if __name__ == "__main__":
    main()
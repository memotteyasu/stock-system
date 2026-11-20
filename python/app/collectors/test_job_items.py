
from collectors.bulk_prices import get_connection
from collectors.job_tracker import JobTracker
from collectors.job_item_tracker import JobItemTracker


conn = get_connection()

try:
    tracker = JobTracker(conn, "daily_update")
    tracker.start()

    run_id = tracker.run_id
    print(f"テスト実行ID: {run_id}")

    items = JobItemTracker(conn, run_id)
    items.prepare()

    print("登録直後:", items.counts())

    stocks = items.pending_stocks(3)

    if len(stocks) < 2:
        raise RuntimeError("テスト対象銘柄が不足しています")

    stock_id, code = stocks[0]
    items.mark_success(stock_id)
    print(f"{code}: success")

    stock_id, code = stocks[1]
    items.mark_failed(stock_id, "動作確認用のエラー")
    print(f"{code}: failed")

    print("更新後:", items.counts())

    tracker.finish("success")

finally:
    conn.close()


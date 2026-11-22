
class DashboardController < ApplicationController
  def index
    db = ActiveRecord::Base.connection

    @total_stocks = db.select_value(
      "SELECT COUNT(*) FROM stocks"
    ).to_i

    @active_stocks = db.select_value(
      "SELECT COUNT(*) FROM stocks WHERE is_active = 1"
    ).to_i

    @completed_stocks = db.select_value(
      "SELECT COUNT(*) FROM stock_fetch_status WHERE status = 'success'"
    ).to_i

    @failed_stocks = db.select_value(
      "SELECT COUNT(*) FROM stock_fetch_status WHERE status = 'error'"
    ).to_i

    @pending_stocks = [@active_stocks - @completed_stocks, 0].max

    @total_prices = db.select_value(
      "SELECT COUNT(*) FROM daily_prices"
    ).to_i

    @progress = if @active_stocks.positive?
      (@completed_stocks.to_f / @active_stocks * 100).round(1)
    else
      0
    end

    @recent_fetches = db.select_all(<<~SQL).to_a
      SELECT
        s.code,
        s.name,
        f.status,
        f.fetched_rows,
        f.last_success_at
      FROM stock_fetch_status f
      INNER JOIN stocks s ON s.id = f.stock_id
      ORDER BY
        f.last_success_at DESC,
        f.updated_at DESC
      LIMIT 5
    SQL

    @stock_jobs = StockJob
      .includes(:stock_job_runs)
      .order(:id)    

    @recent_job_runs = StockJobRun
      .includes(:stock_job)
      .order(created_at: :desc)
      .limit(10)

    recent_run_ids = @recent_job_runs.pluck(:id)

    @item_counts_by_run = StockJobItem
      .where(stock_job_run_id: recent_run_ids)
      .group(:stock_job_run_id, :status)
      .count

    @queued_run_ids = StockJobLaunchRequest
      .where(stock_job_run_id: recent_run_ids)
      .where(status: %w[pending dispatching])
      .distinct
      .pluck(:stock_job_run_id)

    @active_daily_run = StockJobRun
      .joins(:stock_job)
      .active
      .find_by(stock_jobs: { job_key: StockJob::DAILY_UPDATE_KEY })
  end
end

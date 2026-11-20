
class StockJobRunsController < ApplicationController
  def show
    @run = StockJobRun.includes(:stock_job).find(params[:id])

    @logs = @run.stock_job_logs
                .order(created_at: :desc)
                .limit(200)
  end
end

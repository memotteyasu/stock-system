
class StockJobRunsController < ApplicationController
  before_action :set_run, only: [:show, :resume]

  def show
    @logs = @run.stock_job_logs
                .order(created_at: :desc)
                .limit(200)
    @item_counts = @run.stock_job_items.group(:status).count
    @failed_items = @run.stock_job_items
                        .failed
                        .includes(:stock)
                        .order(processed_at: :desc)
                        .limit(100)
    @queued_for_launch = @run.queued_for_launch?
  end

  def create_daily_update
    target_date = Date.iso8601(params.require(:target_date))
    run = StockJobRun.enqueue_daily_update!(target_date: target_date)

    redirect_to stock_job_run_path(run), notice: "日次更新を起動待ちにしました。"
  rescue ActionController::ParameterMissing, Date::Error
    redirect_to root_path, alert: "対象日をYYYY-MM-DD形式で指定してください。"
  rescue StockJobRun::DuplicateTargetDate => error
    redirect_to stock_job_run_path(error.run), alert: "対象日のジョブは既に存在します。"
  rescue StockJobRun::QueueConflict => error
    redirect_to stock_job_run_path(error.run), alert: "実行待ちまたは実行中のジョブがあります。"
  rescue ActiveRecord::RecordNotFound
    redirect_to root_path, alert: "日次更新ジョブが未登録または無効です。"
  end

  def resume
    @run.enqueue_resume!

    redirect_to stock_job_run_path(@run), notice: "再開を起動待ちにしました。"
  rescue StockJobRun::QueueConflict => error
    redirect_to stock_job_run_path(error.run), alert: "実行待ちまたは実行中のジョブがあります。"
  rescue ArgumentError => error
    redirect_to stock_job_run_path(@run), alert: error.message
  end

  private

  def set_run
    @run = StockJobRun.includes(:stock_job).find(params[:id])
  end
end

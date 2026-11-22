
class StockJobRun < ApplicationRecord
  belongs_to :stock_job
  has_many :stock_job_logs, dependent: :restrict_with_error
  has_many :stock_job_items, dependent: :restrict_with_error
  has_many :stock_job_launch_requests, dependent: :restrict_with_error

  class QueueConflict < StandardError
    attr_reader :run

    def initialize(run)
      @run = run
      super("実行待ちまたは実行中のジョブがあります: ##{run.id}")
    end
  end

  class DuplicateTargetDate < StandardError
    attr_reader :run

    def initialize(run)
      @run = run
      super("対象日#{run.target_date}のジョブが既にあります: ##{run.id}")
    end
  end

  validates :status, inclusion: {
    in: %w[pending running success failed stopped]
  }

  scope :active, -> { where(status: %w[pending running]) }
  scope :resumable, -> { where(status: %w[failed stopped]) }

  def self.enqueue_daily_update!(target_date:)
    job = StockJob.find_by!(job_key: StockJob::DAILY_UPDATE_KEY, enabled: true)

    job.with_lock do
      existing = job.stock_job_runs.find_by(target_date: target_date)
      raise DuplicateTargetDate, existing if existing

      active_run = job.stock_job_runs.active.order(created_at: :asc).first
      raise QueueConflict, active_run if active_run

      run = job.stock_job_runs.create!(
        status: "pending",
        target_date: target_date
      )
      run.stock_job_launch_requests.create!(
        request_type: "start",
        status: "pending",
        requested_at: Time.current
      )
      run
    end
  rescue ActiveRecord::RecordNotUnique
    existing = StockJobRun.joins(:stock_job).find_by(
      stock_jobs: { job_key: StockJob::DAILY_UPDATE_KEY },
      target_date: target_date
    )
    raise DuplicateTargetDate, existing if existing

    raise
  end

  def enqueue_resume!
    stock_job.with_lock do
      reload
      raise ArgumentError, "このジョブは再開できません" unless status.in?(%w[failed stopped])

      active_run = stock_job.stock_job_runs.active.where.not(id: id).order(created_at: :asc).first
      raise QueueConflict, active_run if active_run

      if stock_job_launch_requests.where(status: %w[pending dispatching]).exists?
        raise ArgumentError, "このジョブは既に起動待ちです"
      end

      stock_job_launch_requests.create!(
        request_type: "resume",
        status: "pending",
        requested_at: Time.current
      )
    end
  end

  def queued_for_launch?
    stock_job_launch_requests.where(status: %w[pending dispatching]).exists?
  end
end


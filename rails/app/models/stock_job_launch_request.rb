class StockJobLaunchRequest < ApplicationRecord
  belongs_to :stock_job_run

  validates :request_type, inclusion: { in: %w[start resume] }
  validates :status, inclusion: { in: %w[pending dispatching completed failed] }

  scope :pending, -> { where(status: "pending") }
  scope :queued, -> { where(status: %w[pending dispatching]) }
end

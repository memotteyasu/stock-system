
class StockJobItem < ApplicationRecord
  belongs_to :stock_job_run
  belongs_to :stock

  scope :failed, -> { where(status: "failed") }

  validates :status,
            inclusion: {
              in: %w[pending success failed]
            }

  validates :stock_id,
            uniqueness: {
              scope: :stock_job_run_id
            }
end


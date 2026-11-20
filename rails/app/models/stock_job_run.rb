
class StockJobRun < ApplicationRecord
  belongs_to :stock_job
  has_many :stock_job_logs, dependent: :restrict_with_error

  validates :status, inclusion: {
    in: %w[pending running success failed stopped]
  }
end


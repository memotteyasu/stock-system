
class StockJobLog < ApplicationRecord
  belongs_to :stock_job_run

  validates :level, inclusion: {
    in: %w[INFO WARNING ERROR]
  }
  validates :message, presence: true
end


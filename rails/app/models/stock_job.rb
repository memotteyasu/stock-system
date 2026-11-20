
class StockJob < ApplicationRecord
  has_many :stock_job_runs, dependent: :restrict_with_error

  validates :name, presence: true
  validates :job_key, presence: true, uniqueness: true
end



class StockJob < ApplicationRecord
  has_many :stock_job_runs, dependent: :restrict_with_error

  DAILY_UPDATE_KEY = "daily_update".freeze

  validates :name, presence: true
  validates :job_key, presence: true, uniqueness: true
end


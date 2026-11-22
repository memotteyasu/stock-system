class Stock < ApplicationRecord
  has_many :stock_job_items, dependent: :restrict_with_error
end

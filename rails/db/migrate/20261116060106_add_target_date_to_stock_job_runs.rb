
class AddTargetDateToStockJobRuns < ActiveRecord::Migration[7.2]
  def change
    add_column :stock_job_runs, :target_date, :date

    add_index :stock_job_runs,
              [:stock_job_id, :target_date],
              name: "index_stock_job_runs_on_job_and_target_date"
  end
end

class CreateStockJobLaunchRequests < ActiveRecord::Migration[7.2]
  def change
    create_table :stock_job_launch_requests do |t|
      t.references :stock_job_run, null: false, foreign_key: true
      t.string :request_type, null: false
      t.string :status, null: false, default: "pending"
      t.datetime :requested_at, null: false
      t.datetime :dispatched_at
      t.datetime :completed_at
      t.text :error_message

      t.timestamps
    end

    add_index :stock_job_launch_requests,
              [:status, :requested_at],
              name: "index_stock_job_launch_requests_on_status_and_requested_at"
    add_index :stock_job_launch_requests,
              [:stock_job_run_id, :status],
              name: "index_stock_job_launch_requests_on_run_and_status"

    # MySQL permits multiple NULL values, so historical runs without target_date
    # remain valid while daily runs become unique per job and target date.
    add_index :stock_job_runs,
              [:stock_job_id, :target_date],
              unique: true,
              name: "index_stock_job_runs_on_unique_job_and_target_date"
  end
end

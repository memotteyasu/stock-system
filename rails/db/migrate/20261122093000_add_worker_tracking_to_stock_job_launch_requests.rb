class AddWorkerTrackingToStockJobLaunchRequests < ActiveRecord::Migration[7.2]
  def change
    add_column :stock_job_launch_requests, :worker_pid, :integer
    add_column :stock_job_launch_requests, :worker_started_at, :datetime
    add_column :stock_job_launch_requests, :worker_finished_at, :datetime
  end
end

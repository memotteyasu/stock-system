
class CreateStockJobLogs < ActiveRecord::Migration[7.2]
  def change
    create_table :stock_job_logs do |t|
      t.references :stock_job_run, null: false,
                   foreign_key: true
      t.string :level, null: false, default: "INFO"
      t.string :stock_code
      t.text :message, null: false

      t.datetime :created_at, null: false
    end

    add_index :stock_job_logs,
              [:stock_job_run_id, :created_at]
    add_index :stock_job_logs, :level
  end
end


class CreateStockJobRuns < ActiveRecord::Migration[7.2]
  def change
    create_table :stock_job_runs do |t|
      t.references :stock_job, null: false,
                   foreign_key: true
      t.string :status, null: false, default: "pending"
      t.datetime :started_at
      t.datetime :finished_at
      t.integer :success_count, null: false, default: 0
      t.integer :error_count, null: false, default: 0
      t.string :last_stock_code
      t.text :error_message

      t.timestamps
    end

    add_index :stock_job_runs,
              [:stock_job_id, :created_at]
    add_index :stock_job_runs, :status
  end
end

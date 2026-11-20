
class CreateStockJobItems < ActiveRecord::Migration[7.2]
  def change
    create_table :stock_job_items do |t|
      t.references :stock_job_run,
                   null: false,
                   foreign_key: true

      t.references :stock,
                   null: false,
                   foreign_key: true

      t.string :status, null: false, default: "pending"
      t.integer :attempt_count, null: false, default: 0
      t.datetime :processed_at
      t.text :error_message

      t.timestamps
    end

    add_index :stock_job_items,
              [:stock_job_run_id, :stock_id],
              unique: true,
              name: "index_stock_job_items_on_run_and_stock"

    add_index :stock_job_items,
              [:stock_job_run_id, :status],
              name: "index_stock_job_items_on_run_and_status"
  end
end

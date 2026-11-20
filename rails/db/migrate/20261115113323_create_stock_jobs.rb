
class CreateStockJobs < ActiveRecord::Migration[7.2]
  def change
    create_table :stock_jobs do |t|
      t.string :name, null: false
      t.string :job_key, null: false
      t.boolean :enabled, null: false, default: true

      t.timestamps
    end

    add_index :stock_jobs, :job_key, unique: true
  end
end

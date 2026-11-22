# This file is auto-generated from the current state of the database. Instead
# of editing this file, please use the migrations feature of Active Record to
# incrementally modify your database, and then regenerate this schema definition.
#
# This file is the source Rails uses to define your schema when running `bin/rails
# db:schema:load`. When creating a new database, `bin/rails db:schema:load` tends to
# be faster and is potentially less error prone than running all of your
# migrations from scratch. Old migrations may fail to apply correctly if those
# migrations use external dependencies or application code.
#
# It's strongly recommended that you check this file into your version control system.

ActiveRecord::Schema[7.2].define(version: 2026_11_22_093000) do
  create_table "daily_prices", charset: "utf8mb4", collation: "utf8mb4_unicode_ci", force: :cascade do |t|
    t.bigint "stock_id", null: false
    t.date "trade_date", null: false
    t.decimal "open_price", precision: 16, scale: 4
    t.decimal "high_price", precision: 16, scale: 4
    t.decimal "low_price", precision: 16, scale: 4
    t.decimal "close_price", precision: 16, scale: 4
    t.bigint "volume", unsigned: true
    t.string "source", limit: 30, default: "yfinance", null: false
    t.datetime "created_at", precision: nil, default: -> { "CURRENT_TIMESTAMP" }
    t.datetime "updated_at", precision: nil, default: -> { "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP" }
    t.index ["stock_id", "trade_date"], name: "uq_stock_date", unique: true
    t.index ["trade_date"], name: "idx_trade_date"
  end

  create_table "stock_fetch_status", primary_key: "stock_id", id: :bigint, default: nil, charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.datetime "last_attempt_at", precision: nil
    t.datetime "last_success_at", precision: nil
    t.string "status", limit: 20, default: "pending", null: false
    t.integer "fetched_rows", default: 0, null: false
    t.text "error_message"
    t.datetime "updated_at", precision: nil, default: -> { "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP" }, null: false
  end

  create_table "stock_job_items", charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.bigint "stock_job_run_id", null: false
    t.bigint "stock_id", null: false
    t.string "status", default: "pending", null: false
    t.integer "attempt_count", default: 0, null: false
    t.datetime "processed_at"
    t.text "error_message"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["stock_id"], name: "index_stock_job_items_on_stock_id"
    t.index ["stock_job_run_id", "status"], name: "index_stock_job_items_on_run_and_status"
    t.index ["stock_job_run_id", "stock_id"], name: "index_stock_job_items_on_run_and_stock", unique: true
    t.index ["stock_job_run_id"], name: "index_stock_job_items_on_stock_job_run_id"
  end

  create_table "stock_job_launch_requests", charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.bigint "stock_job_run_id", null: false
    t.string "request_type", null: false
    t.string "status", default: "pending", null: false
    t.datetime "requested_at", null: false
    t.datetime "dispatched_at"
    t.datetime "completed_at"
    t.text "error_message"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.integer "worker_pid"
    t.datetime "worker_started_at"
    t.datetime "worker_finished_at"
    t.index ["status", "requested_at"], name: "index_stock_job_launch_requests_on_status_and_requested_at"
    t.index ["stock_job_run_id", "status"], name: "index_stock_job_launch_requests_on_run_and_status"
    t.index ["stock_job_run_id"], name: "index_stock_job_launch_requests_on_stock_job_run_id"
  end

  create_table "stock_job_logs", charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.bigint "stock_job_run_id", null: false
    t.string "level", default: "INFO", null: false
    t.string "stock_code"
    t.text "message", null: false
    t.datetime "created_at", null: false
    t.index ["level"], name: "index_stock_job_logs_on_level"
    t.index ["stock_job_run_id", "created_at"], name: "index_stock_job_logs_on_stock_job_run_id_and_created_at"
    t.index ["stock_job_run_id"], name: "index_stock_job_logs_on_stock_job_run_id"
  end

  create_table "stock_job_runs", charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.bigint "stock_job_id", null: false
    t.string "status", default: "pending", null: false
    t.datetime "started_at"
    t.datetime "finished_at"
    t.integer "success_count", default: 0, null: false
    t.integer "error_count", default: 0, null: false
    t.string "last_stock_code"
    t.text "error_message"
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.date "target_date"
    t.index ["status"], name: "index_stock_job_runs_on_status"
    t.index ["stock_job_id", "created_at"], name: "index_stock_job_runs_on_stock_job_id_and_created_at"
    t.index ["stock_job_id", "target_date"], name: "index_stock_job_runs_on_job_and_target_date"
    t.index ["stock_job_id", "target_date"], name: "index_stock_job_runs_on_unique_job_and_target_date", unique: true
    t.index ["stock_job_id"], name: "index_stock_job_runs_on_stock_job_id"
  end

  create_table "stock_jobs", charset: "utf8mb4", collation: "utf8mb4_0900_ai_ci", force: :cascade do |t|
    t.string "name", null: false
    t.string "job_key", null: false
    t.boolean "enabled", default: true, null: false
    t.datetime "created_at", null: false
    t.datetime "updated_at", null: false
    t.index ["job_key"], name: "index_stock_jobs_on_job_key", unique: true
  end

  create_table "stocks", charset: "utf8mb4", collation: "utf8mb4_unicode_ci", force: :cascade do |t|
    t.string "code", limit: 10, null: false
    t.string "name", null: false
    t.string "market", limit: 100
    t.string "yahoo_symbol", limit: 20
    t.boolean "is_active", default: true, null: false
    t.datetime "created_at", precision: nil, default: -> { "CURRENT_TIMESTAMP" }, null: false
    t.datetime "updated_at", precision: nil, default: -> { "CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP" }, null: false
    t.index ["code"], name: "code", unique: true
  end

  add_foreign_key "daily_prices", "stocks", name: "fk_daily_prices_stock"
  add_foreign_key "stock_fetch_status", "stocks", name: "fk_fetch_stock"
  add_foreign_key "stock_job_items", "stock_job_runs"
  add_foreign_key "stock_job_items", "stocks"
  add_foreign_key "stock_job_launch_requests", "stock_job_runs"
  add_foreign_key "stock_job_logs", "stock_job_runs"
  add_foreign_key "stock_job_runs", "stock_jobs"
end

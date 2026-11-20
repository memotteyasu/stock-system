# This file should ensure the existence of records required to run the application in every environment (production,
# development, test). The code here should be idempotent so that it can be executed at any point in every environment.
# The data can then be loaded with the bin/rails db:seed command (or created alongside the database with db:setup).
#
# Example:
#
#   ["Action", "Comedy", "Drama", "Horror"].each do |genre_name|
#     MovieGenre.find_or_create_by!(name: genre_name)
#   end

jobs = [
  { job_key: "initial_fetch", name: "全銘柄の初回取得" },
  { job_key: "daily_update", name: "毎日の株価更新" },
  { job_key: "trend_analysis", name: "株価トレンド分析" },
  { job_key: "volume_analysis", name: "出来高分析" }
]

jobs.each do |job|
  record = StockJob.find_or_initialize_by(job_key: job[:job_key])
  record.name = job[:name]
  record.enabled = true if record.new_record?
  record.save!
end

puts "ジョブ定義を登録しました: #{StockJob.count}件"


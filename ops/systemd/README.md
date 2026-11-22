# VPSジョブディスパッチャー

`stock-job-dispatcher.service` はVPSホスト上だけで動かします。Railsコンテナは
MySQLの `stock_job_launch_requests` へ起動要求を書くだけで、Dockerソケットや
`sudo` 権限を持ちません。

## 導入前の確認

1. 本番Composeの配置先が `/opt/stock-system/docker-compose.yml` であることを確認します。
2. `stockapp` を専用Linuxユーザーとして作成し、Dockerの実行権限だけを与えます。
3. Pythonコンテナが起動済みで、`/app/collectors/job_dispatcher.py` を読めることを確認します。
4. `stock_job_runs` に同じ `stock_job_id` と `target_date` の重複がないことを確認してから、Rails migrationを実行します。

## 有効化

本番VPSで内容を確認してから、root権限を持つ運用者が実行します。

```sh
sudo install -m 0644 ops/systemd/stock-job-dispatcher.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now stock-job-dispatcher.service
sudo systemctl status stock-job-dispatcher.service
```

このサービスは要求を1件ずつ処理します。実ワーカーは従来どおりMySQL named lock
`stock_daily_update` を取得するため、手動要求・再開・将来の自動実行が重なっても
実処理は二重起動しません。

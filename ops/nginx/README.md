# k2t.work の公開設定

`k2t.work` をVPSのNginxからRailsへリバースプロキシします。RailsはDockerの
`127.0.0.1:3000` にだけ公開し、外部から3000番ポートへ直接アクセスさせません。

## VPSへの設定反映

VPSでNginxとCertbotをインストールし、設定を有効にします。

```sh
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
sudo install -m 0644 ops/nginx/k2t.work.conf /etc/nginx/sites-available/k2t.work
sudo ln -s /etc/nginx/sites-available/k2t.work /etc/nginx/sites-enabled/k2t.work
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl enable --now nginx
```

ファイアウォールまたはConoHaのセキュリティグループでTCP 80/443を許可します。

## DNS切替とHTTPS

DNSのAレコードを `k2t.work -> 160.251.178.154` に切り替え、反映を確認してから
証明書を発行します。

```sh
dig +short k2t.work A
sudo certbot --nginx -d k2t.work
```

証明書発行後は、`https://k2t.work` でRailsのBasic認証画面が表示されることを確認します。

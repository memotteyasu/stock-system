# Stock Monitor 管理画面

## 管理画面の認証

管理画面はHTTP Basic認証で保護します。`rails/.env.example` を参考に、
ローカルおよび本番の `rails/.env` に次の値を設定してください。

```dotenv
ADMIN_USERNAME=管理者ユーザー名
ADMIN_PASSWORD=長くランダムなパスワード
```

`rails/.env` はGit管理の対象外です。資格情報が未設定の場合、管理画面への
アクセスは拒否されます。

This README would normally document whatever steps are necessary to get the
application up and running.

Things you may want to cover:

* Ruby version

* System dependencies

* Configuration

* Database creation

* Database initialization

* How to run the test suite

* Services (job queues, cache servers, search engines, etc.)

* Deployment instructions

* ...

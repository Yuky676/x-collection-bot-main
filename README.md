# 概要
<img width="603" height="372" alt="x-api-collection drawio" src="https://github.com/user-attachments/assets/77f14217-f5b0-4465-8fa3-230b35ef908d" />


過去7日間に、特定のキーワードを含むツイートを自動的に収集し、保存・分析・通知を行うBotを作成しました。

主なできることは以下の通りです。

- Airflowで指定したスケジュールで定期的にツイート収集を行い、postgresに保存
- Grafanaが定期的にpostgresのテーブルを確認し、データを可視化する
- 収集したデータを１週間に１回、geminiに分析依頼をかけて、その結果をgmailを使って任意のアドレスに通知する


# コンテナの構成
- postgres
  - image: `postgres:13`
  - ポート: `5432:5432`
  - ボリューム: `postgres-db-volume:/var/lib/postgresql/data`
  - 環境変数: POSTGRES_USER/PASSWORD/DB はすべて `airflow`
  - healthcheck: `pg_isready`

- redis
  - image: `redis:7.2-bookworm`
  - expose: 6379（ホスト公開は設定されていない。Compose 内の他コンテナから参照可能）

- airflow-apiserver
  - image: `${AIRFLOW_IMAGE_NAME:-apache/airflow:3.0.4}`
  - command: `api-server --host 0.0.0.0 --port 8080`
  - ポート: `8080:8080`

- airflow-scheduler
  - image: `${AIRFLOW_IMAGE_NAME:-apache/airflow:3.0.4}`

- airflow-dag-processor
  - image: 同上

- airflow-worker
  - image: 同上

- airflow-triggerer
  - image: 同上


- airflow-init
  - image: 同上
  - entrypoint: `/bin/bash`（コンテナ起動時に初期化処理を実行）
  - 主な処理: ボリュームディレクトリ作成、所有権変更、`airflow config list`、バージョン表示など

- grafana
  - image: `grafana/grafana-enterprise`
  - container_name: `grafana`
  - ポート: `3011:3000`（ホスト:コンテナ）

---

## プロファイル／デフォルトで起動されないサービス
- airflow-cli
  - profiles: `debug`
  - コマンド: `airflow`（CLI 用）
  - デフォルトでは起動されない。

- flower
  - profiles: `flower`
  - command: `celery flower`
  - ポート: `5555:5555`
  - デフォルトでは起動されない。

 ---
 
## 気にする必要のあるコンテナ
- postgres
	- 取得したツイートを保管しておくDB
- airflow-api
	- Airflowの管理画面用コンテナ
- grafana
	- オブザーバビリティ

# 構築手順

## コンテナの起動
1. .envの作成
```
cat > .env << 'EOF'
AIRFLOW_IMAGE_NAME=apache/airflow:3.0.4
AIRFLOW_UID=50000
AIRFLOW_PROJ_DIR=.
_AIRFLOW_WWW_USER_USERNAME=airflow
_AIRFLOW_WWW_USER_PASSWORD=airflow
_PIP_ADDITIONAL_REQUIREMENTS=
EOF
```

2. airflowの初期化
   ```
   docker compose up airflow-init
   ```

3. コンテナの起動
   docker compose up -d


## postgresの設定
`storage`という名前のDBを作り、以下のようなカラムを持つテーブル`tweets`を作成する。

```
   Column   |           Type           | Collation | Nullable | Default 
------------+--------------------------+-----------+----------+---------
 post_id    | character varying(255)   |           | not null | 
 author_id  | character varying(255)   |           | not null | 
 created_at | timestamp with time zone |           | not null | 
 lang       | character varying(10)    |           |          | 
 text       | text                     |           |          | 
 realname   | character varying(255)   |           | not null | 
 username   | character varying(255)   |           | not null | 
Indexes:
    "tweets_pkey" PRIMARY KEY, btree (post_id)
    "tweets_created_at_idx" btree (created_at)
```


## Airflowの設定
Airflow 3.0.4の使用を想定しています。

1. 「Admin」→「Connections」から以下の情報で登録
	- Connection id: storage
 	- Connection Type: postgres
  	- Host: postgres
    - Login: DBのログインユーザ名
    - Password: DBのログインパスワード  
   	- Port: 5432
   	- Database: storage
2. 「Admin」→「Connections」から以下の情報を登録
   - Connection Id: gmail
   - COnnection Type: SMTP
   - Host: smtp.gmail.com
   - Login: 送信元のgoogleアカウント
   - Password：アプリパスワード
   - Port: 587
   - (もし送信元のメアドをwrapしたいなら)From email：送信元にしたいメアド
   - (もし送信元のメアドをwrapしたいなら)Disable SSL: True
3. 「Admin」→「Variables」から以下の情報を登録
   - X API v2のエンドポイント: {"Key": "x_api_search", "Value": "https://api.x.com/2/tweets/search/recent"}
   - X API v2のtoken: {"Key": "x_api_bearer", "Value": X Developer Portalから払い下げてもらったtoken}
   - 分析結果の送信先：{"Key": "to_addr", "Value": "user@example.com"}
   - gemini用token: {"Key": "gemini_API_token", "Value": AI Studioから払い下げられたtoken}
	


## Grafanaの設定
1. 「Connections」→「Data source」→「Add data source」からpostgresを選択して、DBを接続する
2. 自分の分析したいデータに合うようにダッシュボードを作る

色々工夫してたり、デバッグ用のVariableがあったりするが、その辺はコードを見てね。

最低限、これくらいの設定をしていれば、動かせるよ。

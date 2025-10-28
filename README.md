# このプロジェクトについて
このプロジェクトでは、直近７日間で、キーワードを含む投稿されたツイートを収集し、蓄積・分析を自動で実行するBotの構築を行いました。

環境は全てコンテナで構築してあるため、初期化時はコンテナのビルドを行ってください。


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

# 構築	

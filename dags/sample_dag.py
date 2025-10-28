from airflow.decorators import dag, task
from airflow.operators.bash import BashOperator
import pendulum
import socket

@dag(
    schedule=None,                         # 手動実行向け（登録後すぐ実行したいときに便利）
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Tokyo"),
    catchup=False,
    tags=["check", "sample"],
)
def sample_basic():
    hello = BashOperator(
        task_id="echo_hello",
        bash_command='echo "Hello from $(hostname)"'
    )

    @task
    def say_hi(name: str = "Airflow"):
        now = pendulum.now("Asia/Tokyo").to_datetime_string()
        host = socket.gethostname()
        print(f"Hi {name}! host={host}, now={now}")

    hello >> say_hi()

dag = sample_basic()

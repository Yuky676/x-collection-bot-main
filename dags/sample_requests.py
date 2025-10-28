from email.mime.text import MIMEText
import pendulum
import requests
import smtplib, ssl
from airflow.sdk import dag, task, Variable
from airflow.operators.email import EmailOperator

@dag(
    schedule=None,
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Tokyo"),
    catchup=False,
    tags=["check", "requests"],
)

def send_test_mail():
    EmailOperator(
        task_id="send_mail",
        to="murakami@webclass.jp",
        subject="Test mail",
        html_content="<html><body>Test mail</body></html>",
        conn_id="gmail",
    )

send_test_mail()

import pendulum
import logging
import requests
from airflow.decorators import dag, task
from airflow.models.variable import Variable
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator

def getToken():
    now = pendulum.now("Asia/Tokyo")
    month_start = now.start_of("month")

    week_number = ((now.day + month_start.isoweekday() - 1) // 7) + 1

    if week_number == 2:
        token = Variable.get("WCB-1")
    if week_number == 3:
        token = Variable.get("WCB-2")
    if week_number == 4:
        token = Variable.get("WCB-3")
    if week_number == 5:
        token = Variable.get("x_api_bearer")
    else:
        token = Variable.get("x_api_bearer2")

    return token


@dag(
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Tokyo"),
    schedule="0 2 * * 0,3",
    catchup=False,
    tags=["X API"],
)
def collect_tweets_bot():
    @task
    def get_dummy():
        payload = Variable.get("dummy_json", deserialize_json=True)
        return payload


    @task
    def get_tweets(retries=0):
        api_url = Variable.get("x_api_search")
        token = getToken()

        headers = {"Authorization": f"Bearer {token}"}

        args = {
            "query": "(keyword OR キーワード) lang:ja",
            "max_results": 40,
            "tweet.fields": "lang,created_at,author_id",
            "expansions": "author_id",
            "user.fields": "id,name,username"
        }

        response = requests.get(api_url, headers=headers, params=args)
        if response.status_code == 429:
            reset_unix = response.headers.get("x-rate-limit-reset")
            if reset_unix:
                try:
                    reset_ts = int(float(reset_unix))
                    reset_jst = pendulum.from_timestamp(reset_ts, tz="UTC").in_timezone("Asia/Tokyo")
                    logging.warning(
                        "X API rate limited (429). Resets at %s (Asia/Tokyo)",
                        reset_jst.to_datetime_string(),
                    )
                except Exception:
                    logging.warning("Rate limit header present but unparsable: %r", reset_unix)
            else:
                logging.warning("X API rate limited (429) but no x-rate-limit-reset header.")
            response.raise_for_status()

        response.raise_for_status()
        payload = response.json()

        return payload


    @task
    def processing_json(fetch_data):
        tweets = fetch_data["data"]
        usersInfo = fetch_data["includes"]["users"]

        users_map = {user['id']: user for user in usersInfo}
        rows = []

        for tweet in tweets:
            userInfo = users_map.get(tweet["author_id"])

            rows.append({
                "post_id": tweet["id"],
                "author_id": tweet["author_id"],
                'realname': userInfo.get("name"),
                'username': userInfo.get("username"),
                "created_at": tweet["created_at"],
                "lang": tweet["lang"],
                "text": tweet["text"],
            })

        return rows

    rows = processing_json(fetch_data=get_tweets())
    # rows = processing_json(fetch_data=get_dummy())

    SQLExecuteQueryOperator.partial(
        task_id="insert_tweets",
        conn_id="storage",
        sql="""
        INSERT INTO public.tweets
            (post_id, author_id, realname, username, created_at, lang, text)
        VALUES
            (%(post_id)s, %(author_id)s, %(realname)s, %(username)s, %(created_at)s::timestamptz, %(lang)s, %(text)s)
        ON CONFLICT (post_id) DO NOTHING;
        """
    ).expand(parameters=rows)


collect_tweets_bot()

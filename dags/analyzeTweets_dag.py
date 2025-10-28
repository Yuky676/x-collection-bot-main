import json
import pendulum
from google import genai
import requests
from airflow.sdk import dag, task, Variable
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from airflow.operators.email import EmailOperator
from datetime import datetime

TWEETS_TABLE_STRUCT = ['id', 'author_id', 'created_at', 'lang', 'text']

@dag(
    start_date=pendulum.datetime(2024, 1, 1, tz="Asia/Tokyo"),
    schedule="0 9 * * 1",
    catchup=False,
    tags=["X API"],
)


def analyze_tweets():
    fetch_data = SQLExecuteQueryOperator(
        task_id="get_tweets",
        conn_id="storage",
        sql="""
            SELECT * FROM public.tweets
            WHERE created_at >= now() - interval '7 days'
            AND created_at < now();
        """
    )

    @task
    def processing_fetch_ata(tweets: list):
        tweets_with_columns = []
        for row in tweets:
            tweet_dict = dict(zip(TWEETS_TABLE_STRUCT, row))

            # 'created_at' キーが存在し、その値がdatetimeオブジェクトであれば文字列に変換
            if 'created_at' in tweet_dict and isinstance(tweet_dict['created_at'], datetime):
                tweet_dict['created_at'] = tweet_dict['created_at'].isoformat()

            tweets_with_columns.append(tweet_dict)

        return tweets_with_columns


    @task
    def ask_gemini(tweets: list):
        api_key = Variable.get("gemini_API_token")
        # tweets_json_string = json.dumps(tweets, ensure_ascii=False, indent=2)

        prompt = f"""
            # 命令
            あなたは、テキストデータを分析する専門AIです。
            以下の ##ツイートデータ(JSON形式) を分析し、指定された ##抽出基準 に基づいて、アプリの開発に役立つ情報だけを、##出力形式 に従って新しいJSONオブジェクトを生成してください。
            
            ## ツイートデータ
            {tweets}
            
            ## 抽出基準
            ツイート本文に、以下のいずれかの内容が含まれているものを抽出対象とします。
            - バグ、エラー、クラッシュ、フリーズに関する具体的な報告
            - 新機能の提案、改善要望
            
            ## 出力形式
            抽出したツイートを以下の構造を持つJSON配列として出力してください。
            - `text`: ツイート原文
            - `reason`: 抽出した理由と、どう開発の役に立ちそうかのあなたの考え
            抽出したツイートがない場合は，textに「該当するツイート0件」，reasonに「抽出基準に該当するツイートが見つかりませんでした」と入れたオブジェクトを1件だけ持つJSON配列を返してください。
            - 
        """

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        try:
            return response.text
        except ValueError:
            # response.text へのアクセスで ValueError が発生した場合、
            # それはレスポンスがブロックされたことを意味する
            print("警告: APIからのレスポンスがセーフティ機能によりブロックされました。")

            # なぜブロックされたかの理由をログに出力する
            # このログを見れば、原因がわかります
            print(f"Block Reason: {response.prompt_feedback}")

            # 次のタスクがエラーにならないよう、空のJSON配列を返す
            return "[]"
        except Exception as e:
            print(f"予期せぬ例外が発生しました: {e}")
            return "[]"


    @task
    def make_mail_body(contents):
        html_parts=["<h1>今週投稿された開発の役に立ちそうなツイート</h1>"]

        for i, tweet_obj in enumerate(json.loads(contents, strict=False), 1):
            # 元のテキストの改行をHTMLの<br>タグに変換
            text_content = tweet_obj["text"].replace('\n', '<br>')
            reason = tweet_obj["reason"].replace('\n', '<br>')

            # 各ツイートをdivタグで囲み、スタイルを適用
            html_parts.append(f"""
            <div style="border: 1px solid #cccccc; border-radius: 8px; padding: 15px; margin-bottom: 20px; font-family: sans-serif;">
                <h3 style="margin-top: 0;">ツイート {i}</h3>
                <p>{text_content}</p>
                <h3 style="margin-top: 0;">抽出された理由</h3>
                <p>{reason}</p>
            </div>
            """)

        # HTML全体を一つの文字列に結合
        intro = "※先週投稿されたツイートの中から、geminiが開発に有用だと判断した投稿を抽出しています。\n"
        html_body = intro + "".join(html_parts)

        return html_body


    data = processing_fetch_ata(fetch_data.output)
    html_body = make_mail_body(ask_gemini(data))


    EmailOperator(
        task_id="sending_email",
        to=Variable.get("to_addr"),
        html_content=html_body,
        subject="今週のツイート解析",
        conn_id="gmail",
    )



analyze_tweets()
import yfinance as yf
from forex_python.converter import CurrencyRates
import requests
from datetime import datetime
import openai
import os
from dotenv import load_dotenv
import yagmail
import pandas as pd
import matplotlib.pyplot as plt
import io
import schedule
import time

# =============================
# 環境変数
# =============================
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
EMAIL = os.getenv("EMAIL_ADDRESS")
APP_PASS = os.getenv("EMAIL_APP_PASSWORD")

# =============================
# 株価データ取得
# =============================
def get_stock_data():
    symbols = {"日経平均": "^N225", "ダウ平均": "^DJI", "NASDAQ": "^IXIC"}
    data = {}
    for name, symbol in symbols.items():
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2d")
        if len(hist) < 2:
            continue
        today = hist.iloc[-1]
        yesterday = hist.iloc[-2]
        data[name] = {
            "終値": round(today["Close"],2),
            "最高値": round(today["High"],2),
            "最安値": round(today["Low"],2),
            "前日比": round(today["Close"]-yesterday["Close"],2)
        }
    return data

# =============================
# 為替データ取得
# =============================
def get_forex_data():
    c = CurrencyRates()
    pairs = {"USD/JPY":("USD","JPY"), "EUR/JPY":("EUR","JPY"), "AUD/JPY":("AUD","JPY")}
    data = {}
    for name,(base,quote) in pairs.items():
        rate = c.get_rate(base,quote)
        data[name]={"現在値":round(rate,3)}
    return data

# =============================
# ニュース取得
# =============================
def get_news():
    url = f"https://newsapi.org/v2/top-headlines?category=business&language=jp&apiKey={NEWS_API_KEY}"
    r = requests.get(url)
    articles = r.json().get("articles", [])
    headlines = [a["title"] for a in articles[:5] if a.get("title")]
    return headlines

# =============================
# グラフ生成（株価・為替）
# =============================
def create_chart(stock_data, forex_data):
    fig, axes = plt.subplots(1,2, figsize=(10,4))

    # 株価棒グラフ
    df_stock = pd.DataFrame(stock_data).T
    df_stock["終値"].plot(kind="bar", ax=axes[0], color="skyblue")
    axes[0].set_title("主要株価 終値")
    axes[0].set_ylabel("価格")

    # 為替棒グラフ
    df_forex = pd.DataFrame(forex_data).T
    df_forex["現在値"].plot(kind="bar", ax=axes[1], color="salmon")
    axes[1].set_title("為替レート")
    axes[1].set_ylabel("JPY")

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png")
    buf.seek(0)
    plt.close()
    return buf

# =============================
# GPTで記事生成
# =============================
def generate_article(stock_data, forex_data, news_list):
    date = datetime.now().strftime("%Y年%m月%d日")
    prompt = f"""
    あなたは経済ジャーナリストです。
    以下のデータをもとにMarkdown形式で記事を作成してください。
    株価データ、為替データ、ニュースをわかりやすく整理。
    最後に「総括コメント」と「今日の相場キーワード」を付けてください。

    株価データ:
    {stock_data}

    為替データ:
    {forex_data}

    ニュース見出し:
    {news_list}
    """
    response = openai.ChatCompletion.create(
        model="gpt-4o-mini",
        messages=[
            {"role":"system","content":"あなたは経済ジャーナリストです。"},
            {"role":"user","content":prompt}
        ]
    )
    return response.choices[0].message.content

# =============================
# メール送信
# =============================
def send_email(subject, body, chart_buf):
    yag = yagmail.SMTP(EMAIL, APP_PASS)
    yag.send(
        to=EMAIL,
        subject=subject,
        contents=[body, chart_buf]
    )
    print("📧 メール送信完了")

# =============================
# メイン処理
# =============================
def job():
    print("🕖 データ取得中...")
    stock_data = get_stock_data()
    forex_data = get_forex_data()
    news_list = get_news()
    print("✅ データ取得完了")

    print("🧠 記事生成中...")
    article = generate_article(stock_data, forex_data, news_list)

    print("📊 グラフ作成中...")
    chart_buf = create_chart(stock_data, forex_data)

    subject = f"{datetime.now().strftime('%Y/%m/%d')}の経済日報"
    send_email(subject, article, chart_buf)
    print("🎉 本日の記事送信完了")

# =============================
# スケジュール設定
# =============================
schedule.every().day.at("07:00").do(job)

print("⏱ 自動経済日報bot起動中…")
while True:
    schedule.run_pending()
    time.sleep(60)

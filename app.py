import os
import requests
import threading
from flask import Flask, request
import yt_dlp
from dotenv import load_dotenv

# 🔐 env
load_dotenv()

app = Flask(__name__)

# 🔑 TOKEN
SLACK_BOT_TOKEN = os.getenv("SLACK_TOKEN")

if not SLACK_BOT_TOKEN:
    raise ValueError("❌ SLACK_TOKEN not found in .env file")

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return "Bot is alive 🚀"


# 📥 Скачування
def download_video(url):
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'format': 'mp4'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# 📤 Простий upload (працює стабільно)
def upload_to_slack(file_path, channel):
    with open(file_path, "rb") as f:
        requests.post(
            "https://slack.com/api/files.upload",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
            },
            files={"file": f},
            data={"channels": channel}
        )


# 🔥 Фоновий процес
def process_video(url, channel):
    try:
        # повідомлення "качаю"
        requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "channel": channel,
                "text": "⏳ Downloading video..."
            }
        )

        filepath = download_video(url)

        upload_to_slack(filepath, channel)

    except Exception as e:
        print("❌ ERROR:", e)


# ⚡ Slack events (ГОЛОВНЕ)
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json

    # verification
    if data.get("type") == "url_verification":
        return data.get("challenge"), 200

    if "event" in data:
        event = data["event"]

        # ігноримо самого бота
        if event.get("bot_id"):
            return "OK", 200

        text = event.get("text")
        channel = event.get("channel")

        print("MESSAGE:", text)

        # якщо є лінк
        if text and "http" in text:
            threading.Thread(
                target=process_video,
                args=(text, channel)
            ).start()

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
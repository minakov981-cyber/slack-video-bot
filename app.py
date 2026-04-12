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

# ⬇️ ОЦЕ ДОДАЄШ ТУТ
@app.route("/download", methods=["POST"])
def slack_download():
    print("🔥 /download HIT")
    print("FORM DATA:", request.form)

    url = request.form.get("text")
    channel = request.form.get("channel_id") or request.form.get("channel")

    if not url:
        return {
            "response_type": "ephemeral",
            "text": "❌ No URL provided"
        }, 200

    threading.Thread(
        target=process_video,
        args=(url, channel)
    ).start()

    return {
        "response_type": "ephemeral",
        "text": "⏳ Processing your video..."
    }, 200


# 📥 Скачування
def download_video(url):

    # 👇 ДОДАЙ ОЦЕ СЮДИ
    print("FILES IN ROOT:", os.listdir("."))
    print("COOKIES EXISTS:", os.path.exists("cookies.txt"))

    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'format': 'mp4',
        'cookiefile': 'cookies.txt',
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

# 📤 Простий upload (працює стабільно)
def upload_to_slack(filepath, channel_id):
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    # STEP 1
    res = requests.post(
        "https://slack.com/api/files.getUploadURLExternal",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}"
        },
        data={
            "filename": filename,
            "length": filesize
        }
    )

    data_res = res.json()
    print("STEP 1:", data_res)

    if not data_res.get("ok"):
        print("❌ ERROR STEP 1:", data_res)
        return

    upload_url = data_res["upload_url"]
    file_id = data_res["file_id"]

    # STEP 2
    with open(filepath, "rb") as f:
        requests.post(upload_url, files={"file": f})

    # STEP 3
    res2 = requests.post(
        "https://slack.com/api/files.completeUploadExternal",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "files": [
                {
                    "id": file_id,
                    "title": filename
                }
            ],
            "channel_id": channel_id
        }
    )

    print("STEP 3:", res2.json())

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
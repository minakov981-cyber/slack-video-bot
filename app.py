import os
import requests
import threading
from flask import Flask, request
import yt_dlp
from dotenv import load_dotenv

# 🔐 Завантажуємо змінні середовища
load_dotenv()

app = Flask(__name__)

# 🔑 Беремо токен з .env
SLACK_BOT_TOKEN = os.getenv("SLACK_TOKEN")

if not SLACK_BOT_TOKEN:
    raise ValueError("❌ SLACK_TOKEN not found in .env file")

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


# 📥 Скачування відео
def download_video(url):
    ydl_opts = {
        'outtmpl': f'{DOWNLOAD_FOLDER}/%(title)s.%(ext)s',
        'format': 'mp4'
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# 📤 Завантаження у Slack
def upload_to_slack(filepath, channel_id):
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    # STEP 1: отримати upload URL
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
        print("❌ Slack error STEP1:", data_res)
        return

    upload_url = data_res["upload_url"]
    file_id = data_res["file_id"]

    # STEP 2: upload файл
    with open(filepath, "rb") as f:
        requests.post(upload_url, files={"file": f})

    # STEP 3: завершити upload
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
def process_video(url, channel_id):
    try:
        # повідомлення в Slack
        requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={
                "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
                "Content-Type": "application/json"
            },
            json={
                "channel": channel_id,
                "text": "⏳ Downloading video..."
            }
        )

        filepath = download_video(url)

        upload_to_slack(filepath, channel_id)

    except Exception as e:
        print("❌ ERROR:", e)


# ⚡ Slack endpoint
@app.route("/download", methods=["POST"])
def slack_download():
    url = request.form.get("text")
    channel_id = request.form.get("channel_id")

    if not url:
        return "No URL provided", 200

    # запускаємо у фоні
    threading.Thread(target=process_video, args=(url, channel_id)).start()

    return "Processing...", 200


# ▶ запуск
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
python
import os
import requests
import threading
from flask import Flask, request
import yt_dlp
from dotenv import load_dotenv

# 🔐 Load ENV
load_dotenv()

app = Flask(__name__)

# 🔑 Slack Token
SLACK_BOT_TOKEN = os.getenv("SLACK_TOKEN")

if not SLACK_BOT_TOKEN:
    raise ValueError("❌ SLACK_TOKEN not found in .env file")

# 📁 Downloads folder
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)


@app.route("/")
def home():
    return "Bot is alive 🚀"


# 🔽 Slash command
@app.route("/download", methods=["POST"])
def slack_download():
    print("🔥 /download HIT")
    print("FORM DATA:", request.form)

    url = request.form.get("text")
    user_id = request.form.get("user_id")

    if not url:
        return {
            "response_type": "ephemeral",
            "text": "❌ No URL provided"
        }, 200

    threading.Thread(
        target=process_video,
        args=(url, user_id)
    ).start()

    return {
        "response_type": "ephemeral",
        "text": "⏳ Processing..."
    }, 200


# 📥 Download video
def download_video(url):
    ydl_opts = {
        "outtmpl": f"{DOWNLOAD_FOLDER}/%(title)s.%(ext)s",
        "format": "mp4",
        "cookiefile": "cookies.txt",
        "http_headers": {
            "User-Agent": "Mozilla/5.0"
        }
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


# 📤 Upload to Slack
def upload_to_slack(filepath, user_id, original_url):
    filename = os.path.basename(filepath)
    filesize = os.path.getsize(filepath)

    # STEP 1 — get upload URL
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

    # STEP 2 — upload binary
    with open(filepath, "rb") as f:
        upload_res = requests.post(upload_url, files={"file": f})

    print("STEP 2 STATUS:", upload_res.status_code)

    # STEP 3 — open DM
    dm_res = requests.post(
        "https://slack.com/api/conversations.open",
        headers={
            "Authorization": f"Bearer {SLACK_BOT_TOKEN}",
            "Content-Type": "application/json"
        },
        json={
            "users": user_id
        }
    )

    dm_data = dm_res.json()
    print("DM OPEN:", dm_data)

    if not dm_data.get("ok"):
        print("❌ ERROR OPEN DM:", dm_data)
        return

    real_channel = dm_data["channel"]["id"]

    # STEP 4 — finalize upload
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
            "channel_id": real_channel,
            "initial_comment": f"🔗 Original video:\n{original_url}"
        }
    )

    print("STEP 4:", res2.json())


# 🔥 Main logic
def process_video(url, user_id):
    try:
        filepath = download_video(url)

        upload_to_slack(filepath, user_id, url)

    except Exception as e:
        print("❌ ERROR:", e)


# ⚡ Slack Events
@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json

    # Slack verification
    if data.get("type") == "url_verification":
        return data.get("challenge"), 200

    if "event" in data:
        event = data["event"]

        # Ignore bot messages
        if event.get("bot_id"):
            return "OK", 200

        text = event.get("text")
        user_id = event.get("user")

        print("MESSAGE:", text)

        # If message contains URL
        if text and "http" in text:
            threading.Thread(
                target=process_video,
                args=(text, user_id)
            ).start()

    return "OK", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    app.run(host="0.0.0.0", port=port)
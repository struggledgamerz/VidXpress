import logging
import requests
from PIL import Image
import io
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(level=logging.INFO)

TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"


# Replacement for imghdr → PIL based image type detection
def detect_image_type(file_bytes):
    try:
        img = Image.open(io.BytesIO(file_bytes))
        return img.format.lower()
    except:
        return None


def start(update, context):
    update.message.reply_text("Send any Instagram / FB / Reels link to download!")


def download(update, context):
    import re
    url = update.message.text.strip()

    INSTAGRAM_REGEX = r"(https?://)?(www\.)?(instagram\.com|www\.instagram\.com)/(reel|p|reels)/[A-Za-z0-9_\-]+/?"

    if not re.match(INSTAGRAM_REGEX, url):
        update.message.reply_text("❌ Invalid Instagram link. Please send a valid reel/post URL.")
        return

    update.message.reply_text("⏳ Downloading... Please wait 🔄")

    try:
        api_url = "https://igram.world/api/instagram"
        payload = {"url": url}

        r = requests.post(api_url, json=payload).json()

        # Validate API response
        if "result" not in r or "media" not in r["result"]:
            update.message.reply_text("❌ API error. Link invalid or private.")
            return

        video_url = r["result"]["media"][0]["url"]

        update.message.reply_video(video_url)

    except Exception as e:
        update.message.reply_text("❌ Failed to download. The link may be private or unsupported.")
        print("Error:", e)


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
        

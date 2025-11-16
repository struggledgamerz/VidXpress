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
        return img.format.lower()  # jpeg / png / webp
    except:
        return None


def start(update, context):
    update.message.reply_text("Send any Instagram / FB / Reels link to download!")


def download(update, context):
    url = update.message.text.strip()

    update.message.reply_text("Downloading... Please wait 🔄")

    try:
        # Public IG downloader API
        api_url = f"https://api.sssgram.com/instagram?url={url}"
        r = requests.get(api_url).json()

        video_url = r["links"][0]["link"]

    except Exception as e:
        update.message.reply_text("❌ Failed to download (invalid link or API error).")
        return

    try:
        update.message.reply_video(video=video_url)
    except:
        update.message.reply_text("❌ Telegram does not support this media format.")


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
    

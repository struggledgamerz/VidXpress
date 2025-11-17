import logging
import requests
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)

TOKEN = "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY"

def start(update, context):
    update.message.reply_text("📥 Send any link (Instagram, YouTube, TikTok, Facebook, etc.)")

def download_instagram(url):
    try:
        r = requests.get(f"https://api.geniuslink.workers.dev/instagram?url={url}").json()
        return r.get("url")
    except:
        return None

def download_youtube(url):
    try:
        r = requests.get(f"https://api.geniuslink.workers.dev/youtube?url={url}").json()
        return r.get("url")
    except:
        return None

def download_tiktok(url):
    try:
        r = requests.get(f"https://api.geniuslink.workers.dev/tiktok?url={url}").json()
        return r.get("url")
    except:
        return None

def download_facebook(url):
    try:
        r = requests.get(f"https://api.geniuslink.workers.dev/facebook?url={url}").json()
        return r.get("url")
    except:
        return None

def download_twitter(url):
    try:
        r = requests.get(f"https://api.geniuslink.workers.dev/twitter?url={url}").json()
        return r.get("url")
    except:
        return None


def resolve_media(url):
    hostname = (urlparse(url).hostname or "").lower()

    if "instagram" in hostname:
        return download_instagram(url)

    if "youtube" in hostname or "youtu.be" in hostname:
        return download_youtube(url)

    if "tiktok" in hostname:
        return download_tiktok(url)

    if "facebook" in hostname:
        return download_facebook(url)

    if "twitter" in hostname or "x.com" in hostname:
        return download_twitter(url)

    return None


def download(update, context):
    url = update.message.text.strip()
    update.message.reply_text("⏳ Processing... Please wait 🔄")

    media_url = resolve_media(url)

    if not media_url:
        update.message.reply_text("❌ Invalid or unsupported link!")
        return

    try:
        update.message.reply_video(media_url)
    except:
        update.message.reply_text("❌ Failed to send the video. Try another link.")


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
    

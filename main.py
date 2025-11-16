import logging
import requests
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(level=logging.INFO)

TOKEN = "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY"


def start(update, context):
    update.message.reply_text(
        "🔥 Multi Downloader Active!\nSend any link (IG, FB, TikTok, X, Shorts, Moj, Josh...)"
    )


def download(update, context):
    url = update.message.text.strip()

    update.message.reply_text("⏳ Processing your link...")

    try:
        # UNIVERSAL SUPER API
        api = "https://api.savee.io/api/download"
        r = requests.get(api, params={"url": url}).json()

        # If API failed
        if "medias" not in r or len(r["medias"]) == 0:
            update.message.reply_text("❌ Unable to download. Try another link.")
            return

        media = r["medias"][0]

        video_url = media.get("url")
        if not video_url:
            update.message.reply_text("❌ Failed to get video URL.")
            return

        # Send media
        if media["type"] == "video":
            update.message.reply_video(video_url)
        else:
            update.message.reply_photo(video_url)

    except Exception as e:
        print("ERROR:", e)
        update.message.reply_text("❌ Download failed. Maybe link is private.")


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
    

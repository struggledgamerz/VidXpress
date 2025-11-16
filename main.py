import logging
import requests
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(level=logging.INFO)

TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"

def start(update, context):
    update.message.reply_text("Send any link to download!")

def download(update, context):
    url = update.message.text

    update.message.reply_text("Downloading... wait 🔄")

    try:
        api_url = f"https://api.sssgram.com/instagram?url={url}"
        r = requests.get(api_url).json()
        video = r["links"][0]["link"]
    except:
        update.message.reply_text("❌ Error: Could not download.")
        return

    update.message.reply_video(video=video)

def main():
    updater = Updater(TOKEN, use_context=True)

    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
    

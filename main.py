import logging
import requests
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(level=logging.INFO)

TOKEN = "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY"

def start(update, context):
    update.message.reply_text("Send any reel / short / video link to download!")

def download(update, context):
    url = update.message.text.strip()

    update.message.reply_text("⏳ Processing... Please wait.")

    try:
        api_url = "https://savein.io/api/download"
        data = {"url": url}

        res = requests.post(api_url, json=data)
        result = res.json()

        if "medias" not in result:
            update.message.reply_text("❌ Could not fetch. Maybe link is private or unsupported.")
            return

        media_url = result["medias"][0]["url"]

        # If video
        if result["medias"][0]["type"] == "video":
            update.message.reply_video(media_url)
        else:
            update.message.reply_photo(media_url)

    except Exception as e:
        update.message.reply_text("❌ Failed to download. Try another link.")
        print(e)

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
    

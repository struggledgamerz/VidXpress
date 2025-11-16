import logging
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"

# Simple downloader using public API
def download_video(url):
    try:
        api = f"https://api.sssgram.com/instagram?url={url}"
        r = requests.get(api).json()
        return r["links"][0]["link"]
    except:
        return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send any valid video link (YT, IG, FB, Reels) to download!")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text

    await update.message.reply_text("Downloading... Please wait 🔄")

    link = download_video(url)

    if not link:
        await update.message.reply_text("❌ Failed to download. Invalid link or API error.")
        return

    await update.message.reply_video(video=link)

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.run_polling()

if __name__ == "__main__":
    main()
    

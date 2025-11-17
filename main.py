import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

from download_manager import download_media

TOKEN = "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY"

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send any video link — Instagram, YouTube, TikTok, Facebook, X, Threads, Moj, Chingari etc.")


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()

    await update.message.reply_text("⏳ Downloading… Please wait.")

    file_path, temp = download_media(url)

    if not file_path:
        await update.message.reply_text("❌ Download failed. Link may be private or unsupported.")
        return

    # Send file
    try:
        await update.message.reply_video(video=open(file_path, "rb"))
    except:
        await update.message.reply_document(document=open(file_path, "rb"))

    await update.message.reply_text("✔ Download complete!")


def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

    app.run_polling()


if __name__ == "__main__":
    main()
    

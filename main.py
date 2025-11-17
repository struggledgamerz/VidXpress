import logging
import subprocess
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
from telegram import ChatAction

TOKEN = "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY"

logging.basicConfig(level=logging.INFO)

COOKIES_PATH = "cookies/instagram.txt"  # optional


def start(update, context):
    update.message.reply_text("Send me any link — YouTube, TikTok, Instagram, FB, Twitter…\n\nDownloading using YT-DLP 🔥")


def download(update, context):
    url = update.message.text.strip()

    update.message.reply_chat_action(ChatAction.TYPING)
    update.message.reply_text("Downloading… Please wait 🔄")

    try:
        output_dir = "downloads"
        os.makedirs(output_dir, exist_ok=True)

        output_path = os.path.join(output_dir, "%(title)s.%(ext)s")

        cmd = ["yt-dlp", "-o", output_path, url]

        # Add Instagram cookies if file exists
        if "instagram.com" in url.lower() and os.path.exists(COOKIES_PATH):
            cmd += ["--cookies", COOKIES_PATH]

        logging.info(f"Running command: {' '.join(cmd)}")

        subprocess.run(cmd, check=True)

        # Find downloaded file
        files = os.listdir(output_dir)
        files = sorted([os.path.join(output_dir, f) for f in files], key=os.path.getmtime)

        if not files:
            update.message.reply_text("❌ Failed to download file.")
            return

        latest_file = files[-1]

        # Send file
        with open(latest_file, "rb") as f:
            if latest_file.endswith((".mp4", ".mov", ".webm")):
                update.message.reply_video(f)
            else:
                update.message.reply_document(f)

        os.remove(latest_file)

    except Exception as e:
        logging.error(e)
        update.message.reply_text("❌ Failed. This platform may not be supported.")


def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
    

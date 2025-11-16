import os
import re
import tempfile
import asyncio
from yt_dlp import YoutubeDL
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters

TOKEN = os.getenv("BOT_TOKEN")

URL_RE = re.compile(r"(https?://[^\s]+)")


YDL_OPTS = {
    "format": "bestvideo+bestaudio/best",
    "merge_output_format": "mp4",
    "noplaylist": True,
    "quiet": True
}


async def download_video(url, folder):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: _download(url, folder))


def _download(url, folder):
    with YoutubeDL({**YDL_OPTS, "outtmpl": f"{folder}/%(id)s.%(ext)s"}) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send any Instagram / YouTube / TikTok / Facebook / Twitter link!")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    urls = URL_RE.findall(message)

    if not urls:
        await update.message.reply_text("Please send a valid video link.")
        return

    url = urls[0]
    processing_msg = await update.message.reply_text("Downloading...")

    with tempfile.TemporaryDirectory() as tmp:
        try:
            filepath = await download_video(url, tmp)
        except Exception as e:
            await processing_msg.edit_text(f"Error: {e}")
            return

        size = os.path.getsize(filepath)
        if size > 48 * 1024 * 1024:
            await processing_msg.edit_text("File too large for Telegram (limit ~50MB).")
            return

        await processing_msg.edit_text("Uploading...")

        try:
            await update.message.reply_document(
                InputFile(filepath, filename=os.path.basename(filepath))
            )
        except Exception as e:
            await processing_msg.edit_text(f"Upload error: {e}")
        else:
            await processing_msg.delete()


async def error_handler(update, context):
    print("Error:", context.error)


def main():
    if not TOKEN:
        print("ERROR: TG_BOT_TOKEN not set!")
        return

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_error_handler(error_handler)

    print("Bot running…")
    app.run_polling()


if __name__ == "__main__":
    main()
    

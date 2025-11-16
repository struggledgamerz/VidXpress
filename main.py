# video_saver_bot.py
import os
import re
import asyncio
import tempfile
from pathlib import Path
from yt_dlp import YoutubeDL
from telegram import Update, InputFile
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CommandHandler, filters

TOKEN = os.getenv("BOT_TOKEN")  # set this in env; never hardcode

# Basic link regex (covers many platforms)
URL_RE = re.compile(r"(https?://[^\s]+)")

# YTDLP options
YTDL_OPTS = {
    "format": "bestvideo+bestaudio/best",
    "outtmpl": "%(id)s.%(ext)s",
    "noplaylist": True,
    "merge_output_format": "mp4",
    "quiet": True,
    "no_warnings": True,
    # "logger": ...,  # could add a logger
}

# Helper: run yt-dlp in executor (blocking)
async def yt_download(url: str, dest_folder: str, filename_prefix: str = "") -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _blocking_yt_download, url, dest_folder, filename_prefix)

def _blocking_yt_download(url: str, dest_folder: str, filename_prefix: str):
    os.makedirs(dest_folder, exist_ok=True)
    opts = dict(YTDL_OPTS)
    opts["outtmpl"] = os.path.join(dest_folder, filename_prefix + "%(id)s.%(ext)s")
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        # after download, find filename from info
        filename = ydl.prepare_filename(info)
        # if merge_output_format used, extension might be .mp4
        if not os.path.exists(filename):
            # try mp4
            base = os.path.splitext(filename)[0]
            alt = base + ".mp4"
            if os.path.exists(alt):
                filename = alt
        return {"info": info, "path": filename}

# Command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! Send me a video link (YouTube/Instagram/TikTok/Twitter/etc.) and I'll download it and send back.\n"
        "Commands:\n/help - this help\n/format - choose mp4/mp3 options (soon)\n"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bas link bhejo. Agar file bahut badi hui to bot bata dega.")

# Main message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text = (msg.text or "") + " " + " ".join([a.url for a in (msg.entities or []) if getattr(a, 'url', None)])
    urls = URL_RE.findall(text)
    if not urls and msg.reply_to_message and msg.reply_to_message.text:
        urls = URL_RE.findall(msg.reply_to_message.text)

    if not urls:
        await msg.reply_text("Koi valid link nahi mila. Please YouTube/Instagram/TikTok ka link bhejo.")
        return

    url = urls[0]
    sent = await msg.reply_text("Download start kar raha hoon... thoda time lagega depending on video size.")
    # temp dir
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = await yt_download(url, dest_folder=tmpdir, filename_prefix="")
        except Exception as e:
            await sent.edit_text(f"Download failed: {e}")
            return

        info = result.get("info", {})
        path = result.get("path")
        if not path or not os.path.exists(path):
            await sent.edit_text("Download complete par file nahi mili — shayad format unsupported.")
            return

        file_size = os.path.getsize(path)
        # Telegram bots may have file size limits; we don't assume exact value — check reasonable threshold (e.g., 50MB)
        MAX_DIRECT_SEND = 50 * 1024 * 1024  # 50 MB threshold (adjust if you know your bot's limit)
        if file_size > MAX_DIRECT_SEND:
            # File too big to send directly
            await sent.edit_text(
                f"Downloaded but file is large ({file_size/1024/1024:.1f} MB). I can't upload so large files directly.\n"
                "Options:\n"
                "1) I can trim or lower quality (not implemented automatically).\n"
                "2) You can download from my temporary link (needs external hosting).\n"
                "Reply with 'LINK' to get a temporary download link (if you have integrated storage)."
            )
            return

        # Send file
        try:
            caption = f"{info.get('title','video')}\nSource: {url}"
            async with open(path, "rb") as f:
                await context.bot.send_document(chat_id=msg.chat_id, document=InputFile(f, filename=Path(path).name), caption=caption)
            await sent.delete()
        except Exception as e:
            await sent.edit_text(f"Failed to send file: {e}")

# Basic error handler
async def err_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    print("Error:", context.error)
    # Optional: inform user
    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text("Kuch error aaya. Try again later.")
        except Exception:
            pass

def main():
    if not TOKEN:
        print("ERROR: Set TG_BOT_TOKEN environment variable.")
        return
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(MessageHandler(filters.TEXT | filters.Entity("url") | filters.Document.ALL, handle_message))
    app.add_error_handler(err_handler)
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
  

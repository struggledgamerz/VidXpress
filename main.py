# CRITICAL FIX: Gevent monkey-patching MUST happen before any
# I/O libraries (like httpx, which PTB uses) are imported).
# This prevents the "RuntimeError: Event loop is closed" error
# and ensures gevent workers can handle async tasks.
from gevent import monkey
monkey.patch_all()

import logging
import os
import sys
import asyncio
import yt_dlp
import tempfile
import shutil

from flask import Flask, request
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# --- Configuration & Setup ---

# Set up logging for better visibility
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
# Suppress noisy library logs (optional but helpful)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO) 

# Read token and webhook URL from environment variables
# NOTE: Make sure these environment variables are correctly set in your deployment configuration.
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
WEBHOOK_URL = os.environ.get("WEBHOOK_BASE_URL", "https://your-app-name.onrender.com")

# Initialize the bot Application globally
application = (
    Application.builder()
    .token(TOKEN)
    .concurrent_updates(True) # Use concurrent updates for better performance in a web environment
    .build()
)

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message on /start."""
    if update.message:
        await update.message.reply_text(
            "Hello! Send me a link to download content\\. I'll try to extract the **audio** \\(up to ~50MB\\) and send it back\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Downloads audio from a link using yt-dlp and uploads it to Telegram."""
    if not update.message:
        return

    user_message = update.message
    chat_id = user_message.chat_id
    link = user_message.text
    
    download_message = await user_message.reply_text("⏳ Processing link and starting download... Please wait.")

    # Create a temporary directory for the download
    temp_dir = tempfile.mkdtemp()
    
    try:
        logging.info(f"Received link for download: {link} in temp dir: {temp_dir}")

        # yt-dlp options for downloading best audio format, max size 50MB
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'max_filesize': 50 * 1024 * 1024, # Limit to 50MB for Telegram direct upload
            'restrictfilenames': True,
            'noplaylist': True,
            'verbose': False,
            'logger': logging.getLogger('yt_dlp'),
        }

        # 1. Download the file using yt-dlp
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=True)
            
            # Find the path to the downloaded MP3 file
            mp3_files = [f for f in os.listdir(temp_dir) if f.endswith('.mp3')]
            if mp3_files:
                downloaded_file_path = os.path.join(temp_dir, mp3_files[0])
            else:
                # If no MP3 found, something failed in post-processing
                raise FileNotFoundError("yt-dlp completed, but the expected MP3 file was not found in the temporary directory.")


        # 2. Upload the file to Telegram
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=download_message.message_id,
            text=f"Uploading audio: *{info_dict.get('title', 'Unknown Title')}*",
            parse_mode=ParseMode.MARKDOWN
        )

        with open(downloaded_file_path, 'rb') as audio_file:
            await context.bot.send_audio(
                chat_id=chat_id,
                audio=audio_file,
                title=info_dict.get('title', 'Downloaded Audio'),
                performer=info_dict.get('uploader', 'Unknown'),
                caption=f"Downloaded via the Bot\\. [Original Link]({link})",
                parse_mode=ParseMode.MARKDOWN_V2
            )
            
        await context.bot.delete_message(chat_id=chat_id, message_id=download_message.message_id)
        
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "size limit" in error_msg:
             reply_text = "❌ Download Failed\\. The file size exceeds the 50MB limit\\. I can only download smaller audio tracks\\."
        elif "Unsupported URL" in error_msg:
            reply_text = "❌ Download Failed\\. The link provided is not supported by the downloader\\."
        else:
            # Mask detailed internal error, provide a generic message
            reply_text = "❌ Download Failed\\. An error occurred during the extraction process\\."
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=download_message.message_id,
            text=reply_text,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        logging.error(f"yt-dlp Download Error: {e}", exc_info=True)

    except Exception as e:
        logging.error(f"Error in downloader for chat {chat_id}: {e}", exc_info=True)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=download_message.message_id,
            text="❌ An internal error occurred during the download process\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

    finally:
        # 3. CRITICAL: Clean up the temporary download folder
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"Cleaned up temporary directory: {temp_dir}")


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logging.error("Exception while handling an update:", exc_info=context.error)
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🤖 Sorry, I ran into an error! Please try again later\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logging.error(f"Failed to send error message: {e}")


# --- Application Configuration ---

application.add_handler(CommandHandler("start", start))
# Handle all incoming text messages that look like a URL but are NOT commands
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://\S+') & (~filters.COMMAND), downloader))
application.add_error_handler(error_handler)


# --- Webhook and Server Setup ---

# Create the Flask application instance
app_flask = Flask(__name__)

async def _set_webhook_async():
    """Internal async function to set the webhook."""
    webhook_path = f"/{TOKEN}"
    full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path
    
    logging.info(f"DEBUG: Using BOT TOKEN (first 10 chars): {TOKEN[:10]}...")
    logging.info(f"DEBUG: Calculated Webhook URL: {full_webhook_url}")
    
    async with application:
        await application.bot.set_webhook(url=full_webhook_url)
        logging.info(f"Webhook successfully set to: {full_webhook_url}")

def run_setup():
    """Sets the webhook on the Telegram side using asyncio.run()."""
    logging.info("Starting bot configuration via synchronous runner...")
    try:
        # Run the async setup function synchronously
        asyncio.run(_set_webhook_async())
        logging.info("Bot configuration complete. Ready for server startup.")
        
    except Exception as e:
        # Re-raise the exception after logging to ensure Gunicorn/Render stops the deploy
        logging.error(f"Failed to configure bot webhook: '{e}'")
        sys.exit(1)


# The Flask route that Telegram will hit with updates
@app_flask.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handles incoming Telegram updates."""
    logging.info("DEBUG: Received incoming request on Flask webhook route. Attempting to process update.")
    
    try:
        if not request.json:
            logging.warning("Received request but JSON body was empty.")
            return "OK"
        
        update = Update.de_json(request.get_json(force=True), application.bot)

        # CRITICAL FIX: The process_update method is an async coroutine 
        # that must be explicitly run in this synchronous Flask context.
        asyncio.run(application.process_update(update))
        
        # Telegram requires an immediate 200 OK response
        return "OK"
    except Exception as e:
        # Log the error, but still return 200 to Telegram to prevent retry loops
        logging.error(f"Error processing webhook update: {e}", exc_info=True)
        return "OK"

# Basic health check route
@app_flask.route("/", methods=["GET", "HEAD"])
def health_check():
    """Simple health check."""
    return "Bot running", 200

# The standard entry point for Gunicorn
if __name__ == "__main__":
    run_setup()

# CRITICAL FIX: Gevent monkey-patching MUST happen before any
# I/O libraries (like httpx, which PTB uses) are imported).
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
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)

# --- Configuration & Setup ---

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.INFO) 

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
WEBHOOK_URL = os.environ.get("WEBHOOK_BASE_URL", "https://your-app-name.onrender.com")

application = (
    Application.builder()
    .token(TOKEN)
    .concurrent_updates(True) 
    .build()
)

# --- Utility Functions ---

def get_link_from_message(update: Update) -> str | None:
    """Extracts a URL from the message text."""
    if update.message and update.message.text:
        # Simple extraction for raw links
        return update.message.text.strip()
    return None

async def process_download_core(update: Update, context: ContextTypes.DEFAULT_TYPE, link: str, mode: str, message_id: int) -> None:
    """The core function for handling both audio and video downloads."""
    chat_id = update.effective_chat.id
    
    temp_dir = tempfile.mkdtemp()
    
    try:
        logging.info(f"Starting {mode} download for: {link} in temp dir: {temp_dir}")
        
        # --- yt-dlp Options based on Mode ---
        if mode == 'audio':
            mode_description = "Audio Extraction (MP3)"
            # Audio only, converted to MP3
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }],
                'max_filesize': 50 * 1024 * 1024,
                'restrictfilenames': True,
                'noplaylist': True,
                'verbose': False,
                'logger': logging.getLogger('yt_dlp'),
            }
        else: # mode == 'video'
            mode_description = "Video Download (MP4/WebM)"
            # Best quality video and audio combined
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 
                'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                'max_filesize': 50 * 1024 * 1024,
                'restrictfilenames': True,
                'noplaylist': True,
                'verbose': False,
                'logger': logging.getLogger('yt_dlp'),
            }

        # Update message to show processing status
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏳ Step 1/2: Processing link and starting {mode_description} download\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

        # 1. Download the file
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(link, download=True)
            
            # Find the path to the downloaded file
            if mode == 'audio':
                file_ext = '.mp3'
            else:
                # Look for mp4, webm, or any other common video extension
                file_exts = ['.mp4', '.webm', '.mkv']
                found_files = [f for f in os.listdir(temp_dir) if any(f.endswith(ext) for ext in file_exts)]
                file_ext = os.path.splitext(found_files[0])[1] if found_files else '.tmp'
            
            downloaded_files = [f for f in os.listdir(temp_dir) if f.endswith(file_ext)]
            
            if downloaded_files:
                downloaded_file_path = os.path.join(temp_dir, downloaded_files[0])
                file_size_mb = os.path.getsize(downloaded_file_path) / (1024 * 1024)
            else:
                raise FileNotFoundError(f"yt-dlp completed, but the expected {mode} file was not found.")


        # 2. Upload the file to Telegram
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=f"⏳ Step 2/2: Uploading {mode} file: *{info_dict.get('title', 'Unknown Title')}* \\({file_size_mb:.2f} MB\\)\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

        with open(downloaded_file_path, 'rb') as media_file:
            if mode == 'audio':
                await context.bot.send_audio(
                    chat_id=chat_id,
                    audio=media_file,
                    title=info_dict.get('title', 'Downloaded Audio'),
                    performer=info_dict.get('uploader', 'Unknown'),
                    caption=f"Downloaded via the Bot\\. [Original Link]({link})",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            else: # mode == 'video'
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=media_file,
                    caption=f"Downloaded via the Bot\\. [Original Link]({link})",
                    parse_mode=ParseMode.MARKDOWN_V2
                )
            
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "size limit" in error_msg:
             reply_text = f"❌ Download Failed\\. The file size exceeds the 50MB limit\\. Please choose a shorter media file\\."
        elif "Unsupported URL" in error_msg:
            reply_text = "❌ Download Failed\\. The link provided is not supported by the downloader\\."
        else:
            reply_text = "❌ Download Failed\\. An error occurred during the extraction process\\."
        
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=reply_text,
            parse_mode=ParseMode.MARKDOWN_V2
        )
        logging.error(f"yt-dlp Download Error: {e}", exc_info=True)

    except Exception as e:
        logging.error(f"Error in downloader for chat {chat_id}: {e}", exc_info=True)
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text="❌ An internal error occurred during the download process\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"Cleaned up temporary directory: {temp_dir}")


# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message on /start."""
    if update.message:
        await update.message.reply_text(
            "Hello\\! Send me any media link \\(YouTube, etc\\)\\. I'll ask you if you want to download the **Full Video** or the **Audio Only**\\.\n\n"
            "\\*Note: All files are limited to \\~50MB\\.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def prompt_user_for_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Catches a raw link and prompts the user to select video or audio mode."""
    link = get_link_from_message(update)
    if not link:
        return
    
    # Store the link and the message ID for later use in the callback query
    # We store the link in the context.user_data to be retrieved later
    context.user_data['current_link'] = link
    
    keyboard = [
        [
            InlineKeyboardButton("1. 🎬 Full Video (Max 50MB)", callback_data='mode_video'),
            InlineKeyboardButton("2. 🎧 Audio Only (MP3, Max 50MB)", callback_data='mode_audio'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use escape_markdown(link, version=2) for safety within the message text
    escaped_link = link.replace('.', '\\.').replace('-', '\\-').replace('_', '\\_').replace('*', '\\*').replace('[', '\\[').replace('`', '\\`')
    
    await update.message.reply_text(
        f"You sent the link: `{escaped_link}`\n\nWhat would you like to download?",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def handle_mode_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the button press (callback query) to start the download."""
    query = update.callback_query
    # Always call answer to dismiss the loading indicator on the button
    await query.answer()
    
    # Retrieve the stored link and clear it from user_data
    link = context.user_data.pop('current_link', None)
    
    if not link:
        # If the link is not found (e.g., bot restarted or too much time passed)
        await query.edit_message_text(
            "❌ Error: Couldn't find the original link or the link expired\\. Please send the link again to restart\\.", 
            parse_mode=ParseMode.MARKDOWN_V2
        )
        return

    mode = query.data.replace('mode_', '')
    
    # Pass control to the core download function
    await process_download_core(update, context, link, mode, query.message.message_id)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logging.error("Exception while handling an update:", exc_info=context.error)
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🤖 Sorry, I ran into an error\\! Please try again later\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logging.error(f"Failed to send error message: {e}")


# --- Application Configuration ---

application.add_handler(CommandHandler("start", start))

# Handler 1: Catches raw links and prompts for mode selection
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://\S+') & (~filters.COMMAND), prompt_user_for_mode))

# Handler 2: Catches button clicks (callback queries)
application.add_handler(CallbackQueryHandler(handle_mode_selection, pattern='^mode_(audio|video)$'))

application.add_error_handler(error_handler)


# --- Webhook and Server Setup ---

app_flask = Flask(__name__)

async def _set_webhook_async():
    """Internal async function to set the webhook."""
    webhook_path = f"/{TOKEN}"
    full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path
    
    logging.info(f"DEBUG: Using BOT TOKEN (first 10 chars): {TOKEN[:10]}...")
    logging.info(f"DEBUG: Calculated Webhook URL: {full_webhook_url}")
    
    await application.bot.set_webhook(url=full_webhook_url)
    logging.info(f"Webhook successfully set to: {full_webhook_url}")

def run_setup():
    """Sets the webhook on the Telegram side using asyncio.run()."""
    logging.info("Starting bot configuration via synchronous runner...")
    try:
        asyncio.run(_set_webhook_async())
        logging.info("Bot configuration complete. Ready for server startup.")
        
    except Exception as e:
        logging.error(f"Failed to configure bot webhook: '{e}'")
        sys.exit(1)


@app_flask.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handles incoming Telegram updates."""
    logging.info("DEBUG: Received incoming request on Flask webhook route. Attempting to process update.")
    
    try:
        if not request.json:
            logging.warning("Received request but JSON body was empty.")
            return "OK"
        
        update = Update.de_json(request.get_json(force=True), application.bot)

        async def process_telegram_update():
            if not application._initialized:
                await application.initialize()
            
            await application.process_update(update)

        asyncio.run(process_telegram_update())
        
        return "OK"
        
    except Exception as e:
        logging.error(f"Error processing webhook update: {e}", exc_info=True)
        return "OK"

@app_flask.route("/", methods=["GET", "HEAD"])
def health_check():
    """Simple health check."""
    return "Bot running", 200

if __name__ == "__main__":
    run_setup()

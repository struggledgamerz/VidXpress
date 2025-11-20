import logging
import os
import sys
import asyncio
import re
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager 
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    CallbackQueryHandler,
    filters
)

# Third-party library for media extraction
try:
    import yt_dlp
    from yt_dlp.utils import DownloadError # Import specific error for better handling
except ImportError:
    print("FATAL: yt-dlp is not installed. Video download functionality will fail.")


# --- Configuration ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL_BASE", "https://ff-like-bot-px1w.onrender.com")
PORT = int(os.environ.get("PORT", "8080")) 

WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_URL_BASE}{WEBHOOK_PATH}"

# Regular expression to match common video/YouTube URLs
YOUTUBE_URL_REGEX = re.compile(
    r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/shorts\/|facebook\.com|twitch\.tv|vimeo\.com|dailymotion\.com|tiktok\.com\/)([\w\-\/]+)'
)

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Handlers ---

async def start_command(update: Update, context: Application) -> None:
    """Sends a welcome message and instructions when the /start command is issued."""
    logger.info(f"Received /start from user {update.effective_user.id}")
    await update.message.reply_text(
        "👋 Welcome! I can fetch direct download links for videos from many popular sites (like YouTube).\n\n"
        "Just send me a video link, and I'll give you options for video or audio download."
    )

async def url_handler(update: Update, context: Application) -> None:
    """Checks for a URL and provides download buttons if found, otherwise echoes the text."""
    text = update.message.text
    match = YOUTUBE_URL_REGEX.search(text)

    if match:
        url = match.group(0)
        
        # Data format: "action|url"
        video_callback_data = f"download_video|{url}"
        audio_callback_data = f"download_audio|{url}"

        keyboard = [
            [
                InlineKeyboardButton("🎥 Download Video (MP4)", callback_data=video_callback_data),
                InlineKeyboardButton("🎵 Download Audio (MP3)", callback_data=audio_callback_data)
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"Found a link! Please select the format you want.",
            reply_markup=reply_markup
        )
    else:
        # Fallback echo logic for non-URLs
        await update.message.reply_text(f"You said: {text}")


async def button_callback_handler(update: Update, context: Application) -> None:
    """Handles button clicks to retrieve the direct download link using yt-dlp."""
    query = update.callback_query
    await query.answer() # Always answer the callback query to dismiss the loading state
    
    # Check if data exists and contains the separator
    if not query.data or "|" not in query.data:
        await query.edit_message_text("❌ Invalid callback data.")
        return

    try:
        # Split the callback data: e.g., "download_video|https://..."
        action, url = query.data.split("|", 1)
        
        # Give immediate feedback that processing has started
        await query.edit_message_text(f"🚀 Fetching download link for: `{url}`\n\n_This may take a moment..._")
        
        # Configure yt-dlp options based on the requested action
        if action == 'download_video':
            format_selector = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        elif action == 'download_audio':
            format_selector = 'bestaudio/best'
        else:
            await query.edit_message_text("❌ Unknown action requested.")
            return

        # yt-dlp options for link extraction (not actual download)
        ydl_opts = {
            'format': format_selector,
            'skip_download': True,
            'quiet': True,
            'noplaylist': True,
            'force_generic_extractor': True,
            'logger': logging.getLogger('yt-dlp.quiet'), 
            # NEW ROBUSTNESS FLAGS:
            'retries': 5, # Retry failed network connections
            'no_check_formats': True, # Skip strict format checks which can fail in non-browser environments
            # Attempting to bypass JS runtime issues
            'extractor_args': {'youtube': {'player_client': 'default'}},
        }
        
        # Run yt-dlp extraction
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Running this asynchronously is crucial to avoid blocking the Uvicorn worker
            info = await asyncio.to_thread(ydl.extract_info, url, download=False)
            
        # Extract the title and the final URL
        title = info.get('title', 'Your Requested File')
        
        # Check if the desired format is present
        if 'url' in info:
            download_url = info['url']
        elif 'formats' in info and info['formats']:
            # For some sites, the best format is in the list
            download_url = info['formats'][-1].get('url') # Try to get the last (often best) URL
        else:
            download_url = None

        if download_url:
            message = (
                f"✅ **{title}** ready!\n\n"
                f"📥 **Download Link ({'Video (MP4)' if action == 'download_video' else 'Audio (MP3)'}):**\n"
                f"**[Click to Download]({download_url})**\n\n"
                f"`{download_url}`\n\n" # Also provide the link as raw text for easy copy
                f"_Note: The link is valid for a limited time._"
            )
            await query.edit_message_text(message, parse_mode='Markdown')
        else:
            await query.edit_message_text("❌ Could not find a direct download link. The content might be geoblocked, private, or unsupported by the service.")

    except DownloadError as e: # Catch the specific yt-dlp error
        logger.error(f"yt-dlp DownloadError for {url}: {e}")
        # Custom message for the user explaining the likely cause
        error_message = str(e)
        if "Sign in to confirm" in error_message or "confirm your age" in error_message:
             user_friendly_error = (
                 f"⚠️ **Cannot access the video.**\n\n"
                 "The video is likely **age-restricted**, **private**, or **geoblocked**.\n\n"
                 "_The server cannot sign in or bypass these restrictions._"
             )
        else:
            # Catch other download-related errors (e.g., video deleted)
            user_friendly_error = (
                 f"❌ **Download Extraction Failed.**\n\n"
                 "The video link might be broken, unsupported, or the content has been removed."
             )
        
        await query.edit_message_text(user_friendly_error, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in callback handler: {e}", exc_info=True)
        # Inform the user about the failure
        await query.edit_message_text(f"❌ An unexpected error occurred while processing the link. ({e.__class__.__name__})")

async def error_handler(update: Update, context: Application) -> None:
    """Log the error."""
    logger.error("Exception while handling an update:", exc_info=context.error)

# --- PTB Application Setup ---

def build_application() -> Application:
    """Builds and returns the PTB Application instance."""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .updater(None)  
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CallbackQueryHandler(button_callback_handler)) 
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, url_handler))
    application.add_error_handler(error_handler)
    
    return application

# Initialize the application instance globally
application = build_application()

# --- Webhook Setup Function (Runs ONLY before Uvicorn starts) ---

def run_setup():
    """Synchronous setup function to set the webhook URL."""
    if "YOUR_BOT_TOKEN_HERE" in BOT_TOKEN:
        logger.error("FATAL: BOT_TOKEN is not configured! Cannot set webhook.")
        sys.exit(1)
        
    logger.info("Starting bot configuration via synchronous runner...")
    logger.info(f"DEBUG: Calculated Webhook URL: {WEBHOOK_URL}")

    async def set_webhook_async():
        await application.initialize() 
        await application.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            max_connections=40
        )
        
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(set_webhook_async()) 
        logger.info(f"Webhook successfully set to: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")

    logger.info("Bot configuration complete. Ready for server startup.")


# --- FastAPI Web Server with Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Ensures the PTB Application object is initialized and started 
    within the main Uvicorn worker process's async event loop.
    """
    logger.info("FastAPI Startup: Calling Application.initialize()...")
    await application.initialize()
    logger.info("FastAPI Startup: Application initialized. Starting PTB async tasks...")
    await application.start()
    
    yield 
    
    logger.info("FastAPI Shutdown: Stopping PTB async tasks...")
    await application.stop()
    logger.info("FastAPI Shutdown complete.")


# The main FastAPI application instance (used by Uvicorn)
app_fastapi = FastAPI(title="Async Telegram Webhook Bot", lifespan=lifespan)

@app_fastapi.get("/")
def health_check():
    """Simple endpoint for health checks."""
    return {"status": "ok"}

@app_fastapi.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """The main webhook endpoint that receives updates from Telegram."""
    
    # 1. Get JSON data from the request body asynchronously
    try:
        json_data: Dict[str, Any] = await request.json()
    except Exception as e:
        logger.error(f"Error reading request JSON: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    logger.info("Received incoming request on FastAPI webhook route. Attempting to process update.")

    # 2. Convert the raw JSON into a PTB Update object
    try:
        update = Update.de_json(json_data, application.bot)
    except Exception as e:
        logger.error(f"Error creating Update object: {e}")
        return {"message": "Update creation failed, but request received"}

    # 3. Process the update asynchronously
    try:
        # This is where the handlers are executed asynchronously
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return {"message": "Update processing failed internally"}


    # 4. Return the standard 'OK' response to Telegram
    return {"message": "ok"}


if __name__ == "__main__":
    try:
        import uvicorn
        logger.info("Running setup...")
        run_setup()
        logger.info("Starting local server with Uvicorn...")
        uvicorn.run(app_fastapi, host="0.0.0.0", port=PORT)
    except ImportError:
        logger.error("Uvicorn is not installed.")
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")

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
            "Hello! Send me a link to download content.",
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user's link, sends a 'wait' message, and simulates the download."""
    if not update.message:
        return

    try:
        # Acknowledge receipt of the link immediately
        await update.message.reply_text("⏳ Downloading... Please wait.")

        # --- ACTUAL DOWNLOAD LOGIC WITH YT-DLP GOES HERE ---
        link = update.message.text
        logging.info(f"Received link for download: {link}")
        
        # NOTE: Implement your blocking yt-dlp logic here.
        # Since gevent is patching, synchronous I/O should work within the worker.
        
        # Example using context.bot to send the final message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"✅ Download simulation complete for: `{link}`"
        )

    except Exception as e:
        logging.error(f"Error in downloader for chat {update.effective_chat.id}: {e}", exc_info=True)
        await update.message.reply_text("❌ An internal error occurred during the download process.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logging.error("Exception while handling an update:", exc_info=context.error)
    if update and update.effective_chat:
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="🤖 Sorry, I ran into an error! Please try again later."
            )
        except Exception as e:
            logging.error(f"Failed to send error message: {e}")


# --- Application Configuration ---

application.add_handler(CommandHandler("start", start))
# Handle all incoming text messages that look like a URL
application.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'https?://\S+'), downloader))
application.add_error_handler(error_handler)


# --- Webhook and Server Setup ---

# Create the Flask application instance
app_flask = Flask(__name__)

async def _set_webhook_async():
    """Internal async function to set the webhook."""
    webhook_path = f"/{TOKEN}"
    full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path
    
    # Use the async context manager for setup/teardown
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
        # Exit with a non-zero status code to signal a failed startup
        sys.exit(1)


# The Flask route that Telegram will hit with updates
@app_flask.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handles incoming Telegram updates."""
    # Process the update using the Telegram Application instance
    try:
        if not request.json:
            return "OK"
            
        update = Update.de_json(request.get_json(force=True), application.bot)
        # Process the update asynchronously within the Gevent worker
        application.process_update(update)
        # Telegram expects an HTTP 200 response immediately
        return "OK"
    except Exception as e:
        # Log the error, but still return 200 to Telegram to prevent retry floods
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
    # Gunicorn command: gunicorn --bind 0.0.0.0:$PORT main:app_flask --worker-class gevent

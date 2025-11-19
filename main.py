# CRITICAL FIX: Gevent monkey-patching MUST happen before any
# I/O libraries (like httpx, which PTB uses) are imported.
# This prevents the "RuntimeError: Event loop is closed" error
# and is necessary for gevent workers to function correctly with asyncio code.
from gevent import monkey
monkey.patch_all()

import logging
import os
import sys

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
logging.getLogger("telegram").setLevel(logging.INFO) # Keep telegram logs useful

# Read token and webhook URL from environment variables
# NOTE: Make sure these environment variables are correctly set in your deployment configuration.
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-app-name.onrender.com")

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
    # Ensure the update object and message are present before replying
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
        
        # NOTE: Your actual yt-dlp/download logic needs to be integrated here.
        # Since we are using gevent, synchronous I/O should work, but be mindful of long tasks.
        # For production-grade resilience, complex/long tasks should ideally be offloaded.
        
        # Simulate work
        # import time; time.sleep(5) 
        
        await update.message.reply_text(f"✅ Download simulation complete for: `{link}`")

    except Exception as e:
        logging.error(f"Error in downloader for chat {update.effective_chat.id}: {e}", exc_info=True)
        await update.message.reply_text("❌ An internal error occurred during the download process.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logging.error("Exception while handling an update:", exc_info=context.error)
    # Only reply if there is an update object and a message
    if update and update.effective_chat:
        try:
            # We use context.bot.send_message instead of update.message.reply_text because 
            # the error might occur before a message object is available (e.g., in inline queries)
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

# Define the run_setup function to set the webhook
def run_setup():
    """Sets the webhook on the Telegram side."""
    logging.info("Starting bot configuration via synchronous runner...")
    
    webhook_path = f"/{TOKEN}"
    full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path
    
    try:
        # Use run_polling for a one-off run to set the webhook.
        # This correctly initializes and runs the necessary async components once.
        application.run_polling(
            drop_interval=1,
            check_interval=0.1,
            poll_interval=0,
            close_loop=True,
            stop_signals=None,
            startup_webhook=full_webhook_url,
            max_iterations=1,
            timeout=10,
        )

        logging.info(f"Webhook successfully set to: {full_webhook_url}")
        logging.info("Bot configuration complete. Ready for server startup.")
        
    except Exception as e:
        # Re-raise the exception after logging to ensure Gunicorn/Render stops the deploy
        logging.error(f"Failed to configure bot webhook: '{e}'")
        sys.exit(1)


# The Flask route that Telegram will hit with updates
@app_flask.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handles incoming Telegram updates."""
    # Process the update using the Telegram Application instance
    try:
        # Check for empty JSON body which can happen if Telegram pings the webhook URL
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
    # Gunicorn will start the app_flask object using its command:
    # gunicorn --bind 0.0.0.0:$PORT main:app_flask --worker-class gevent

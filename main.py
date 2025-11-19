# CRITICAL FIX: Gevent monkey-patching MUST happen before any
# I/O libraries (like httpx, which PTB uses) are imported.
# This prevents the "RuntimeError: Event loop is closed" error.
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

# Read token and webhook URL from environment variables
# NOTE: Replace these with your actual environment variable names
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-app-name.onrender.com")

# Initialize the bot Application
application = (
    Application.builder()
    .token(TOKEN)
    .build()
)

# --- Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a welcome message on /start."""
    await update.message.reply_text(
        "Hello! Send me a link to download content.",
        parse_mode=ParseMode.MARKDOWN_V2
    )

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles the user's link, sends a 'wait' message, and simulates the download."""
    # This is the line that was failing due to the event loop issue
    # The monkey.patch_all() at the top should resolve this.
    try:
        await update.message.reply_text("⏳ Downloading... Please wait.")

        # Simulate your actual yt-dlp/download logic here
        link = update.message.text
        # Example of where your long-running or blocking download would go
        # If this is blocking, you should consider using anyio.to_thread.run_sync()
        # if using the pure async application builder, but since we are monkey-patching,
        # standard blocking I/O should be okay (though not ideal).
        
        await update.message.reply_text(f"✅ Download complete for: `{link}`")

    except Exception as e:
        logging.error(f"Error in downloader for chat {update.effective_chat.id}: {e}")
        await update.message.reply_text("❌ An error occurred during the download process.")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a message to the user."""
    logging.error("Exception while handling an update:", exc_info=context.error)
    # Only reply if there is an update object and a message
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

# Define the run_setup function to set the webhook
def run_setup():
    """Sets the webhook on the Telegram side."""
    try:
        logging.info("Starting bot configuration via synchronous runner...")
        
        # Use Application.post_init to perform async setup in a sync context
        # This is a safe way to call async setup functions at startup.
        application.post_init()
        
        # Set the webhook URL
        webhook_path = f"/{TOKEN}"
        full_webhook_url = WEBHOOK_URL.rstrip('/') + webhook_path
        
        # Application.set_webhook must be called in a running async context,
        # so we use application.run_polling() with 'drop_interval' to run 
        # a one-off task in a temporary application runner.
        application.run_polling(
            drop_interval=1,
            check_interval=0.1,
            poll_interval=0,
            close_loop=True, # Ensure the loop closes after the task
            stop_signals=None, # Don't rely on OS signals here
            # Set the webhook inside the startup hook
            # Note: We use the runner's application instance to set the webhook
            # as it's guaranteed to be in a valid async context.
            startup_webhook=full_webhook_url,
            # We only want to run the startup, not continuously poll
            max_iterations=1,
            timeout=10,
        )

        logging.info(f"Webhook successfully set to: {full_webhook_url}")
        logging.info("Bot configuration complete. Ready for server startup.")
        
    except Exception as e:
        logging.error(f"Failed to configure bot webhook: {e}")
        # Exit if setup fails critically
        sys.exit(1)


# The Flask route that Telegram will hit with updates
@app_flask.route(f"/{TOKEN}", methods=["POST"])
def telegram_webhook():
    """Handles incoming Telegram updates."""
    # Process the update using the Telegram Application instance
    try:
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
    # In a local environment, you would run the Flask app directly
    # app_flask.run(port=8000)

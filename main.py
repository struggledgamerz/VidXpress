import logging
import os
import sys
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters
)

# --- Configuration ---
# Use environment variables for sensitive data
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
# WEBHOOK_URL_BASE is the base URL of your deployed service (e.g., https://ff-like-bot-px1w.onrender.com)
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL_BASE", "https://ff-like-bot-px1w.onrender.com")
# PORT is provided by the environment (e.g., Render)
PORT = int(os.environ.get("PORT", "8080")) 

# The full webhook path Telegram will call
WEBHOOK_URL = f"{WEBHOOK_URL_BASE}/{BOT_TOKEN}"

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Application and Handlers ---

async def start_command(update: Update, context: Application) -> None:
    """Sends a welcome message when the /start command is issued."""
    logger.info(f"Received /start from user {update.effective_user.id}")
    await update.message.reply_text(
        "Welcome! I'm a simple bot running on an asynchronous server (Uvicorn/FastAPI). "
        "Send me any text!"
    )

async def echo_message(update: Update, context: Application) -> None:
    """Echoes the user's message."""
    logger.info(f"Received message from user {update.effective_user.id}: {update.message.text}")
    text = update.message.text
    # Simple logic: if the user sends text, echo it back
    if text:
        await update.message.reply_text(f"You said: {text}")

async def error_handler(update: Update, context: Application) -> None:
    """Log the error and notify the user (optional)."""
    logger.error("Exception while handling an update:", exc_info=context.error)

# --- PTB Application Setup ---

def build_application() -> Application:
    """Builds and returns the PTB Application instance."""
    # We use Application.builder() for the modern, async PTB
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .updater(None)  # We are using webhooks, so no built-in polling/updater
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))
    application.add_error_handler(error_handler)
    
    return application

# Initialize the application instance
application = build_application()

# --- Webhook Setup Function (called once on startup) ---

def run_setup():
    """
    Synchronous setup function called by the deployment environment 
    to set the webhook URL before the server starts.
    """
    logger.info("Starting bot configuration via synchronous runner...")

    if "YOUR_BOT_TOKEN_HERE" in BOT_TOKEN:
        logger.error("FATAL: BOT_TOKEN is not configured! Cannot set webhook.")
        sys.exit(1)

    logger.info(f"DEBUG: Using BOT TOKEN (first 10 chars): {BOT_TOKEN[:10]}...")
    logger.info(f"DEBUG: Calculated Webhook URL: {WEBHOOK_URL}")

    # Use a separate asyncio event loop for the setup phase
    # This ensures the async PTB application methods can be called correctly
    async def set_webhook_async():
        await application.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            # We set a max_connections limit as a best practice
            max_connections=40
        )
        
    try:
        # Run the async setup in a new event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(application.initialize())
        loop.run_until_complete(set_webhook_async())
        logger.info(f"Webhook successfully set to: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        # In a production environment, you might want to exit here if setup fails
        
    logger.info("Bot configuration complete. Ready for server startup.")


# --- FastAPI Web Server ---

# The main FastAPI application instance (used by Uvicorn)
app_fastapi = FastAPI(title="Async Telegram Webhook Bot")

@app_fastapi.get("/")
def health_check():
    """Simple endpoint for health checks."""
    return {"status": "ok"}

@app_fastapi.post(f"/{BOT_TOKEN}")
async def telegram_webhook(request: Request):
    """
    The main webhook endpoint that receives updates from Telegram.
    
    NOTE: We use the full BOT_TOKEN as the route path, matching the WEBHOOK_URL.
    """
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
        # Return OK anyway to tell Telegram we received the message
        return {"message": "Update creation failed, but request received"}

    # 3. Process the update asynchronously! This is the fix for the RuntimeWarning.
    try:
        # Crucial: Must use 'await' here since process_update is an async function
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        # Still return OK so Telegram doesn't keep retrying the same update
        return {"message": "Update processing failed internally"}


    # 4. Return the standard 'OK' response to Telegram
    return {"message": "ok"}


if __name__ == "__main__":
    # If running locally (e.g., for local testing before deployment)
    try:
        # This is a local development/testing block, NOT typically run on Render/similar platforms
        # since they call 'run_setup()' and then use Uvicorn via the start command.
        
        # If you run this file directly, it will start Uvicorn
        import uvicorn
        logger.info("Running locally via Uvicorn. Webhooks will not work unless you use a tunneling service like ngrok.")
        application.run_polling(poll_interval=1.0, allowed_updates=Update.ALL_TYPES)
        # You would typically run setup manually before starting the server locally, or use polling
        # run_setup()
        # uvicorn.run(app_fastapi, host="0.0.0.0", port=PORT)
    except ImportError:
        logger.error("Uvicorn is not installed. Cannot run locally. Did you forget to install it?")
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        

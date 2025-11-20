import logging
import os
import sys
import asyncio
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException
from contextlib import asynccontextmanager 
from telegram import Update
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler, 
    filters
)

# --- Configuration ---
# Use environment variables for sensitive data
# Note: The deployment environment automatically provides the BOT_TOKEN
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
# WEBHOOK_URL_BASE is the base URL of your deployed service (e.g., https://ff-like-bot-px1w.onrender.com)
WEBHOOK_URL_BASE = os.environ.get("WEBHOOK_URL_BASE", "https://ff-like-bot-px1w.onrender.com")
# PORT is provided by the environment (e.g., Render)
PORT = int(os.environ.get("PORT", "8080")) 

# The full webhook path Telegram will call
WEBHOOK_PATH = f"/{BOT_TOKEN}"
WEBHOOK_URL = f"{WEBHOOK_URL_BASE}{WEBHOOK_PATH}"

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
        "Welcome! I'm running on a speedy asynchronous server (Uvicorn/FastAPI). "
        "Send me any text!"
    )

async def echo_message(update: Update, context: Application) -> None:
    """Echoes the user's message."""
    logger.info(f"Received message from user {update.effective_user.id}: {update.message.text}")
    text = update.message.text
    if text:
        await update.message.reply_text(f"You said: {text}")

async def error_handler(update: Update, context: Application) -> None:
    """Log the error."""
    # We log the error using the context's error attribute
    logger.error("Exception while handling an update:", exc_info=context.error)

# --- PTB Application Setup ---

def build_application() -> Application:
    """Builds and returns the PTB Application instance."""
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .updater(None)  # Use None for webhook deployments
        .build()
    )

    # Register handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo_message))
    application.add_error_handler(error_handler)
    
    return application

# Initialize the application instance globally
application = build_application()

# --- Webhook Setup Function (Runs ONLY before Uvicorn starts) ---

def run_setup():
    """
    Synchronous setup function called by the deployment environment 
    to set the webhook URL before the Uvicorn server starts.
    This runs the webhook setting operation.
    """
    if "YOUR_BOT_TOKEN_HERE" in BOT_TOKEN:
        logger.error("FATAL: BOT_TOKEN is not configured! Cannot set webhook.")
        sys.exit(1)
        
    logger.info("Starting bot configuration via synchronous runner...")
    logger.info(f"DEBUG: Calculated Webhook URL: {WEBHOOK_URL}")

    async def set_webhook_async():
        # Initialize must be called first to allow bot calls
        await application.initialize() 
        await application.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            max_connections=40
        )
        
    try:
        # Create and run in a new event loop for this synchronous setup phase
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(set_webhook_async()) 
        logger.info(f"Webhook successfully set to: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook: {e}")
        # We allow the process to continue even if webhook setting failed, 
        # as a previous webhook might still be active.

    logger.info("Bot configuration complete. Ready for server startup.")


# --- FastAPI Web Server with Lifespan (The fix for the Runtime Error) ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager runs code at application startup and shutdown.
    This ensures the PTB Application object is initialized within the main 
    Uvicorn worker process's async event loop.
    """
    logger.info("FastAPI Startup: Calling Application.initialize()...")
    # CRITICAL FIX for the 'Application was not initialized' error:
    await application.initialize()
    logger.info("FastAPI Startup: Application initialized. Starting PTB async tasks...")
    # Start the application's background tasks (necessary for job queue, etc.)
    await application.start()
    
    yield # Server is running and ready to handle requests
    
    # Code below runs on application shutdown
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
        # Returning a response anyway
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
    # Local running block - not executed during standard deployment, but useful for testing
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

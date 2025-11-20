import os
import re
import logging
import shutil
import concurrent.futures
from urllib.parse import urlparse

# --- Telegram/Web Framework Imports ---
from fastapi import FastAPI, Request, Response, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Import the main download function from the local file
from download_manager import download_media, logger as download_logger

# --- Configuration ---
# NOTE: The token is securely retrieved from the environment variable TELEGRAM_BOT_TOKEN.
# The user-provided token is set as a fallback for local testing.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY") 
# The deployment URL provided by the user is used here.
WEBHOOK_URL = os.environ.get("WEBHOOK_URL_BASE", "https://ff-like-bot-px1w.onrender.com")
PORT = int(os.environ.get("PORT", "8080")) # Default port for Uvicorn

# Set up main logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
bot_logger = logging.getLogger('TelegramBot')
download_logger.setLevel(logging.WARNING) 

# --- Global State ---
# Initialize FastAPI app and Telegram Application globally
app_fastapi = FastAPI()
application = None 

# --- Thread Pool Executor ---
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


# --- Handlers ---

async def start_command(update: Update, context: CallbackContext) -> None:
    """Sends a welcome message when the /start command is issued."""
    user = update.effective_user
    await update.message.reply_html(
        f"Hi {user.first_name}!\n\n"
        "Send me a URL from YouTube, Instagram, Threads, Moj, or Chingari, and I will try to download the media for you.\n\n"
        "Please be patient, as large video files may take a moment to process.",
    )

def extract_url(text):
    """Simple regex to extract the first URL from a string."""
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

async def handle_url(update: Update, context: CallbackContext) -> None:
    """Processes incoming messages that might contain a URL."""
    text = update.message.text
    url = extract_url(text)

    if not url:
        # Silently return if no URL is found, as we are now using filters.TEXT
        return 

    # Send an initial message to the user that the request is being processed
    status_message = await update.message.reply_text(f"Processing URL: `{url}`\n\nStarting download... (This might take a moment)", parse_mode='Markdown')
    
    # Run the download process in the background thread pool
    future = executor.submit(download_media, url)
    
    # Store necessary context information to use in the callback
    callback_args = {
        'chat_id': update.effective_chat.id,
        'reply_to_message_id': update.message.message_id,
        'status_message_id': status_message.message_id,
        'context': context,
    }

    # Attach the callback function to handle the result when the download is finished
    future.add_done_callback(lambda f: execute_callback(f, callback_args))


def execute_callback(future: concurrent.futures.Future, callback_args: dict):
    """
    Callback executed when the download_media thread finishes.
    This function prepares the result and calls the asynchronous send_media_callback.
    """
    try:
        # Retrieve the result (filepath, temp_dir) from the future
        result = future.result()
        # Create a new event loop and run the async callback to send the file
        context = callback_args['context']
        context.application.loop.create_task(send_media_callback(result, callback_args))
    except Exception as e:
        bot_logger.error(f"Error executing callback: {e}")
        # Attempt to clean up the status message
        context = callback_args['context']
        context.application.loop.create_task(
            context.bot.edit_message_text(
                chat_id=callback_args['chat_id'],
                message_id=callback_args['status_message_id'],
                text="An unexpected error occurred during processing. Please try again."
            )
        )


async def send_media_callback(result: tuple, args: dict):
    """
    Asynchronously sends the downloaded file to the user and cleans up.
    """
    path, temp_dir = result
    chat_id = args['chat_id']
    status_message_id = args['status_message_id']
    context = args['context']
    bot = context.bot

    try:
        # 1. Check for success
        if not path:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text="❌ Could not download media from the provided URL. The link may be invalid or restricted."
            )
            return

        # 2. Prepare file
        filename = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        
        bot_logger.info(f"Successfully downloaded file: {path}")

        # 3. Determine send method
        send_method = bot.send_document # Default fallback
        caption = f"✅ Download Complete: `{filename}`"
        
        if ext in ['.mp4', '.mov', '.webm', '.mkv']:
            send_method = bot.send_video
            caption = "✅ Video Downloaded"
        elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
            send_method = bot.send_photo
            caption = "✅ Image Downloaded"

        # 4. Send the file
        with open(path, 'rb') as f:
            # First, delete the "Downloading..." message
            await bot.delete_message(chat_id=chat_id, message_id=status_message_id)

            # Then, send the media file
            await send_method(
                chat_id=chat_id,
                document=f,
                caption=caption,
                # Use reply_to_message_id to link the response to the original command
                reply_to_message_id=args['reply_to_message_id'], 
                parse_mode='Markdown'
            )
            bot_logger.info(f"Sent media to chat {chat_id}")

    except Exception as e:
        bot_logger.error(f"Failed to send file or encountered error: {e}")
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text=f"An error occurred while sending the file: {e}"
        )
    finally:
        # 5. Cleanup temporary directory
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                bot_logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except OSError as e:
                bot_logger.error(f"Error cleaning up temp directory {temp_dir}: {e}")


# --- Telegram Bot Setup (Function called by run_setup) ---

def setup_bot():
    """Initializes the Telegram Application, handlers, and webhook."""
    global application
    
    # Check configuration for deployment only
    if BOT_TOKEN == "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY" or WEBHOOK_URL == "https://ff-like-bot-px1w.onrender.com":
        bot_logger.warning("Configuration variables are using hardcoded fallbacks. Ensure you set environment variables for production.")

    # 1. Build the Telegram Application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .updater(None) # Crucial: disable internal polling updater
        .build()
    )

    # 2. Add Handlers
    application.add_handler(CommandHandler("start", start_command))
    
    # Use filters.TEXT and rely on the internal extract_url check
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)
    )
    
    # 3. Set Webhook
    webhook_path = "/webhook"
    webhook_url = WEBHOOK_URL + webhook_path
    
    # We call run_webhook to configure the server environment
    application.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=webhook_path,
        webhook_url=webhook_url,
    )

    bot_logger.info(f"Webhook set to: {webhook_url}")
    return application


# --- Deployment Entry Points ---

# Placeholder function required by the deployment command: python3 -c "import main; main.run_setup()"
def run_setup():
    """Initializes and configures the bot for webhook deployment."""
    global application
    application = setup_bot()
    bot_logger.info("Bot setup complete (Webhooks configured).")


# FastAPI route to receive Telegram updates
@app_fastapi.post("/webhook")
async def telegram_webhook(request: Request):
    """Handles incoming Telegram updates via the webhook."""
    global application
    
    if not application:
        # If application hasn't been initialized (e.g., setup failed), return 503
        raise HTTPException(status_code=503, detail="Bot not initialized. Check run_setup.")
        
    try:
        # Get the update data from the request body
        update_json = await request.json()
        
        # Convert JSON data to Telegram Update object
        update = Update.de_json(update_json, application.bot)
        
        # Process the update using the Application's dispatcher
        await application.update_queue.put(update)

        # Always return 200 OK immediately to Telegram
        return Response(status_code=200)

    except Exception as e:
        bot_logger.error(f"Error processing webhook update: {e}")
        # Return 200 OK even on error to prevent Telegram from retrying constantly
        return Response(status_code=200)


# --- Local Execution (Polling Fallback) ---

if __name__ == "__main__":
    """Runs the bot in polling mode for local development."""
    bot_logger.info("Starting bot in LOCAL POLLING MODE...")
    
    if BOT_TOKEN == "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY":
        bot_logger.warning("Using hardcoded BOT_TOKEN for local testing.")

    try:
        # Initialize the Application
        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .build()
        )
        
        # Add Handlers
        application.add_handler(CommandHandler("start", start_command))
        
        # Use filters.TEXT and rely on the internal extract_url check
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)
        )
        
        # Start the Polling loop
        application.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        bot_logger.error(f"Failed to start bot in polling mode: {e}")
        

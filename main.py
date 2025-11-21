import os
import re
import logging
import shutil
import concurrent.futures
import asyncio
from contextlib import asynccontextmanager

# --- Telegram/Web Framework Imports ---
from fastapi import FastAPI, Request, Response, HTTPException
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# Import the main download function from the local file
from download_manager import download_media, logger as download_logger

# --- Configuration ---
# NOTE: The token is securely retrieved from the environment variable TELEGRAM_BOT_TOKEN.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY") 
WEBHOOK_URL = os.environ.get("WEBHOOK_BASE_URL", "https://ff-like-bot-px1w.onrender.com")
PORT = int(os.environ.get("PORT", "8080")) # Default port for Uvicorn

# Set up main logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
bot_logger = logging.getLogger('TelegramBot')
download_logger.setLevel(logging.WARNING) 

# --- Global State ---
# Initialize Telegram Application globally. It will be set in the lifespan event.
application: Application = None 
# NEW: Global variable to store the main asyncio event loop reference
MAIN_LOOP: asyncio.AbstractEventLoop = None 

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
    This function prepares the result and safely schedules the asynchronous 
    Telegram response onto the main event loop using run_coroutine_threadsafe.
    """
    context = callback_args['context']
    
    global MAIN_LOOP # Use the global loop reference

    # CRITICAL FIX: Use the globally stored MAIN_LOOP which was set during Uvicorn startup.
    main_loop = MAIN_LOOP 
    
    if not main_loop:
        bot_logger.error("MAIN_LOOP is not set. Cannot schedule async task.")
        return

    try:
        # Retrieve the result (filepath, temp_dir) from the future
        result = future.result()
        
        # Define the coroutine to run on the main loop
        coro = send_media_callback(result, callback_args)
        
        # Schedule the coroutine
        asyncio.run_coroutine_threadsafe(coro, main_loop)
        
    except Exception as e:
        bot_logger.error(f"Error executing callback: {e}")
        
        # If an error occurs, define a coroutine to send the error message
        async def error_edit_message():
            await context.bot.edit_message_text(
                chat_id=callback_args['chat_id'],
                message_id=callback_args['status_message_id'],
                text=f"An unexpected error occurred during processing: {str(e)}"
            )

        # Safely schedule the error coroutine
        asyncio.run_coroutine_threadsafe(error_edit_message(), main_loop)


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
                text="❌ Could not download media from the provided URL. The link may be invalid or restricted. (Check for sign-in requirements or region locks.)"
            )
            return

        # 2. Prepare file
        filename = os.path.basename(path)
        ext = os.path.splitext(path)[1].lower()
        
        bot_logger.info(f"Successfully downloaded file: {path}")

        # 3. Determine send method
        send_method = bot.send_document 
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


# --- Telegram Bot Initialization ---

async def init_bot_async() -> Application:
    """Initializes the Telegram Application and handlers."""
    
    # Check configuration for deployment only
    if BOT_TOKEN == "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY" or WEBHOOK_URL == "https://ff-like-bot-px1w.onrender.com":
        bot_logger.warning("Configuration variables are using hardcoded fallbacks. Ensure you set environment variables for production.")

    # 1. Build the Telegram Application
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .updater(None) # Disable internal polling updater
        .build()
    )
    
    # Initialize Application's internal state
    await app.initialize()

    # 2. Add Handlers
    app.add_handler(CommandHandler("start", start_command))
    
    # Use filters.TEXT and rely on the internal extract_url check
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)
    )
    
    return app

async def set_webhook_async():
    """Manually sets the webhook URL with Telegram."""
    # We build a temporary application object just to call set_webhook once
    temp_app = Application.builder().token(BOT_TOKEN).updater(None).build()
    await temp_app.initialize()

    webhook_path = "/webhook"
    webhook_url = WEBHOOK_URL + webhook_path
    
    await temp_app.bot.set_webhook(url=webhook_url)
    bot_logger.info(f"Webhook successfully registered to: {webhook_url}")

# --- FastAPI Setup and Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI Lifespan: Initializes the Telegram Application for each Uvicorn worker process.
    """
    global application, MAIN_LOOP
    bot_logger.info("Initializing Telegram Application for Uvicorn worker...")
    
    # Initialize the global application object
    application = await init_bot_async()

    # Start the application internal update processing
    await application.start()
    
    # CRITICAL FIX: Store the main event loop reference here, 
    # where we are guaranteed to be in the running loop context.
    MAIN_LOOP = asyncio.get_running_loop()

    bot_logger.info("Telegram Application ready in worker.")
    yield # Server starts listening

    # Cleanup: This runs when the server shuts down
    await application.stop()
    MAIN_LOOP = None # Clear loop reference on shutdown
    bot_logger.info("Telegram Application shut down.")


# Initialize FastAPI with the lifespan context manager
app_fastapi = FastAPI(lifespan=lifespan)

# --- Deployment Entry Points ---

# Function required by the deployment command: python3 -c "import main; main.run_setup()"
def run_setup():
    """
    Synchronously runs the async set_webhook_async function to register the webhook URL.
    This runs in the initial Render build phase before Uvicorn starts.
    """
    # Use a new event loop to run the async setup synchronously
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Register the webhook once
    loop.run_until_complete(set_webhook_async())
    
    bot_logger.info("Bot setup complete (Webhook registered).")


# FastAPI route to handle root path health checks
@app_fastapi.get("/")
def read_root():
    """Returns a simple message for health checks."""
    return {"message": "Telegram Bot Webhook Service is running"}


# FastAPI route to receive Telegram updates
@app_fastapi.post("/webhook")
async def telegram_webhook(request: Request):
    """Handles incoming Telegram updates via the webhook."""
    global application
    
    if not application:
        # This guard should rarely be hit now due to the lifespan manager
        raise HTTPException(status_code=503, detail="Bot not initialized in worker.")
        
    try:
        # Get the update data from the request body
        update_json = await request.json()
        
        # Convert JSON data to Telegram Update object
        update = Update.de_json(update_json, application.bot)
        
        # Put the update into the Application's internal queue for processing
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
        # Initialize and run polling synchronously
        app = asyncio.run(init_bot_async())
        app.run_polling(allowed_updates=Update.ALL_TYPES)
        
    except Exception as e:
        bot_logger.error(f"Failed to start bot in polling mode: {e}")

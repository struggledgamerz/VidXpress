import os
import re
import logging
import shutil
import concurrent.futures
from urllib.parse import urlparse

# Import the main download function from the local file
from download_manager import download_media, logger as download_logger

# Import telegram libraries
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext

# --- Configuration ---
# You MUST replace 'YOUR_BOT_TOKEN_HERE' with your actual Telegram bot token.
# Using an environment variable is safer in production.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY") 

# Set up main logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
# Use a custom logger for the bot
bot_logger = logging.getLogger('TelegramBot')
# Set the download manager logger level higher to only show serious issues in the console
download_logger.setLevel(logging.WARNING) 


# --- Thread Pool Executor ---
# Use a thread pool to handle media downloads in the background, preventing the bot 
# from freezing while waiting for large files.
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
    # This regex looks for http or https links
    urls = re.findall(r'https?://[^\s]+', text)
    return urls[0] if urls else None

async def handle_url(update: Update, context: CallbackContext) -> None:
    """Processes incoming messages that might contain a URL."""
    text = update.message.text
    url = extract_url(text)

    if not url:
        # Should not happen often if the filter is set correctly, but acts as a safeguard
        await update.message.reply_text("Please send a valid URL.")
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


def main() -> None:
    """Start the bot."""
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        bot_logger.error("Please set the TELEGRAM_BOT_TOKEN environment variable or replace the placeholder in main.py.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # --- Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    
    # Message handler for any text containing a URL
    application.add_handler(
        MessageHandler(filters.TEXT & filters.URL & ~filters.COMMAND, handle_url)
    )

    # Run the bot until the user presses Ctrl-C
    bot_logger.info("Bot started successfully. Listening for messages...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

import os
import logging
import shutil
import json
import asyncio # Imported to bridge synchronous Flask with asynchronous Telegram code
from flask import Flask, request, Response 
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from http import HTTPStatus
from download_manager import download_media # Assuming download_manager is updated with None, None fix

# --- CONFIGURATION ---
TOKEN = os.environ.get("TELEGRAM_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
PORT = int(os.environ.get("PORT", "8080"))
# IMPORTANT: The user MUST set this environment variable on Render
WEBHOOK_BASE_URL = os.environ.get("WEBHOOK_BASE_URL", "https://your-app-name.example.com") 
WEBHOOK_URL_PATH = f"/{TOKEN}" 
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}{WEBHOOK_URL_PATH}"
# --- END CONFIGURATION ---

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Initialize Flask App
app_flask = Flask(__name__)

# Initialize Telegram Bot Application
application = ApplicationBuilder().token(TOKEN).build()

# --- HANDLERS ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and explains the bot's function."""
    await update.message.reply_text(
        "Hello! Send any video link — Instagram, YouTube, TikTok, Facebook, X, Threads, Moj, Chingari etc."
    )

async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the download request, sends the file, and cleans up."""
    if not update.message or not update.message.text:
        return
        
    url = update.message.text.strip()

    await update.message.reply_text("⏳ Downloading… Please wait.")

    # We rely on download_media returning (file_path, temp_dir) or (None, None)
    file_path, temp = download_media(url)

    try:
        if not file_path:
            await update.message.reply_text("❌ Download failed. Link may be private or unsupported.")
            return
        
        # NOTE: Using 'with open' is crucial for resource management
        with open(file_path, "rb") as video_file:
            try:
                await update.message.reply_video(video=video_file, caption="Downloaded via VidXpress Bot")
            except Exception as e:
                logger.warning(f"Failed to send as video: {e}. Trying as document.")
                video_file.seek(0)
                await update.message.reply_document(document=video_file, filename=os.path.basename(file_path))

        await update.message.reply_text("✔ Download complete!")

    except Exception as e:
        logger.error(f"Error during file transfer: {e}")
        await update.message.reply_text("⚠️ An error occurred while sending the file to Telegram.")

    finally:
        # MANDATORY CLEANUP STEP: Delete the entire temporary directory and its contents
        if temp and os.path.exists(temp):
            try:
                shutil.rmtree(temp, ignore_errors=True)
                logger.info(f"Cleaned up temporary directory: {temp}")
            except Exception as e:
                logger.error(f"Failed to clean up temporary directory {temp}: {e}")

# --- FLASK ENDPOINTS ---

@app_flask.route('/')
def index():
    """Health Check Endpoint for Uptime Robot (GET /)"""
    return "VidXpress Bot is Running.", HTTPStatus.OK

@app_flask.route(WEBHOOK_URL_PATH, methods=["POST"])
def telegram_webhook():
    """Telegram Webhook Endpoint (POST /<token>)"""
    if not request.json:
        return Response("Invalid data received", status=HTTPStatus.BAD_REQUEST)

    try:
        update = Update.de_json(data=request.json, bot=application.bot)
        
        # Define and run the async processing function synchronously
        async def process_update_async():
            await application.process_update(update)

        # Run the async function using asyncio.run()
        asyncio.run(process_update_async())
        
    except Exception as e:
        # Log the error, but still return 200 OK to Telegram to avoid repeated retries
        logger.error(f"Error processing update: {e}", exc_info=True)
        return Response("Update processed with error", status=HTTPStatus.OK) 
        
    return Response("OK", status=HTTPStatus.OK)

# --- MAIN EXECUTION ---

def main():
    # 1. Add Handlers (Sync Operation)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

    # 2. Define the async setup function for bot initialization
    async def setup_bot_async():
        # CRITICAL FIX: Application must be explicitly started when manually managing webhooks
        await application.start()
        
        # 3. Set the Webhook on Telegram (Async Operation)
        try:
            await application.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
            logger.info(f"Webhook successfully set to: {WEBHOOK_URL}")
        except Exception as e:
            logger.error(f"Failed to set webhook URL! Error: {e}")
            raise # Stop if webhook setup fails

    # Run the async setup function synchronously before starting the Flask server
    try:
        asyncio.run(setup_bot_async())
    except Exception as e:
        logger.critical(f"Bot setup failed. Cannot start server: {e}")
        return

    # 4. Start the Flask Server (Sync Operation)
    logger.info(f"Starting Flask server on port {PORT}...")
    # NOTE: app_flask.run() is synchronous and blocking
    app_flask.run(host='0.0.0.0', port=PORT)


if __name__ == "__main__":
    if not WEBHOOK_BASE_URL or WEBHOOK_BASE_URL == "https://your-app-name.example.com":
        logger.error("!!! CRITICAL ERROR: WEBHOOK_BASE_URL not set. Running in Polling Mode for testing. Please set WEBHOOK_BASE_URL to deploy.")
        # We can't use application.run_polling() here because the Flask server starts later.
        # This part is just for development/testing if the URL isn't set.
        # For deployment, ensure WEBHOOK_BASE_URL is properly configured.
        main() # We still run main, but rely on the error being caught if the URL is wrong.
    else:
        main()

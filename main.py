import os
import logging
import shutil
import json
from flask import Flask, request, Response # Flask is needed for robust Webhook and Health Check
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from http import HTTPStatus
from download_manager import download_media # Assuming this is available

# --- CONFIGURATION ---
# Using standard Render environment variables for better integration
TOKEN = os.environ.get("TELEGRAM_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
PORT = int(os.environ.get("PORT", "8080"))
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

# --- HANDLERS (Same as before) ---

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

    file_path, temp = download_media(url)

    try:
        if not file_path:
            await update.message.reply_text("❌ Download failed. Link may be private or unsupported.")
            return
        
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
        try:
            if os.path.exists(temp):
                shutil.rmtree(temp, ignore_errors=True)
                logger.info(f"Cleaned up temporary directory: {temp}")
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {temp}: {e}")

# --- FLASK ENDPOINTS ---

@app_flask.route('/')
def index():
    """Health Check Endpoint for Uptime Robot (GET /)"""
    # This will return 200 OK and keep the Render service awake.
    return "VidXpress Bot is Running.", HTTPStatus.OK

@app_flask.route(WEBHOOK_URL_PATH, methods=["POST"])
async def telegram_webhook():
    """Telegram Webhook Endpoint (POST /<token>)"""
    # Check if the request body is valid JSON
    if not request.json:
        return Response("Invalid data received", status=HTTPStatus.BAD_REQUEST)

    # Use the application's update handler
    try:
        update = Update.de_json(data=request.json, bot=application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        # Return 200 OK even if processing fails to prevent Telegram from retrying
        return Response("Update processed with error", status=HTTPStatus.OK) 
        
    return Response("OK", status=HTTPStatus.OK)

# --- MAIN EXECUTION ---

def main():
    # 1. Add Handlers to the Telegram Application
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

    # 2. Set the Webhook on Telegram (runs only once at startup)
    try:
        # Note: We must run this synchronously before the Flask app starts
        application.bot.set_webhook(url=WEBHOOK_URL, allowed_updates=Update.ALL_TYPES)
        logger.info(f"Webhook successfully set to: {WEBHOOK_URL}")
    except Exception as e:
        logger.error(f"Failed to set webhook URL! Error: {e}")
        return # Stop if webhook setup fails

    # 3. Start the Flask Server
    logger.info(f"Starting Flask server on port {PORT}...")
    # Use '0.0.0.0' for Render/cloud platforms
    app_flask.run(host='0.0.0.0', port=PORT)


if __name__ == "__main__":
    if not WEBHOOK_BASE_URL or WEBHOOK_BASE_URL == "https://your-app-name.example.com":
        logger.error("!!! CRITICAL ERROR: WEBHOOK_BASE_URL not set. Running in Polling Mode for testing.")
        # Fallback to simple polling (You MUST set WEBHOOK_BASE_URL on Render for production!)
        application.run_polling() 
    else:
        main()

import logging
import os
import shutil
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from http import HTTPStatus # For checking HTTP response status

# Assuming the file is named 'download_manager.py'
from download_manager import download_media

# --- CONFIGURATION ---
# The environment variables are CRUCIAL for webhook deployment
TOKEN = os.environ.get("BOT_TOKEN", "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY")
PORT = int(os.environ.get("PORT", "8080"))
# The URL must be your public web address (e.g., https://your-app-name.onrender.com)
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "https://your-app-name.example.com") 
# --- END CONFIGURATION ---

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and explains the bot's function."""
    await update.message.reply_text(
        "Hello! Send any video link — Instagram, YouTube, TikTok, Facebook, X, Threads, Moj, Chingari etc."
    )


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the download request, sends the file, and cleans up."""
    url = update.message.text.strip()

    # Reply immediately to show the bot is active, as downloads can take time
    await update.message.reply_text("⏳ Downloading… Please wait.")

    # file_path is the downloaded file, temp is the temp directory path
    file_path, temp = download_media(url)

    # --- File Sending and Cleanup Block ---
    try:
        if not file_path:
            # Handle download failure
            await update.message.reply_text("❌ Download failed. Link may be private or unsupported (e.g., age-restricted YouTube videos).")
            return
        
        # 1. Send file logic
        # Open file in binary read mode
        with open(file_path, "rb") as video_file:
            try:
                # Try sending as video first
                await update.message.reply_video(video=video_file, caption="Downloaded via Bot")
            except Exception as e:
                # If reply_video fails (e.g., file is too large or not a proper video format),
                # try sending as a document and log the video failure
                logger.warning(f"Failed to send as video: {e}. Trying as document.")
                video_file.seek(0) # Rewind the file pointer for the document send
                # Use os.path.basename for a clean filename
                await update.message.reply_document(document=video_file, filename=os.path.basename(file_path))

        await update.message.reply_text("✔ Download complete!")

    except Exception as e:
        # Catch any final errors during file transfer or Telegram API call
        logger.error(f"Error during file transfer: {e}")
        await update.message.reply_text("⚠️ An error occurred while sending the file to Telegram.")

    finally:
        # 2. MANDATORY CLEANUP STEP: Delete the entire temporary directory and its contents
        try:
            if os.path.exists(temp):
                shutil.rmtree(temp, ignore_errors=True)
                logger.info(f"Cleaned up temporary directory: {temp}")
        except Exception as e:
            logger.error(f"Failed to clean up temporary directory {temp}: {e}")
    # --- End of Cleanup Block ---


def main():
    """Starts the bot using webhooks."""
    if WEBHOOK_URL == "https://your-app-name.example.com":
        logger.error("!!! CRITICAL ERROR: Please set the WEBHOOK_URL environment variable to your deployment URL !!!")
        logger.error("Falling back to local polling for testing...")
        
        # Fallback to polling for local testing if WEBHOOK_URL is not set
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))
        app.run_polling(poll_interval=1.0)
        return

    # 1. Build the Application
    app = ApplicationBuilder().token(TOKEN).build()

    # 2. Add Handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

    # 3. Configure and Run Webhook
    logger.info(f"Starting webhook listener on port {PORT}...")
    
    # Run the bot using the webhook method
    # Note: Telegram requires a secure (HTTPS) URL for webhooks
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path=TOKEN, # Use the token as a secret path segment
        webhook_url=f"{WEBHOOK_URL}/{TOKEN}"
    )


if __name__ == "__main__":
    main()

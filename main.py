import logging
import os
import shutil # 1. Import shutil for directory removal
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters

# Assuming you have renamed 'downloadmanager (1).py' to 'download_manager.py'
from download_manager import download_media

TOKEN = "7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY" # NOTE: Using a placeholder token

# Set up logging for better error visibility
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user and explains the bot's function."""
    await update.message.reply_text(
        "Hello! Send any video link — Instagram, YouTube, TikTok, Facebook, X, Threads, Moj, Chingari etc."
    )


async def downloader(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the download request, sends the file, and cleans up."""
    url = update.message.text.strip()

    await update.message.reply_text("⏳ Downloading… Please wait.")

    # file_path is the downloaded file, temp is the temp directory path
    file_path, temp = download_media(url)

    # If the download failed, clean up the temp directory (if one was created)
    if not file_path:
        # Check if a temporary directory path was successfully returned
        if temp and os.path.exists(temp):
            shutil.rmtree(temp, ignore_errors=True)
        await update.message.reply_text("❌ Download failed. Link may be private or unsupported (e.g., age-restricted YouTube videos).")
        return

    # --- File Sending and Cleanup Block ---
    try:
        # 1. Send file logic
        # Open file in binary read mode
        with open(file_path, "rb") as video_file:
            try:
                # Try sending as video first
                await update.message.reply_video(video=video_file, caption="Downloaded via Bot")
            except Exception as e:
                # If reply_video fails (e.g., file is too large or not a proper video format),
                # try sending as a document and log the video failure
                logging.warning(f"Failed to send as video: {e}. Trying as document.")
                video_file.seek(0) # Rewind the file pointer for the document send
                await update.message.reply_document(document=video_file, filename=os.path.basename(file_path))

        await update.message.reply_text("✔ Download complete!")

    except Exception as e:
        # Catch any final errors during file transfer or Telegram API call
        logging.error(f"Error during file transfer: {e}")
        await update.message.reply_text("⚠️ An error occurred while sending the file to Telegram.")

    finally:
        # 2. MANDATORY CLEANUP STEP: Delete the entire temporary directory and its contents
        try:
            if os.path.exists(temp):
                shutil.rmtree(temp, ignore_errors=True)
                logging.info(f"Cleaned up temporary directory: {temp}")
        except Exception as e:
            logging.error(f"Failed to clean up temporary directory {temp}: {e}")
    # --- End of Cleanup Block ---


def main():
    """Starts the bot."""
    # NOTE: In a production environment, it is better practice to load the token
    # from an environment variable (e.g., os.environ.get("TELEGRAM_TOKEN")).
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, downloader))

    # Use run_polling for development or run_webhook for cloud deployment
    logging.info("Starting bot polling...")
    app.run_polling(poll_interval=1.0)


if __name__ == "__main__":
    main()


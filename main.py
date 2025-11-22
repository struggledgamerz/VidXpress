import os
import tempfile
import logging
import shutil # Added for explicit cleanup
from typing import Dict, Any, Union

from fastapi import FastAPI, Request, HTTPException
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode
import yt_dlp

# --- Configuration ---
# Set the port Uvicorn/FastAPI will listen on (Render default is 10000)
PORT = int(os.environ.get('PORT', 10000)) 
# Your Bot Token goes here
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY') # Replace with your actual token in the deployment environment

# Public URL of the deployed service (e.g., https://your-service-name.onrender.com)
WEBHOOK_URL = os.environ.get('WEBHOOK_BASE_URL', 'https://ff-like-bot-px1w.onrender.com') 

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Maximum file size for Telegram bot API upload in bytes (50 MB limit applied to avoid timeouts)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 

class DownloadManager:
    """Manages yt-dlp download operations with custom settings."""
    def __init__(self):
        self.logger = logging.getLogger('DownloadManager')

    def download(self, url: str) -> Dict[str, Union[str, bool]]:
        """
        Attempts to download the video from the given URL.
        Returns a dict containing the status and resulting file path or error message.
        """
        temp_dir = tempfile.mkdtemp()
        download_info = {
            'success': False,
            'file_path': None,
            'error': None,
            'temp_dir': temp_dir
        }
        
        # Use a short template based on the video ID within the temp directory.
        output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')

        # yt-dlp options (Attempt 1: Simple MP4 priority)
        ydl_opts = {
            'outtmpl': output_template,
            # Filter by max file size to prevent timeouts on large uploads.
            'max_filesize': MAX_FILE_SIZE_BYTES, 
            # --- TWEAK FOR YOUTUBE/SHORTS ---
            # Prioritize best MP4 format (which Telegram wants), then best overall. 
            'format': 'best[ext=mp4]/best', 
            # ---------------------------------
            'noplaylist': True,
            'quiet': True,
            'verbose': False,
            'noprogress': True,
            'logger': self.logger,
            'allow_unplayable_formats': True,
            # Workaround for missing JavaScript runtime (needed for YouTube)
            'extractor_args': {'youtube': {'player_client': 'default'}},
        }

        self.logger.info(f"Created temporary directory: {temp_dir}")
        self.logger.info("Attempt 1: Trying simple MP4 format priority.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                # Find the actual downloaded file path
                downloaded_files = []
                if 'requested_downloads' in info_dict:
                    downloaded_files = [f['filepath'] for f in info_dict['requested_downloads'] if os.path.exists(f['filepath'])]
                
                # Secondary check for files written directly to temp_dir
                if not downloaded_files and os.listdir(temp_dir):
                    for filename in os.listdir(temp_dir):
                        if filename.startswith(info_dict.get('id', '')):
                            downloaded_files.append(os.path.join(temp_dir, filename))
                            
                if downloaded_files:
                    download_info['file_path'] = downloaded_files[0]
                    download_info['success'] = True
                    self.logger.info(f"Attempt 1 successful. Downloaded file: {download_info['file_path']}")
                    return download_info


        except Exception as e:
            error_message = str(e)
            self.logger.warning(f"Attempt 1 failed. Reason: {error_message}")
            download_info['error'] = error_message
            
            # --- Attempt 2: Fallback (Absolute best quality/format) ---
            self.logger.info("Attempt 2: Falling back to absolute best quality/format.")
            ydl_opts.pop('format', None) # Remove explicit format filter
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    downloaded_files = []
                    if 'requested_downloads' in info_dict:
                        downloaded_files = [f['filepath'] for f in info_dict['requested_downloads'] if os.path.exists(f['filepath'])]
                    
                    if not downloaded_files and os.listdir(temp_dir):
                        for filename in os.listdir(temp_dir):
                            if filename.startswith(info_dict.get('id', '')):
                                downloaded_files.append(os.path.join(temp_dir, filename))
                                
                    if downloaded_files:
                        download_info['file_path'] = downloaded_files[0]
                        download_info['success'] = True
                        self.logger.info(f"Attempt 2 successful. Downloaded file: {download_info['file_path']}")
                        return download_info
                                
            except Exception as e:
                final_error = str(e)
                self.logger.error(f"Attempt 2 failed. Final failure reason: {final_error}")
                download_info['error'] = final_error
                return download_info

        return download_info


class TelegramBot:
    """The main Telegram Bot logic and handlers."""
    def __init__(self, token: str):
        self.download_manager = DownloadManager()
        self.app = ApplicationBuilder().token(token).build()
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        self.logger = logging.getLogger('TelegramBot')

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a welcome message on /start."""
        await update.message.reply_text('Hello! Send me a link to a video from Facebook, YouTube, or other supported sites, and I will try to download and send it to you. \n\n⚠️ **Note:** Videos over 50MB may fail due to upload size/time limits.', 
                                        parse_mode=ParseMode.MARKDOWN)

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles text messages containing a URL."""
        url = update.message.text
        
        # 1. Send initial processing message
        processing_message = await update.message.reply_text("⏳ Processing link and checking size...", parse_mode=ParseMode.HTML)

        # 2. Start download
        download_result = {'temp_dir': None}
        try:
            download_result = self.download_manager.download(url)
            temp_dir = download_result['temp_dir']
            
            # 3. Handle download failure
            if not download_result['success']:
                error = download_result['error']
                # Provide a more specific error message for common YouTube issues
                youtube_hint = ""
                if "Sign in to confirm" in error or "JavaScript runtime" in error:
                    youtube_hint = "\n\n**Possible Cause:** The video requires sign-in (age restriction/private) or the server lacks a JavaScript engine needed to process complex YouTube formats."
                
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id, 
                    message_id=processing_message.message_id,
                    text=f"❌ Download Failed!\n\nReason: The video is likely private, age-restricted, or too large (>{MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB).{youtube_hint}\n\nDetails: `{error}`", 
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            # 4. Handle successful download
            file_path = download_result['file_path']
            self.logger.info(f"Successfully downloaded file: {file_path}")
            
            # 4a. Delete the initial processing message
            await processing_message.delete()
            
            # 4b. Send the file using a callback to clean up the temp directory
            await update.message.reply_video(
                video=open(file_path, 'rb'),
                caption=f"✅ Downloaded successfully!",
                supports_streaming=True,
                read_timeout=60, # Increase timeout for large uploads
                write_timeout=60
            )

        except Exception as e:
            self.logger.error(f"Failed to send file or encountered error in send_media_callback: {e}")
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id, 
                message_id=processing_message.message_id,
                text=f"❌ An unexpected error occurred during upload: `{e}`. This usually means the file was too large and the connection timed out.",
                parse_mode=ParseMode.MARKDOWN
            )

        finally:
            # 5. Cleanup temporary directory
            if 'temp_dir' in download_result and download_result['temp_dir'] and os.path.exists(download_result['temp_dir']):
                try:
                    shutil.rmtree(download_result['temp_dir'])
                    self.logger.info(f"Cleaned up temporary directory: {download_result['temp_dir']}")
                except OSError as e:
                    self.logger.error(f"Error cleaning up temporary directory {download_result['temp_dir']}: {e}")

# --- FastAPI Setup for Webhook ---

app = FastAPI()
bot = TelegramBot(token=BOT_TOKEN)
application = bot.app 

@app.on_event("startup")
async def startup_event():
    """Set the webhook on startup."""
    if WEBHOOK_URL and BOT_TOKEN != 'YOUR_BOT_TOKEN':
        # The URL must point to the /webhook endpoint
        webhook_url = f"{WEBHOOK_URL}/webhook"
        logger.info(f"Setting webhook to {webhook_url}")
        # Use the base PTB Application object to set the webhook
        await application.bot.set_webhook(url=webhook_url)
    else:
        logger.error("BOT_TOKEN or WEBHOOK_URL not configured. Cannot set webhook.")


@app.post("/webhook")
async def webhook(request: Request):
    """Handle incoming Telegram updates."""
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        
        # Process the update using the PTB application
        await application.process_update(update)
        
        return {"message": "OK"}
    except Exception as e:
        logger.error(f"Error processing webhook update: {e}")
        # Return 200 OK even on error to prevent Telegram from retrying endlessly
        return {"message": "Error"}


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting FastAPI on port {PORT}")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)

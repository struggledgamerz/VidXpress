import os
import tempfile
import logging
import shutil
from typing import Dict, Any, Union

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CommandHandler
)
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

# --- Static Privacy Policy Content (for the web endpoint) ---
PRIVACY_POLICY_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>VidXpress⚡ - Privacy Policy</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f4f4f9;
            color: #333;
        }
        .container {
            max-width: 700px;
            margin: 0 auto;
            background: #fff;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
        }
        h1 {
            color: #007bff;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
            margin-top: 0;
        }
        h2 {
            color: #555;
            margin-top: 25px;
        }
        p, ul {
            line-height: 1.6;
        }
        ul {
            list-style-type: disc;
            padding-left: 20px;
        }
        code {
            background-color: #eee;
            padding: 2px 4px;
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Video Downloader Bot - Privacy Policy</h1>
        <p>This bot is designed solely to download and relay publicly accessible video content from external platforms (e.g., YouTube, Facebook).</p>

        <h2>1. Data Collection and Processing</h2>
        <ul>
            <li><strong>Input Data:</strong> The bot only processes the URL link you send in your message to identify and locate the video source.</li>
            <li><strong>Personal Data:</strong> We do not collect, store, or share any personal identifying information (like your Telegram User ID or chat history) beyond what is required to fulfill the request.</li>
        </ul>

        <h2>2. Content Storage and Deletion</h2>
        <ul>
            <li><strong>Temporary Files:</strong> Requested videos are downloaded to a temporary location on the host server.</li>
            <li><strong>No Persistence:</strong> These files are immediately and permanently deleted using the <code>shutil.rmtree()</code> function after they are successfully uploaded to Telegram or if the download/upload process fails. No logs or files related to your requests are retained after the transaction is complete.</li>
        </ul>

        <h2>3. Third Parties</h2>
        <p>Video processing relies on the <code>yt-dlp</code> tool to handle video extraction and format detection, and the standard Telegram Bot API for message handling and file uploads.</p>
        
        <p style="margin-top: 30px; font-size: 0.9em; color: #777;">Last Updated: November 2025</p>
    </div>
</body>
</html>
"""

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
            # Prioritize best MP4 format (which Telegram wants), then best overall. 
            'format': 'best[ext=mp4]/best', 
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
        
        # Handlers: Only start and message handler 
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        self.logger = logging.getLogger('TelegramBot')

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a welcome message on /start."""
        policy_url = f"{WEBHOOK_URL}/privacy"
        await update.message.reply_text(f'Hello! Send me a link to a video from Facebook, YouTube, or other supported sites, and I will try to download and send it to you. \n\n⚠️ **Note:** Videos over 50MB may fail due to upload size/time limits. The official [Privacy Policy]({policy_url}) is available here.', 
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
            
            # 4b. Send the file 
            await update.message.reply_video(
                video=open(file_path, 'rb'),
                caption=f"✅ Downloaded successfully!",
                supports_streaming=True,
                read_timeout=60, 
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

# NEW PUBLIC WEB ENDPOINT FOR PRIVACY POLICY
@app.get("/privacy", response_class=HTMLResponse)
async def get_privacy_policy():
    """Serves the privacy policy as a public HTML page."""
    return PRIVACY_POLICY_HTML


@app.on_event("startup")
async def startup_event():
    """Initialize PTB application and set the webhook on startup."""
    if WEBHOOK_URL and BOT_TOKEN != 'YOUR_BOT_TOKEN':
        # FIX: Explicitly initialize and start the PTB application for webhook readiness
        await application.initialize()
        
        # Set the webhook
        webhook_url = f"{WEBHOOK_URL}/webhook"
        logger.info(f"Setting webhook to {webhook_url}")
        await application.bot.set_webhook(url=webhook_url)

        # Start the application instance (required for process_update to work)
        await application.start()
    else:
        logger.error("BOT_TOKEN or WEBHOOK_URL not configured. Cannot set webhook.")


@app.on_event("shutdown")
async def shutdown_event():
    """Stop the PTB application on shutdown."""
    if WEBHOOK_URL and BOT_TOKEN != 'YOUR_BOT_TOKEN':
        # Cleanly stop the application on service shutdown
        await application.stop()


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

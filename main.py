import os
import tempfile
import logging
import shutil
import asyncio 
import time
from typing import Dict, Any, Union
from contextlib import asynccontextmanager

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
# Set the port Uvicorn/FastAPI will listen on 
PORT = int(os.environ.get('PORT', 5000)) 
# Your Bot Token goes here
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')

# Public URL of the deployed service (e.g., https://ff-like-bot-px1w.onrender.com)
# THIS MUST BE SET IN RENDER ENVIRONMENT VARIABLES
WEBHOOK_URL = os.environ.get('WEBHOOK_BASE_URL', '') 
# Environment variable to hold Netscape format cookies content for yt-dlp authentication
YOUTUBE_COOKIES = os.environ.get('YOUTUBE_COOKIES', '')

# Define the path for the webhook and privacy policy URL. 
WEBHOOK_PATH = f"/{BOT_TOKEN}" if BOT_TOKEN else "/webhook"
PRIVACY_POLICY_PATH = "/privacy"

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Maximum file size for Telegram bot API upload in bytes (50 MB limit)
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 

# --- Global Telegram Application Object ---
application = None # Initialize globally

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
        <h1>VidXpress⚡ - Privacy Policy</h1>
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
        NOTE: This is a SYNCHRONOUS function and MUST be run in a thread (via asyncio.to_thread).
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
            'max_filesize': MAX_FILE_SIZE_BYTES, 
            'format': 'best[ext=mp4]/best', 
            'noplaylist': True,
            'quiet': True,
            'verbose': False,
            'noprogress': True,
            'logger': self.logger,
            'allow_unplayable_formats': True,
            'extractor_args': ['youtube:player_client=default']
        }

        # --- Add cookie support for restricted videos ---
        if YOUTUBE_COOKIES:
            try:
                cookie_file_path = os.path.join(temp_dir, 'cookies.txt')
                # IMPORTANT: Write the cookies content to the temporary file
                with open(cookie_file_path, 'w', encoding='utf-8') as f:
                    f.write(YOUTUBE_COOKIES)
                ydl_opts['cookiefile'] = cookie_file_path
                self.logger.info("Authentication (cookies) enabled for yt-dlp and loaded into temp file.")
            except Exception as e:
                self.logger.error(f"Error creating cookie file: {e}")
                
        self.logger.info(f"Created temporary directory: {temp_dir}")
        self.logger.info("Attempt 1: Trying simple MP4 format priority.")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                
                # --- CRITICAL FIX: Handle list (playlist) output ---
                if isinstance(info_dict, list):
                    # We expect only one item since 'noplaylist' is True. 
                    if info_dict:
                        info_dict = info_dict[0]
                    else:
                        # Handles the specific error 'list' object has no attribute 'get' 
                        # if the list was unexpectedly empty.
                        raise ValueError("yt-dlp returned an empty list, likely no videos found.")
                # --- CRITICAL FIX END ---

                downloaded_files = []
                # Check for the downloaded file path in the expected locations
                if 'requested_downloads' in info_dict and isinstance(info_dict['requested_downloads'], list):
                    downloaded_files = [f['filepath'] for f in info_dict['requested_downloads'] if os.path.exists(f['filepath'])]
                
                # Fallback check on the temp directory for the file using its ID
                if not downloaded_files and os.listdir(temp_dir):
                    video_id = info_dict.get('id', '')
                    for filename in os.listdir(temp_dir):
                        if filename.startswith(video_id):
                            downloaded_files.append(os.path.join(temp_dir, filename))
                            
                if downloaded_files:
                    download_info['file_path'] = downloaded_files[0]
                    download_info['success'] = True
                    self.logger.info(f"Attempt 1 successful. Downloaded file: {download_info['file_path']}")
                    return download_info
                
                # If we reached here, download was successful but file path couldn't be located.
                download_info['error'] = "Download successful, but file path could not be located in temporary directory."
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
                    
                    # --- CRITICAL FIX: Handle list (playlist) output ---
                    if isinstance(info_dict, list):
                        if info_dict:
                            info_dict = info_dict[0]
                        else:
                            raise ValueError("yt-dlp returned an empty list, likely no videos found.")
                    # --- CRITICAL FIX END ---

                    downloaded_files = []
                    # Check for the downloaded file path in the expected locations
                    if 'requested_downloads' in info_dict and isinstance(info_dict['requested_downloads'], list):
                        downloaded_files = [f['filepath'] for f in info_dict['requested_downloads'] if os.path.exists(f['filepath'])]
                    
                    # Fallback check on the temp directory for the file using its ID
                    if not downloaded_files and os.listdir(temp_dir):
                        video_id = info_dict.get('id', '')
                        for filename in os.listdir(temp_dir):
                            if filename.startswith(video_id):
                                downloaded_files.append(os.path.join(temp_dir, filename))
                                
                    if downloaded_files:
                        download_info['file_path'] = downloaded_files[0]
                        download_info['success'] = True
                        self.logger.info(f"Attempt 2 successful. Downloaded file: {download_info['file_path']}")
                        return download_info

                    # If we reached here, download was successful but file path could not be located.
                    download_info['error'] = "Download successful, but file path could not be located in temporary directory (Attempt 2)."
                    return download_info
                                
            except Exception as e:
                final_error = str(e)
                self.logger.error(f"Attempt 2 failed. Final failure reason: {final_error}")
                download_info['error'] = final_error
                return download_info

        # Catch-all return
        return download_info


class TelegramBot:
    """The main Telegram Bot logic and handlers."""
    def __init__(self, token: str):
        self.download_manager = DownloadManager()
        self.app = ApplicationBuilder().token(token).build()
        
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        self.logger = logging.getLogger('TelegramBot')

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Sends a welcome message on /start."""
        policy_url = f"{WEBHOOK_URL}{PRIVACY_POLICY_PATH}"
        cookie_status = "✅ On (Cookies Loaded)" if YOUTUBE_COOKIES else "❌ Off (Set YOUTUBE_COOKIES variable)"
        
        await update.message.reply_text(
            f'Hello! Send me a link to a video from Facebook, YouTube, or other supported sites, and I will try to download and send it to you. \n\n'
            f'🍪 **Authentication Status:** {cookie_status}. (Agar aapne cookies add ki hain, toh age-restricted videos bhi download ho sakti hain.)\n\n'
            f'⚠️ **Note:** Videos over 50MB may fail due to upload size/time limits. The official [Privacy Policy]({policy_url}) is available here.', 
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handles text messages containing a URL."""
        url = update.message.text
        
        # 1. Send initial processing message
        processing_message = await update.message.reply_text("⏳ Processing link and checking size...", parse_mode=ParseMode.HTML)

        # 2. Start download
        download_result = {'temp_dir': None}
        try:
            # Running blocking I/O in a separate thread
            download_result = await asyncio.to_thread(self.download_manager.download, url)
            temp_dir = download_result['temp_dir']
            
            # 3. Handle download failure
            if not download_result['success']:
                error = download_result['error']
                # Provide a more specific error message for common YouTube issues
                youtube_hint = ""
                if "Sign in to confirm" in error or "cookies" in error:
                    cookie_fix = "Kripya apne deployment settings mein `YOUTUBE_COOKIES` environment variable set karein ya check karein ki woh expire toh nahi ho gayi." if not YOUTUBE_COOKIES else "Aapki cookies shayad expired ya invalid hain. Nayi cookies generate karke daaliye."
                    youtube_hint = f"\n\n**🛑 UNABLE TO ACCESS (SIGN-IN REQUIRED):** Yeh video age-restricted, private, ya authentication (cookies) maang raha hai. {cookie_fix}"
                elif "JavaScript runtime" in error or "No supported JavaScript runtime could be found" in error:
                    youtube_hint = "\n\n**Possible Cause:** The video extraction failed due to complexity (This warning should be fixed in the new code)."
                elif "no attribute 'get'" in error:
                    # Specific error handling for the 'list' object error
                    youtube_hint = "\n\n**🛑 Processing Error:** Bot ko URL process karne mein internal error aaya (shayad yeh koi playlist ya non-video content hai)."

                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id, 
                    message_id=processing_message.message_id,
                    text=f"❌ Download Failed!\n\nReason: The video is likely too large (>{MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB) or protected.{youtube_hint}\n\nDetails: `{error}`", 
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            # 4. Handle successful download
            file_path = download_result['file_path']
            self.logger.info(f"Successfully downloaded file: {file_path}")
            
            # 4a. Delete the initial processing message
            await processing_message.delete()
            
            # 4b. Send the file 
            if not os.path.exists(file_path):
                 raise FileNotFoundError(f"Downloaded file not found at path: {file_path}")

            # Send the video file
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

# --- FastAPI Lifespan Manager ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes and shuts down the Telegram Bot Application."""
    global application

    if BOT_TOKEN and WEBHOOK_URL:
        # --- Startup ---
        logger.info("Starting up Telegram Application...")
        
        # Log cookie status on startup for confirmation
        cookie_status_log = "ENABLED (Content Found)" if YOUTUBE_COOKIES else "DISABLED (No YOUTUBE_COOKIES variable found)"
        logger.info(f"Cookie Status Check: {cookie_status_log}")
        
        bot_instance = TelegramBot(token=BOT_TOKEN)
        application = bot_instance.app
        
        # 1. Initialize the application (fixes the "not initialized" error)
        await application.initialize() 
        
        # 2. Start the application
        await application.start()
        
        # 3. Set the webhook (dropping pending updates ensures a clean start)
        full_webhook_url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
        try:
            # We wait for 1 second to ensure the app server is definitely ready 
            # before making the external API call, reducing the chance of internal timeouts.
            await asyncio.sleep(1) 
            await application.bot.set_webhook(url=full_webhook_url, drop_pending_updates=True)
            logger.info(f"✅ Webhook successfully set to: {full_webhook_url}")
        except Exception as e:
            logger.error(f"❌ FATAL ERROR: Failed to set Webhook. Check BOT_TOKEN and WEBHOOK_BASE_URL. Reason: {e}")

    else:
        logger.warning("Bot not fully configured - TELEGRAM_BOT_TOKEN and/or WEBHOOK_BASE_URL not set.") 
    
    # Yield control to the FastAPI server while the bot is running
    yield
    
    # --- Shutdown ---
    if application:
        logger.info("Shutting down Telegram Application...")
        await application.stop()
        logger.info("Application shut down successfully.")
    
# --- FastAPI App Initialization ---
app = FastAPI(lifespan=lifespan)


# WEBHOOK ENDPOINT
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    """Receives updates from Telegram via webhook."""
    # Check only if application is set (not None), since the 'started' attribute is invalid.
    if not application:
        logger.error("Webhook received but application object is None (not initialized).")
        # Return 200 OK so Telegram doesn't keep retrying, but log the error
        return {"status": "error", "message": "Bot not ready."}
        
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        
        # Process the update
        await application.process_update(update)
        
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing update: {e}")
        return {"status": "error", "message": str(e)}

# PUBLIC WEB ENDPOINTS
@app.get("/")
async def root():
    return {"status": "ok"}
  

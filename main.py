import os
import logging
import shutil
import json
import asyncio 
from flask import Flask, request, Response, escape 
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, ContextTypes, filters
from http import HTTPStatus
from download_manager import download_media 

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

# --- PRIVACY POLICY CONTENT (Embedded HTML) ---

PRIVACY_POLICY_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VidXpress Bot Privacy Policy</title>
    <style>
        body { font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; background-color: #f4f4f4; color: #333; }
        h1, h2 { color: #007bff; }
        .container { background-color: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
        th { background-color: #f8f8f8; }
        code { background-color: #eee; padding: 2px 4px; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Privacy Policy for VidXpress Bot</h1>
        <p>This Privacy Policy explains how we handle the information you provide while using our service.</p>

        <h2>1. Data Collection and Usage</h2>
        <p>We collect the following types of information, which are necessary for the bot's operation:</p>
        
        <table>
            <thead>
                <tr>
                    <th>Type of Data</th>
                    <th>Purpose</th>
                    <th>Storage Duration</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td><strong>Telegram User ID (UID)</strong></td>
                    <td>To identify you as a unique user.</td>
                    <td>Permanently (as long as you use the Bot)</td>
                </tr>
                <tr>
                    <td><strong>Chat ID</strong></td>
                    <td>To send media and replies back to the correct chat.</td>
                    <td>Permanently (as long as you use the Bot)</td>
                </tr>
                <tr>
                    <td><strong>User-Provided URLs</strong></td>
                    <td>To fetch and download the requested media.</td>
                    <td>Only during the processing of the request</td>
                </tr>
                <tr>
                    <td><strong>Temporary Media Files</strong></td>
                    <td>The downloaded video/photo is stored locally on the server.</td>
                    <td><strong>Immediately deleted</strong> after the media is sent to you.</td>
                </tr>
            </tbody>
        </table>

        <h2>2. Information Sharing and Disclosure</h2>
        <p>We do not share, sell, rent, or trade your personal information (User ID, Chat ID, or URLs) with third parties.</p>
        <p><strong>Third-Party Services:</strong> The Bot uses <code>yt-dlp</code> and related Python libraries to access the URLs you provide. These services are used only for the purpose of downloading the requested media.</p>

        <h2>3. Data Storage and Security</h2>
        <ul>
            <li>**Permanent Data:** Your User ID and Chat ID are handled securely by Telegram.</li>
            <li>**Temporary Data:** Downloaded media files are stored only in a temporary directory on the server and are <strong>deleted immediately</strong> upon successful transmission or failure. The server does not maintain any permanent logs of downloaded media or URLs.</li>
        </ul>

        <h2>4. Consent</h2>
        <p>By using the VidXpress Bot, you consent to this Privacy Policy.</p>

        <h2>5. Contact Information</h2>
        <p>If you have any questions about this Privacy Policy, please contact the bot developer.</p>
    </div>
</body>
</html>
"""

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
                # Use os.path.basename(file_path) for cleaner file name when sending
                await update.message.reply_video(video=video_file, caption="Downloaded via VidXpress Bot")
            except Exception as e:
                logger.warning(f"Failed to send as video: {e}. Trying as document.")
                video_file.seek(0)
                await update.message.reply_document(document=video_file, filename=os.path.basename(file_path), caption="Downloaded via VidXpress Bot (Sent as Document)")

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

@app_flask.route('/privacy')
def privacy_policy():
    """Endpoint to display the Bot's Privacy Policy."""
    # Serve the hardcoded HTML policy
    return Response(PRIVACY_POLICY_HTML, mimetype='text/html')


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
    app_flask.run(host='0.0.0.0', port=PORT)


if __name__ == "__main__":
    if not WEBHOOK_BASE_URL or WEBHOOK_BASE_URL == "https://your-app-name.example.com":
        logger.error("!!! CRITICAL ERROR: WEBHOOK_BASE_URL not set. Please set WEBHOOK_BASE_URL to deploy.")
        # If running locally without a webhook, you'd typically use run_polling().
        # For this deployment model, we assume webhook is necessary.
        main() 
    else:
        main()

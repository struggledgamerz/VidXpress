import os
import logging
import shutil
import asyncio
import json
from datetime import datetime
from typing import Dict, Any, Union
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, 
    MessageHandler, 
    filters, 
    ContextTypes, 
    CommandHandler,
    Application,
    CallbackQueryHandler
)
from telegram.constants import ParseMode

# Import local DownloadManager
from download_manager import DownloadManager 

# --- Configuration ---
PORT = int(os.environ.get('PORT', 5000)) 
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '7817163480:AAE4Z1dBE_LK9gTN75xOc5Q4Saq29RmhAvY')

# Public URL of the deployed service
WEBHOOK_URL = os.environ.get('WEBHOOK_BASE_URL', 'https://ff-like-bot-px1w.onrender.com') 
YOUTUBE_COOKIES = os.environ.get('YOUTUBE_COOKIES', '')

# --- NEW: Force Join Configuration ---
# Yahan apne channel ka Username (@channel) ya ID (-100...) dalein.
# Example: "@VidXpressOfficial"
FORCE_CHANNEL_ID = os.environ.get('FORCE_CHANNEL_ID', '') 

WEBHOOK_PATH = f"/{BOT_TOKEN}" if BOT_TOKEN else "/webhook"
PRIVACY_POLICY_PATH = "/privacy"
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024 

# --- Analytics Configuration ---
ANALYTICS_FILE = "analytics.json"
ADMIN_CHANNEL_ID = -1003479404949 

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Analytics Functions ---

def load_analytics():
    if not os.path.exists(ANALYTICS_FILE):
        return {"total_users": [], "total_requests": 0, "daily_usage": {}, "logs": []}
    try:
        with open(ANALYTICS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {"total_users": [], "total_requests": 0, "daily_usage": {}, "logs": []}

def save_analytics(data):
    try:
        with open(ANALYTICS_FILE, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save analytics: {e}")

async def update_analytics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Updates analytics data and sends log to admin channel."""
    if not update.effective_user:
        return

    user_id = update.effective_user.id
    text = "Action"
    if update.message and update.message.text:
        text = update.message.text
    elif update.callback_query:
        text = f"Button: {update.callback_query.data}"
    
    username = update.effective_user.username or "Unknown"

    # 1. Update Local JSON
    data = load_analytics()

    if user_id not in data["total_users"]:
        data["total_users"].append(user_id)

    data["total_requests"] += 1
    today = datetime.now().strftime("%Y-%m-%d")
    data["daily_usage"][today] = data["daily_usage"].get(today, 0) + 1

    log_entry = {
        "user": user_id,
        "username": username,
        "text": text,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    data["logs"].append(log_entry)
    data["logs"] = data["logs"][-50:] 
    
    save_analytics(data)

    # 2. Send Log to Admin Channel
    if ADMIN_CHANNEL_ID:
        try:
            log_message = (
                f"📊 <b>New Activity</b>\n"
                f"👤 <b>User:</b> <a href='tg://user?id={user_id}'>{username}</a> (`{user_id}`)\n"
                f"💬 <b>Action:</b> {text}"
            )
            await context.bot.send_message(
                chat_id=ADMIN_CHANNEL_ID,
                text=log_message,
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.warning(f"Admin log failed: {e}")

# --- Helper: Force Join Check ---

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Checks if the user is a member of the forced channel.
    Returns True if member (or if force join is disabled), False otherwise.
    """
    # Agar FORCE_CHANNEL_ID set nahi hai, toh check skip karo
    if not FORCE_CHANNEL_ID:
        return True
        
    user_id = update.effective_user.id
    
    try:
        member = await context.bot.get_chat_member(chat_id=FORCE_CHANNEL_ID, user_id=user_id)
        # 'left' means user has left, 'kicked' means banned. 
        # 'creator', 'administrator', 'member', 'restricted' are allowed.
        if member.status in ['left', 'kicked']:
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking membership for {FORCE_CHANNEL_ID}: {e}")
        # Agar bot admin nahi hai ya channel galat hai, toh hum user ko block nahi karenge
        # taaki bot chalta rahe.
        return True

async def send_force_join_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a message asking the user to join the channel."""
    # Channel link generate karein
    channel_url = f"https://t.me/{FORCE_CHANNEL_ID.replace('@', '')}"
    
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", url=channel_url)],
        [InlineKeyboardButton("✅ I Have Joined", callback_data="check_subscription")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    msg_text = (
        "👋 **Welcome!**\n\n"
        "To use this bot, you must join our official updates channel first.\n\n"
        "Please join and then click 'I Have Joined'."
    )
    
    if update.message:
        await update.message.reply_text(msg_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    elif update.callback_query:
        # Agar button click se aaya hai (re-check)
        await update.callback_query.edit_message_text(msg_text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)

# --- Static Content ---
PRIVACY_POLICY_HTML = """<!DOCTYPE html><html><body><h1>Privacy Policy</h1><p>Data is deleted immediately after processing.</p></body></html>"""

# --- Telegram Bot Logic ---

class TelegramBot:
    def __init__(self, token: str, max_file_size: int):
        self.download_manager = DownloadManager(max_file_size)
        self.app = ApplicationBuilder().token(token).build()
        
        # Handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CallbackQueryHandler(self.handle_callback)) # For "I Have Joined" button
        self.app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), self.handle_message))
        
        self.logger = logging.getLogger('TelegramBot')
        self.max_file_size = max_file_size

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # 1. Check Subscription First
        if not await check_membership(update, context):
            await send_force_join_message(update, context)
            return

        await update_analytics(update, context)
        policy_url = f"{WEBHOOK_URL}{PRIVACY_POLICY_PATH}"
        cookie_status = "✅ On" if YOUTUBE_COOKIES else "❌ Off"
        
        await update.message.reply_text(
            f'👋 **Welcome to VidXpress!**\n\n'
            f'Send me any video link from YouTube, Instagram, Facebook, etc.\n\n'
            f'⚠️ **Limit:** 50MB per video.\n'
            f'[Privacy Policy]({policy_url})', 
            parse_mode=ParseMode.MARKDOWN
        )

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        
        if query.data == "check_subscription":
            if await check_membership(update, context):
                await query.edit_message_text("✅ **Thanks for joining!**\n\nNow you can send me any video link to download.", parse_mode=ParseMode.MARKDOWN)
            else:
                await query.answer("❌ You haven't joined yet!", show_alert=True)
                # Message wahi rahega, bas alert dikhayega

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # 1. Check Subscription First
        if not await check_membership(update, context):
            await send_force_join_message(update, context)
            return

        await update_analytics(update, context)
        
        url = update.message.text
        if not url: return
        
        # 2. Guardrail for YouTube (Optional - uncomment if needed)
        # if "youtube.com" in url or "youtu.be" in url:
        #     await update.message.reply_text("❌ YouTube downloads are currently disabled.")
        #     return

        processing_message = await update.message.reply_text("⏳ Processing link...", parse_mode=ParseMode.HTML)

        try:
            # Run blocking I/O in a separate thread
            download_result = await asyncio.to_thread(self.download_manager.download, url)
            temp_dir = download_result.get('temp_dir')
            
            if not download_result['success']:
                error = download_result['error']
                hint = ""
                if "Sign in" in str(error): hint = "\n🛑 Login required (Cookies invalid)."
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id, 
                    message_id=processing_message.message_id,
                    text=f"❌ Failed: {error}{hint}"
                )
                return

            file_path = download_result['file_path']
            await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_message.message_id)
            
            if file_path and os.path.exists(file_path):
                await update.message.reply_video(
                    video=open(file_path, 'rb'),
                    caption="✅ Downloaded via VidXpress",
                    read_timeout=60, 
                    write_timeout=60
                )
            else:
                await update.message.reply_text("❌ File missing after download.")

        except Exception as e:
            self.logger.error(f"Error: {e}")
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id, 
                    message_id=processing_message.message_id,
                    text="❌ Error occurred during processing."
                )
            except: pass
        finally:
            if 'temp_dir' in locals() and temp_dir and os.path.exists(temp_dir):
                try: shutil.rmtree(temp_dir)
                except: pass

# --- FastAPI & Lifespan ---

application = None 

@asynccontextmanager
async def lifespan(app: FastAPI):
    global application
    if BOT_TOKEN:
        logger.info("Initializing Bot...")
        bot_instance = TelegramBot(token=BOT_TOKEN, max_file_size=MAX_FILE_SIZE_BYTES)
        application = bot_instance.app
        await application.initialize()
        await application.start()
        
        if WEBHOOK_URL:
            url = f"{WEBHOOK_URL}{WEBHOOK_PATH}"
            logger.info(f"Setting webhook: {url}")
            try:
                await application.bot.set_webhook(url=url, drop_pending_updates=True)
            except Exception as e:
                logger.error(f"Webhook Set Failed: {e}")
    
    yield
    
    if application:
        await application.stop()

app = FastAPI(lifespan=lifespan)

@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    if not application:
        return {"status": "error", "message": "Bot not initialized"}
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error"}

@app.get("/")
async def root():
    return {"status": "active", "mode": "WEBHOOK"}

@app.get(PRIVACY_POLICY_PATH)
async def privacy():
    return HTMLResponse(content=PRIVACY_POLICY_HTML)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT)

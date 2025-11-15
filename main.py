import logging
import os
import asyncio
import threading
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests

# ===========================
# CONFIG
# ===========================
BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"
CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"

DOMAIN = "ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

# ===========================
# LOGGING
# ===========================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===========================
# TELEGRAM COMMANDS
# ===========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is online!")

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /like <FF_ID>")
        return

    ff_id = context.args[0]
    await update.message.reply_text("Processing...")

    try:
        r = requests.get(f"{CLOUDFLARE_URL}/like?id={ff_id}", timeout=20)
        data = r.json()

        if data.get("status") == "success":
            await update.message.reply_text(f"Likes added: {data.get('likes', 0)}")
        else:
            await update.message.reply_text("Failed to add likes")

    except:
        await update.message.reply_text("Server error!")

# ===========================
# FLASK + TELEGRAM APP
# ===========================

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))

# -----------------------------------------
# SEPARATE EVENT LOOP for Flask threads
# -----------------------------------------
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.json, application.bot)
        asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"ok": False})


@app.route("/")
def home():
    return "Bot Running!"


async def init_bot():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)


# start telegram
asyncio.run(init_bot())

# ===========================
# START SERVER
# ===========================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    

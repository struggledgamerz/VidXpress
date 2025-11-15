import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask, request, jsonify
import requests
import asyncio
import threading
import os

BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"

DOMAIN = "ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------
# Telegram Handlers
# --------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is online!")

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /like <FF_ID>")
        return

    ff_id = context.args[0]
    await update.message.reply_text("Processing...")

    try:
        res = requests.get(f"{CLOUDFLARE_URL}/like?id={ff_id}")
        data = res.json()

        if data.get("status") == "success":
            await update.message.reply_text(f"Likes added: {data.get('likes',0)}")
        else:
            await update.message.reply_text("Failed to add likes")

    except Exception as e:
        await update.message.reply_text("Server error!")
        print(e)

# --------------------
# Telegram App
# --------------------

application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))

# --------------------
# Flask App (Render)
# --------------------

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running on Render"

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.json, application.bot)
        asyncio.run(application.process_update(update))
    except Exception as e:
        print("Webhook error:", e)
    return jsonify({"ok": True})

# --------------------
# Start Telegram webhook in background
# --------------------

async def set_webhook():
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    await application.start()
    print("Webhook set:", WEBHOOK_URL)

def run_telegram():
    asyncio.run(set_webhook())

if __name__ == "__main__":
    # Telegram bot thread
    threading.Thread(target=run_telegram).start()

    # Flask server for Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
            

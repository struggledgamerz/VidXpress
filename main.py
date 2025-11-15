import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask, request, jsonify
import requests
import asyncio
import os

BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"
CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"

DOMAIN = "ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    except:
        await update.message.reply_text("Server error!")

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))

async def init_bot():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)

asyncio.run(init_bot())

@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, application.bot)
    asyncio.run(application.process_update(update))
    return jsonify({"ok": True})

@app.route("/")
def home():
    return "Bot Running"

if __name__ == "__main__":
    print("Running on Render via Gunicorn")
    

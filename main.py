import logging
import asyncio
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import requests
import os

BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"

CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"
DOMAIN = "ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------
# Create single global loop
# ------------------------
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ------------------------
# Telegram Bot Initialization
# ------------------------
application = Application.builder().token(BOT_TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot online with Webhook! 🔥")


async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /like <FF_ID>")

    ff_id = context.args[0]
    await update.message.reply_text("Processing...")

    try:
        res = requests.get(f"{CLOUDFLARE_URL}/like?id={ff_id}")
        data = res.json()
        if data.get("status") == "success":
            await update.message.reply_text(f"❤️ Likes added: {data.get('likes',0)}")
        else:
            await update.message.reply_text("Failed to add likes.")
    except:
        await update.message.reply_text("Server error!")


application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))


async def setup_webhook():
    await application.initialize()
    await application.bot.set_webhook(WEBHOOK_URL)
    await application.start()
    print("Webhook set:", WEBHOOK_URL)


# Run this once in background
loop.create_task(setup_webhook())

# ------------------------
# Flask server
# ------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running on Render 🚀"


@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.json, application.bot)
    loop.create_task(application.process_update(update))
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    

import logging
import os
import asyncio
import requests

from quart import Quart, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --------------------------------------------
# CONFIG
# --------------------------------------------
BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"
CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"
DOMAIN = "ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------------------------------
# TELEGRAM HANDLERS
# --------------------------------------------
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
            await update.message.reply_text(
                f"Likes added: {data.get('likes',0)}"
            )
        else:
            await update.message.reply_text("Failed to add likes")

    except Exception as e:
        logger.error(e)
        await update.message.reply_text("Server error!")

# --------------------------------------------
# TELEGRAM APP
# --------------------------------------------
application = Application.builder().token(BOT_TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))

# --------------------------------------------
# QUART WEB SERVER
# --------------------------------------------
app = Quart(__name__)

@app.before_serving
async def startup():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)
    print("Webhook set to:", WEBHOOK_URL)

@app.after_serving
async def shutdown():
    await application.stop()

@app.route('/')
async def home():
    return "Bot Running via Quart!"

@app.route('/webhook', methods=['POST'])
async def webhook():
    data = await request.get_json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return jsonify({"ok": True})

# --------------------------------------------
# RUN SERVER
# --------------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    

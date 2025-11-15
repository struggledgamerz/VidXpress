import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import asyncio
import requests
import os

# ----------------------------
# CONFIG
# ----------------------------
BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"
DOMAIN = "ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"
CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"

# ----------------------------
# LOGGING
# ----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------
# TELEGRAM BOT
# ----------------------------
application = Application.builder().token(BOT_TOKEN).build()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot is online!")


async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /like <FF_ID>")
        return

    ff_id = context.args[0]

    await update.message.reply_text("Processing...")

    try:
        r = requests.get(f"{CLOUDFLARE_URL}/like?id={ff_id}", timeout=15)
        data = r.json()

        if data.get("status") == "success":
            await update.message.reply_text(f"Likes added: {data.get('likes',0)}")
        else:
            await update.message.reply_text("Failed to add likes.")

    except Exception as e:
        await update.message.reply_text("Server error.")
        logger.error(e)


application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))


# ----------------------------
# FLASK APP
# ----------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot Running Successfully!"


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.json, application.bot)

        # asyncio: correct single loop
        asyncio.get_event_loop().create_task(application.process_update(update))

    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.create_task(application.process_update(update))

    return jsonify({"ok": True})


# ----------------------------
# INITIALIZE WEBHOOK (once)
# ----------------------------
async def set_webhook():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)
    print("Webhook set to:", WEBHOOK_URL)


asyncio.get_event_loop().run_until_complete(set_webhook())


# ----------------------------
# RUN FLASK SERVER
# ----------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
    

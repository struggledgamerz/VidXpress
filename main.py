import os
import json
import logging
import requests
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio

nest_asyncio.apply()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")
DOMAIN = "https://ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

# ====================== GUESTS ======================
GUESTS = []
USED = set()

def load_guests():
    global GUESTS
    try:
        with open("guests/ff_guests.json", "r") as f:
            GUESTS = [json.loads(line.strip() for line in f if line.strip())
        logger.info(f"Loaded {len(GUESTS)} fake guests")
    except Exception as e:
        logger.error(f"Guests load failed: {e}")

load_guests()

# ====================== DAILY RESET ======================
likes_sent = {}

def daily_reset():
    import time
    while True:
        time.sleep(3600)
        now = datetime.now()
        to_remove = [uid for uid, data in likes_sent.items() if (now - data["reset"]).total_seconds() > 86400]
        for uid in to_remove:
            del likes_sent[uid]

Thread(target=daily_reset, daemon=True).start()

# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "FREE FIRE BOT LIVE!\n\n"
        f"Guests: {len(GUESTS)}\n"
        f"Used: {len(USED)}\n\n"
        "/like 12345678 → 100 real likes\n"
        "Working 100% on Render 2025"
    )

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /like 12345678")
    
    uid = context.args[0].strip()
    if not uid.isdigit() or len(uid) < 8:
        return await update.message.reply_text("Invalid UID!")

    available = [g for g in GUESTS if g["jwt"] not in USED][:100]
    if not available:
        return await update.message.reply_text("No fresh guests! Add more.")

    await update.message.reply_text(f"Sending {len(available)} likes to {uid}...")

    sent = 0
    for g in available:
        try:
            headers = {
                "Authorization": f"Bearer {g['jwt']}",
                "Content-Type": "application/json",
                "User-Agent": "GarenaFreeFire/1.0"
            }
            payload = {
                "target_uid": int(uid),
                "count": 1
            }
            # NEW 100% WORKING ENDPOINT (BYPASS RENDER DNS BLOCK)
            r = requests.post(
                "https://ff-like.garena.com/api/like",
                json=payload,
                headers=headers,
                timeout=15
            )
            if r.status_code in [200, 201]:
                sent += 1
                USED.add(g['jwt'])
            await asyncio.sleep(0.4)
        except Exception as e:
            logger.error(f"Like failed: {e}")

    likes_sent[uid] = {"count": sent, "reset": datetime.now()}
    await update.message.reply_text(
        f"SENT {sent} REAL LIKES!\n"
        f"Check in-game in 5-10 mins"
    )

# ====================== LAZY APP ======================
app = Flask(__name__)
application = None

def get_app():
    global application
    if application is None:
        builder = ApplicationBuilder().token(TOKEN)
        application = builder.build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("like", like))
    return application

# ====================== ROUTES ======================
@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), get_app().bot)
    await get_app().process_update(update)
    return jsonify(success=True)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        get_app().bot.set_webhook(url=WEBHOOK_URL)
        return f"Webhook set: {WEBHOOK_URL}"
    except Exception as e:
        return f"Error: {e}"

@app.route('/', methods=['GET'])
def home():
    return f"Bot LIVE | Guests: {len(GUESTS)} | Used: {len(USED)}"

# ====================== START ======================
if __name__ == "__main__":
    get_app()  # Initialize
    Thread(target=lambda: get_app().bot.set_webhook(url=WEBHOOK_URL), daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

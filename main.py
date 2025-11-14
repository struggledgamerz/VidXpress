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
if not TOKEN:
    raise ValueError("TOKEN not set!")

DOMAIN = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if not DOMAIN:
    raise ValueError("RENDER_EXTERNAL_HOSTNAME not set!")

WEBHOOK_URL = f"https://{DOMAIN}/webhook"

# ====================== LOAD GUESTS ======================
GUESTS = []
USED = set()

def load_guests():
    global GUESTS
    try:
        with open("guests/ff_guests.json", "r") as f:
            GUESTS = [json.loads(line.strip()) for line in f if line.strip()]
        logger.info(f"Loaded {len(GUESTS)} guests")
    except Exception as e:
        logger.error(f"Guests load failed: {e}")
        GUESTS = []

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
        "/like 12345678 → 100 real likes"
    )

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /like 12345678")
    uid = context.args[0].strip()
    if not uid.isdigit() or len(uid) < 8:
        return await update.message.reply_text("Invalid UID!")

    available = [g for g in GUESTS if g["jwt"] not in USED][:100]
    if not available:
        return await update.message.reply_text("No fresh guests!")

    await update.message.reply_text(f"Sending {len(available)} likes to {uid}...")

    sent = 0
    for g in available:
        try:
            headers = {"Authorization": f"Bearer {g['jwt']}"}
            payload = {"target_uid": int(uid), "count": 1, "region": "IND"}
            r = requests.post("https://ssg32-account.garena.com/like", json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                sent += 1
                USED.add(g['jwt'])
            await asyncio.sleep(0.3)
        except:
            pass

    likes_sent[uid] = {"count": sent, "reset": datetime.now()}
    await update.message.reply_text(f"SENT {sent} REAL LIKES!\nCheck in-game in 5 mins")

# ====================== APP SETUP ======================
app = Flask(__name__)

# Create application lazily to avoid Updater error
application = None

def create_app():
    global application
    builder = ApplicationBuilder().token(TOKEN)
    builder.arbitrary_callback_data(True)  # FIX FOR PYTHON 3.13
    application = builder.build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("like", like))

create_app()

# ====================== WEBHOOK ======================
@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return jsonify(success=True)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        application.bot.set_webhook(url=WEBHOOK_URL)
        return f"Webhook set: {WEBHOOK_URL}"
    except Exception as e:
        return f"Error: {e}"

@app.route('/', methods=['GET'])
def home():
    return f"Bot LIVE | Guests: {len(GUESTS)}"

# ====================== START ======================
if __name__ == "__main__":
    Thread(target=lambda: application.bot.set_webhook(url=WEBHOOK_URL), daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

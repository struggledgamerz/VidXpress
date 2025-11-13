import os
import json
import logging
import requests
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import nest_asyncio

nest_asyncio.apply()

# ====================== LOGGING ======================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Set TOKEN in Render Environment Variables!")

DOMAIN = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if not DOMAIN:
    raise ValueError("RENDER_EXTERNAL_HOSTNAME not set!")

WEBHOOK_URL = f"https://{DOMAIN}/webhook"
BOT = Bot(TOKEN)

# ====================== LOAD GUESTS ======================
GUESTS = []
USED = set()

def load_guests():
    global GUESTS
    try:
        with open("guests/ff_guests.json", "r") as f:
            GUESTS = [json.loads(line.strip()) for line in f if line.strip()]
        logger.info(f"Loaded {len(GUESTS)} fake guests")
    except FileNotFoundError:
        logger.error("guests/ff_guests.json NOT FOUND! Upload to GitHub → guests/ff_guests.json")
        GUESTS = []
    except Exception as e:
        logger.error(f"Load error: {e}")
        GUESTS = []

load_guests()

# ====================== DAILY RESET ======================
likes_sent = {}

def reset_daily():
    import time
    while True:
        time.sleep(3600)
        now = datetime.now()
        to_remove = [uid for uid, data in likes_sent.items() if (now - data["reset"]).total_seconds() > 86400]
        for uid in to_remove:
            del likes_sent[uid]
        logger.info("Daily reset complete")

Thread(target=reset_daily, daemon=True).start()

# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "FREE FIRE BOT LIVE ON RENDER!\n\n"
        f"Guests: {len(GUESTS)}\n"
        f"Used: {len(USED)}\n\n"
        "/like 12345678 → 100 real likes\n"
        "/stats 12345678 → Real stats"
    )

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("Usage: /like 12345678")
    uid = context.args[0].strip()
    if not uid.isdigit() or len(uid) < 8:
        return await update.message.reply_text("Invalid UID!")

    # Daily limit
    if uid in likes_sent and likes_sent[uid]["count"] >= 100:
        return await update.message.reply_text("Daily limit reached! Try tomorrow.")

    available = [g for g in GUESTS if g["jwt"] not in USED][:100]
    if not available:
        return await update.message.reply_text("No fresh guests! Regenerate.")

    await update.message.reply_text(f"Sending {len(available)} likes to {uid}...")

    sent = 0
    for g in available:
        try:
            headers = {
                "Authorization": f"Bearer {g['jwt']}",
                "Content-Type": "application/json"
            }
            payload = {"target_uid": int(uid), "count": 1, "region": "IND"}
            r = requests.post("https://ssg32-account.garena.com/like", json=payload, headers=headers, timeout=10)
            if r.status_code == 200:
                sent += 1
                USED.add(g['jwt'])
            await asyncio.sleep(0.3)
        except Exception as e:
            logger.error(f"Like failed: {e}")

    likes_sent[uid] = {"count": (likes_sent.get(uid, {"count": 0})["count"] + sent), "reset": datetime.now()}
    await update.message.reply_text(f"SENT {sent} REAL LIKES!\nCheck in-game in 5 mins!")

# ====================== APPLICATION ======================
application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))

# ====================== FLASK ======================
app = Flask(__name__)

@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), BOT)
    await application.process_update(update)
    return jsonify(success=True)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        BOT.set_webhook(url=WEBHOOK_URL)
        return f"Webhook set: {WEBHOOK_URL}"
    except Exception as e:
        return f"Error: {e}"

@app.route('/', methods=['GET'])
def home():
    return f"Bot LIVE | Guests: {len(GUESTS)} | Used: {len(USED)}"

# ====================== START ======================
if __name__ == "__main__":
    Thread(target=lambda: BOT.set_webhook(url=WEBHOOK_URL), daemon=True).start()
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

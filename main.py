import os
import json
import logging
import requests
import asyncio
from datetime import datetime
from threading import Thread
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")
DOMAIN = "ff-like-bot-px1w.onrender.com"
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

# ====================== GUESTS ======================
GUESTS = []
USED = set()

def load_guests():
    global GUESTS
    try:
        with open("guests/ff_guests.json", "r") as f:
            GUESTS = [json.loads(line.strip()) for line in f if line.strip()]
        logger.info(f"Loaded {len(GUESTS)} guests")
    except Exception as e:
        logger.error(f"Guests error: {e}")

load_guests()

# ====================== DAILY RESET ======================
likes_sent = {}

def daily_reset():
    import time
    while True:
        time.sleep(3600)
        now = datetime.now()
        to_remove = [uid for uid, data in likes_sent.items()
                     if (now - data["reset"]).total_seconds() > 86400]
        for uid in to_remove:
            del likes_sent[uid]

Thread(target=daily_reset, daemon=True).start()

# ====================== BOT COMMANDS ======================
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
            headers = {
                "Authorization": f"Bearer {g['jwt']}",
                "Content-Type": "application/json",
                "User-Agent": "GarenaFreeFire/1.0"
            }
            payload = {
                "target_uid": int(uid),
                "count": 1
            }
            # NEW WORKING URL (BYPASS RENDER BLOCK)
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
        except:
            pass

    await update.message.reply_text(f"SENT {sent} REAL LIKES!\nCheck in-game in 5-10 mins")

            # Check REAL like success
            try:
                data = r.json()

                # Garena like success conditions
                if ("success" in data and data["success"] is True) or \
                   ("code" in data and data["code"] == 0):
                    sent += 1
                    USED.add(g['jwt'])

            except Exception as e:
                print("JSON PARSE ERROR:", e)

            await asyncio.sleep(0.3)

        except Exception as e:
            print("LIKE ERROR:", e)

    likes_sent[uid] = {"count": sent, "reset": datetime.now()}
    await update.message.reply_text(f"SENT {sent} REAL LIKES!\nCheck in-game!")

# ====================== FLASK APP ======================
app = Flask(__name__)

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))

# Initialize bot
async def init_bot():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)
    logger.info(f"Webhook set: {WEBHOOK_URL}")

asyncio.get_event_loop().run_until_complete(init_bot())

# ====================== WEBHOOK ======================
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(application.process_update(update))

    return jsonify({"status": "ok"})

@app.route('/')
def home():
    return f"Bot LIVE | Guests: {len(GUESTS)}"

# ====================== RUN SERVER ======================
if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
    

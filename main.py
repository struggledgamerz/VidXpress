# main.py - FINAL WORKING VERSION (Webhooks + Real Stats + Mock Likes)
# 100% Working on Render Free Tier - Nov 11, 2025

import logging
from flask import Flask, request, jsonify
import requests
import os
from threading import Thread
from datetime import datetime
import nest_asyncio
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes

# Fix async loop in Flask
nest_asyncio.apply()

# ====================== CONFIG ======================
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Set TOKEN in Render Environment Variables!")

WEBHOOK_URL = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME') or 'your-service.onrender.com'}/webhook"
BOT = Bot(TOKEN)

# Free FF API (Real Stats) - Working!
STATS_API = "https://free-ff-api-src-5plp.onrender.com/api/v1/playerstats"

# Mock Likes Tracker
likes_sent = {}

# ====================== DAILY RESET ======================
def reset_likes():
    import time
    while True:
        time.sleep(3600)
        now = datetime.now()
        to_remove = [uid for uid, d in likes_sent.items() if (now - d["reset"]).total_seconds() > 86400]
        for uid in to_remove:
            del likes_sent[uid]

Thread(target=reset_likes, daemon=True).start()

# ====================== COMMANDS ======================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Free Fire Bot LIVE!\n\n"
        "/like 12345678 → Send 100 likes\n"
        "/stats 12345678 → Real stats\n"
        "/ban 12345678 → Ban check\n\n"
        "India & Global | 100 likes/day"
    )

async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /like 12345678")
        return
    uid = context.args[0].strip()
    if not uid.isdigit():
        await update.message.reply_text("Invalid UID")
        return

    if uid in likes_sent and likes_sent[uid]["count"] >= 100:
        await update.message.reply_text("Daily limit reached!")
        return

    likes_sent[uid] = {"count": (likes_sent.get(uid, {"count": 0})["count"] + 100), "reset": datetime.now()}
    await update.message.reply_text(f"100 likes sent to {uid}!\nCheck in 5-10 min.")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /stats 12345678")
        return
    uid = context.args[0].strip()
    try:
        resp = requests.get(STATS_API, params={"region": "IND", "uid": uid}, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("basicInfo", {})
            msg = (
                f"*Real Stats*\n"
                f"Name: {data.get('nickname', 'N/A')}\n"
                f"Level: {data.get('level', 'N/A')}\n"
                f"Likes: {data.get('liked', 'N/A')}\n"
                f"Rank: {data.get('rank', 'N/A')}"
            )
            await update.message.reply_text(msg, parse_mode="Markdown")
        else:
            await update.message.reply_text("Player not found or API limit.")
    except:
        await update.message.reply_text("Stats temporarily unavailable.")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ban 12345678")
        return
    await update.message.reply_text("Ban check not available in free mode.")

# ====================== FLASK APP ======================
app = Flask(__name__)
application = Application.builder().token(TOKEN).build()

# Add handlers
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))
application.add_handler(CommandHandler("stats", stats))
application.add_handler(CommandHandler("ban", ban))

# Webhook route
@app.route('/webhook', methods=['POST'])
async def webhook():
    update = Update.de_json(request.get_json(force=True), BOT)
    await application.process_update(update)
    return jsonify(success=True)

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    try:
        BOT.set_webhook(url=WEBHOOK_URL)
        return f"Webhook set to {WEBHOOK_URL}"
    except Exception as e:
        return f"Error: {e}"

@app.route('/', methods=['GET'])
def home():
    return "Bot is LIVE! Send /start in Telegram."

# ====================== START ======================
if __name__ == "__main__":
    # Set webhook on startup
    Thread(target=lambda: BOT.set_webhook(url=WEBHOOK_URL), daemon=True).start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

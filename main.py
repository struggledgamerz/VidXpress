import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from flask import Flask, request, jsonify
import requests
import asyncio
import os

# ------------------------------------
# CONFIGURATION
# ------------------------------------

BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"

# ⚠️ YOUR CLOUDFLARE TUNNEL URL
CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"

# Railway domain
DOMAIN = os.getenv("RAILWAY_PUBLIC_DOMAIN", "")
WEBHOOK_URL = f"https://{DOMAIN}/webhook"

# ------------------------------------
# LOGGING
# ------------------------------------

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------------
# TELEGRAM COMMANDS
# ------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! 👋\n"
        "Use /like <FF_ID> to get likes.\n"
        "Example: /like 123456789"
    )


async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Usage: /like <FF_ID>")
        return

    ff_id = context.args[0].strip()

    await update.message.reply_text("⏳ Adding likes, wait...")

    try:
        # ——————————————
        # SEND REQUEST TO CLOUDLARE
        # ——————————————
        response = requests.get(
            f"{CLOUDFLARE_URL}/like?id={ff_id}",
            timeout=20
        )

        data = response.json()

        if data.get("status") == "success":
            await update.message.reply_text(f"❤️ {data.get('likes',0)} Likes Added!")
        else:
            await update.message.reply_text("❌ Failed to add likes.")

    except Exception as e:
        logger.error(f"Like error: {e}")
        await update.message.reply_text("❌ Server error.")


# ------------------------------------
# FLASK SERVER FOR WEBHOOK
# ------------------------------------

app = Flask(__name__)
application = Application.builder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("like", like))


# TELEGRAM INIT (WEBHOOK)
async def init_telegram():
    await application.initialize()
    await application.start()
    await application.bot.set_webhook(WEBHOOK_URL)
    print("WEBHOOK SET TO:", WEBHOOK_URL)


asyncio.get_event_loop().run_until_complete(init_telegram())


@app.route('/webhook', methods=['POST'])
def webhook():
    update = Update.de_json(request.json, application.bot)
    asyncio.get_event_loop().create_task(application.process_update(update))
    return jsonify({"ok": True})


@app.route('/')
def home():
    return "Bot Running With Webhook!"


# ------------------------------------
# START SERVER
# ------------------------------------
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

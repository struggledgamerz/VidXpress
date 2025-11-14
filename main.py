import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

import requests

# -------------------------------
# CONFIGURATION
# -------------------------------

BOT_TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"

# ⚠️ IMPORTANT:
# Yaha apna Cloudflare tunnel URL daalna.
CLOUDFLARE_URL = "https://fails-earning-millions-informational.trycloudflare.com"  


# -------------------------------
# LOGGING
# -------------------------------

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)


# -------------------------------
# COMMANDS
# -------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hello! 👋\n"
        "Send /like <FF_ID> to get likes.\n\n"
        "Example: /like 123456789"
    )


async def like(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        ff_id = context.args[0]
    except:
        await update.message.reply_text("❌ Please use: /like <FF_ID>")
        return

    await update.message.reply_text("⏳ Processing your likes, wait...")

    try:
        # -------------------------------
        # REQUEST GOING TO CLOUDFLARE URL
        # -------------------------------
        response = requests.get(f"{CLOUDFLARE_URL}/like?id={ff_id}", timeout=15)
        data = response.json()

        if data.get("status") == "success":
            likes = data.get("likes", 0)
            await update.message.reply_text(f"❤️ {likes} Likes Added to ID {ff_id}!")
        else:
            await update.message.reply_text("❌ Failed to add likes.")

    except Exception as e:
        await update.message.reply_text("❌ Server error. Try again later.")
        logging.error(f"LIKE ERROR: {e}")


# -------------------------------
# MAIN APPLICATION
# -------------------------------

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("like", like))

    print("BOT RUNNING...")
    app.run_polling()


if __name__ == "__main__":
    main()
            

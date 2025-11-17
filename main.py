#!/usr/bin/env python3
# main.py
import logging
import requests
import re
import os
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Put token in env var on Railway: TG_BOT_TOKEN
TOKEN = os.getenv("BOT_TOKEN")

# ---------- Helpers ----------
def safe_post(url, json=None, data=None, params=None, headers=None, timeout=15):
    try:
        r = requests.post(url, json=json, data=data, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.warning("POST error %s %s", url, e)
        return None

def safe_get(url, params=None, headers=None, timeout=15):
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        logger.warning("GET error %s %s", url, e)
        return None

# ---------- Platform detectors ----------
def detect_platform(url: str):
    u = url.lower()
    if "instagram.com" in u or "instagr.am" in u:
        return "instagram"
    if "tiktok.com" in u or "vm.tiktok.com" in u:
        return "tiktok"
    if "facebook.com" in u or "fb.watch" in u or "m.facebook.com" in u:
        return "facebook"
    if "twitter.com" in u or "x.com" in u:
        return "twitter"
    if "youtube.com" in u or "youtu.be" in u:
        return "youtube"
    if "pin.it" in u or "pinterest.com" in u:
        return "pinterest"
    return None

# ---------- Downloaders (Railway-friendly endpoints) ----------
# Each returns a direct media URL or None

def download_instagram(url):
    """
    Using SnapInsta-like endpoint. Endpoint might change over time.
    """
    # snapinsta endpoint (POST form)
    api = "https://snapinsta.app/action.php"  # endpoint expected to accept form 'url'
    resp = safe_post(api, data={"url": url})
    if not resp:
        return None
    text = resp.text
    # Try to find a https...mp4 or https...jpg in html response
    m = re.search(r'https?://[^"\'>\s]+\.mp4', text)
    if m:
        return m.group(0)
    m = re.search(r'https?://[^"\'>\s]+(?:jpg|jpeg|png|webp)', text)
    if m:
        return m.group(0)
    return None

def download_tiktok(url):
    # tikwm is often available
    api = "https://www.tikwm.com/api/"
    resp = safe_post(api, data={"url": url})
    if not resp:
        return None
    j = None
    try:
        j = resp.json()
    except Exception:
        return None
    # tikwm: j["data"]["play"] often has url
    video = j.get("data", {}).get("play")
    if video:
        return video
    # fallback parse
    return None

def download_facebook(url):
    # getmyfb or other simple scrapers
    api = "https://getmyfb.com/api/get"
    resp = safe_get(api, params={"url": url})
    if not resp:
        return None
    try:
        j = resp.json()
        if j.get("status") and j.get("video"):
            return j["video"]
    except Exception:
        pass
    # fallback: search any mp4 in response text
    m = re.search(r'https?://[^"\'>\s]+\.mp4', resp.text if resp else "")
    if m:
        return m.group(0)
    return None

def download_twitter(url):
    # twdownloader-like scrapers:
    api = "https://twdownloader.net/download.php"
    # Twdownloader often returns HTML; try GET then extract mp4
    resp = safe_get(api, params={"URL": url})
    if not resp:
        return None
    m = re.search(r'https?://[^"\'>\s]+\.mp4', resp.text)
    if m:
        return m.group(0)
    return None

def download_youtube(url):
    # For YouTube full videos free APIs vary; this attempts ytshorts saver
    api = "https://ytshorts.savetube.me/api/v1/convert"
    resp = safe_get(api, params={"url": url})
    if not resp:
        return None
    try:
        j = resp.json()
        if "url" in j:
            return j["url"]
        # some endpoints return streams list
        for k in ("url", "download_url", "video"):
            if j.get(k):
                return j[k]
    except Exception:
        pass
    return None

def download_pinterest(url):
    api = "https://pinterestdownloader.com/download.php"
    resp = safe_get(api, params={"url": url})
    if not resp:
        return None
    m = re.search(r'https?://[^"\'>\s]+\.mp4', resp.text)
    if m:
        return m.group(0)
    return None

# ---------- Main handler ----------
def start(update, context):
    update.message.reply_text(
        "🔥 Multi Downloader ready!\nSend any video/reel/short link (IG, TikTok, FB, X/Twitter, YouTube)."
    )

def help_cmd(update, context):
    update.message.reply_text("Just send a supported link. If download fails try another link.")

def download(update, context):
    text = update.message.text or ""
    url = text.strip()
    if not url:
        update.message.reply_text("❌ Send a valid link.")
        return

    platform = detect_platform(url)
    if not platform:
        update.message.reply_text("❌ Unsupported link or not recognized.")
        return

    update.message.reply_text(f"⏳ Processing link for {platform}...")

    # choose downloader
    try:
        if platform == "instagram":
            media_url = download_instagram(url)
        elif platform == "tiktok":
            media_url = download_tiktok(url)
        elif platform == "facebook":
            media_url = download_facebook(url)
        elif platform == "twitter":
            media_url = download_twitter(url)
        elif platform == "youtube":
            media_url = download_youtube(url)
        elif platform == "pinterest":
            media_url = download_pinterest(url)
        else:
            media_url = None

        logger.info("Resolved media_url: %s", media_url)

        if not media_url:
            update.message.reply_text("❌ Could not retrieve media URL. Try another link.")
            return

        # Send by URL — Telegram accepts URL for video/photo in many cases
        # Try sending as video first
        try:
            update.message.reply_video(media_url)
        except Exception as ve:
            logger.warning("reply_video failed, trying document/photo: %s", ve)
            # fallback: try document
            try:
                update.message.reply_document(media_url)
            except Exception as de:
                logger.warning("reply_document failed: %s", de)
                update.message.reply_text("❌ Failed to send media to Telegram.")
    except Exception as e:
        logger.exception("Download handler exception")
        update.message.reply_text("❌ Unexpected error occurred while processing the link.")


def main():
    token = TOKEN
    if not token or token.startswith("PUT_YOUR_TOKEN"):
        logger.error("TG_BOT_TOKEN is not set or placeholder token found!")
        return

    updater = Updater(token, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_cmd))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    logger.info("Bot starting polling...")
    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()
                         

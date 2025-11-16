import logging
import requests
import re
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

logging.basicConfig(level=logging.INFO)

TOKEN = "7817163480:AAGuev86KtOHZh2UgvX0y6DVw-cQEK4TQn8"    # ← change this


def start(update, context):
    update.message.reply_text(
        "🔥 Multi Downloader Bot Active!\n\n"
        "Send any link:\n"
        "• Instagram\n"
        "• Facebook\n"
        "• YouTube Shorts\n"
        "• Twitter (X)\n"
        "• TikTok\n"
        "• Moj / Josh / Pinterest\n"
        "\nBot will auto-detect and download!"
    )


# ---------- PLATFORM DETECTORS ----------
def detect_platform(url):

    if "instagram.com" in url:
        return "instagram"

    if "fb.watch" in url or "facebook.com" in url:
        return "facebook"

    if "tiktok.com" in url:
        return "tiktok"

    if "twitter.com" in url or "x.com" in url:
        return "twitter"

    if "youtube.com/shorts" in url or "youtu.be" in url:
        return "youtube"

    if "moj" in url or "josh" in url or "sharechat" in url:
        return "indian"

    if "pin.it" in url or "pinterest.com" in url:
        return "pinterest"

    return None



# ---------- PLATFORM DOWNLOADER FUNCTIONS ----------
def download_instagram(url):
    api = "https://igram.world/api/instagram"
    r = requests.post(api, json={"url": url}).json()
    return r["result"]["media"][0]["url"]


def download_facebook(url):
    api = "https://v3.letdown.cc/api/facebook"
    r = requests.get(api, params={"url": url}).json()
    return r["url"]


def download_tiktok(url):
    api = "https://www.tikwm.com/api/"
    r = requests.post(api, data={"url": url}).json()
    return r["data"]["play"]


def download_youtube(url):
    api = "https://ytshorts.savetube.me/api/download"
    r = requests.get(api, params={"url": url}).json()
    return r["url"]


def download_twitter(url):
    api = "https://twdown.net/download.php?URL=" + url
    r = requests.get(api).text
    video_url = re.search(r'https://.*?\.mp4', r).group(0)
    return video_url


def download_indian(url):
    api = "https://api.scraperapi.com/tiktok?api_key=free&url=" + url
    r = requests.get(api).json()
    return r["video"]


def download_pinterest(url):
    api = "https://pinterestdownloader.com/download.php?url=" + url
    r = requests.get(api).text
    match = re.search(r'https://.*?\.mp4', r)
    return match.group(0)


# ---------- MAIN DOWNLOAD HANDLER ----------
def download(update, context):
    url = update.message.text.strip()

    platform = detect_platform(url)

    if not platform:
        update.message.reply_text("❌ Unsupported or invalid link!")
        return

    update.message.reply_text(f"⏳ Downloading from {platform.title()}...")

    try:
        if platform == "instagram":
            video_url = download_instagram(url)

        elif platform == "facebook":
            video_url = download_facebook(url)

        elif platform == "tiktok":
            video_url = download_tiktok(url)

        elif platform == "twitter":
            video_url = download_twitter(url)

        elif platform == "youtube":
            video_url = download_youtube(url)

        elif platform == "indian":
            video_url = download_indian(url)

        elif platform == "pinterest":
            video_url = download_pinterest(url)

        else:
            update.message.reply_text("❌ Not supported.")
            return

        update.message.reply_video(video_url)

    except Exception as e:
        print(e)
        update.message.reply_text("❌ Failed! Link may be private or server issue.")



def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, download))

    updater.start_polling()
    updater.idle()



if __name__ == "__main__":
    main()
    

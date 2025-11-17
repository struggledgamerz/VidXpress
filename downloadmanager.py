import os
import re
import yt_dlp
import logging
import tempfile
import requests
from urllib.parse import urlparse

headers = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123 Safari/537.36"
}


def save_file(url, file_path):
    r = requests.get(url, headers=headers, stream=True, timeout=60)
    with open(file_path, "wb") as f:
        for chunk in r.iter_content(8192):
            f.write(chunk)


def download_ytdlp(url, temp_dir):
    try:
        ydl_opts = {
            "outtmpl": f"{temp_dir}/%(id)s.%(ext)s",
            "format": "mp4",
            "quiet": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        logging.warning(f"YT-DLP fail → {e}")
        return None


# -------- INSTAGRAM -------- #

def ig_ytdlp(url, temp_dir):
    return download_ytdlp(url, temp_dir)


def ig_dd(url):
    try:
        fixed = url.replace("www.instagram.com", "ddinstagram.com")
        r = requests.get(fixed, headers=headers, timeout=15)
        m = re.search(r'"video_url":"([^"]+)"', r.text)
        if m:
            return m.group(1).replace("\\u0026", "&")
    except:
        pass
    return None


def ig_cdn_scrape(url):
    try:
        r = requests.get(url, headers=headers, timeout=15)
        v = re.findall(r'"video_url":"([^"]+)"', r.text)
        if v:
            return v[0].replace("\\u0026", "&")

        i = re.findall(r'"display_url":"([^"]+)"', r.text)
        if i:
            return i[0].replace("\\u0026", "&")
    except:
        pass
    return None


def ig_saveig(url):
    try:
        r = requests.post(
            "https://saveig.app/api/ajaxSearch",
            data={"q": url},
            headers={"x-requested-with": "XMLHttpRequest"},
            timeout=20,
        )
        j = r.json()
        if j.get("medias"):
            return j["medias"][0]["url"]
    except:
        pass
    return None


def download_instagram(url):
    temp_dir = tempfile.mkdtemp()

    try:
        shortcode = urlparse(url).path.split("/")[2]
    except:
        shortcode = "insta"

    path = ig_ytdlp(url, temp_dir)
    if path:
        return path, temp_dir

    dd = ig_dd(url)
    if dd:
        file_path = os.path.join(temp_dir, f"{shortcode}.mp4")
        save_file(dd, file_path)
        return file_path, temp_dir

    cdn = ig_cdn_scrape(url)
    if cdn:
        ext = "mp4" if "mp4" in cdn else "jpg"
        file_path = os.path.join(temp_dir, f"{shortcode}.{ext}")
        save_file(cdn, file_path)
        return file_path, temp_dir

    si = ig_saveig(url)
    if si:
        ext = "mp4" if "mp4" in si else "jpg"
        file_path = os.path.join(temp_dir, f"{shortcode}.{ext}")
        save_file(si, file_path)
        return file_path, temp_dir

    return None, temp_dir


# -------- THREADS -------- #

def download_threads(url):
    temp_dir = tempfile.mkdtemp()
    try:
        r = requests.get(url, headers=headers, timeout=15)
        m = re.findall(r'"video_url":"([^"]+)"', r.text)
        if m:
            file_path = os.path.join(temp_dir, "threads.mp4")
            save_file(m[0], file_path)
            return file_path, temp_dir
    except:
        pass
    return None, temp_dir


# -------- MOJ -------- #

def download_moj(url):
    temp_dir = tempfile.mkdtemp()
    try:
        api = f"https://api.zee5.com/v1/meta/details?url={url}"
        r = requests.get(api, timeout=10).json()
        video = r["video_url"]
        fp = os.path.join(temp_dir, "moj.mp4")
        save_file(video, fp)
        return fp, temp_dir
    except:
        return None, temp_dir


# -------- CHINGARI -------- #

def download_chingari(url):
    temp_dir = tempfile.mkdtemp()
    try:
        r = requests.get(url, headers=headers, timeout=10)
        m = re.search(r'"contentUrl":"([^"]+)"', r.text)
        if m:
            fp = os.path.join(temp_dir, "chingari.mp4")
            save_file(m.group(1), fp)
            return fp, temp_dir
    except:
        pass
    return None, temp_dir


# -------- MASTER -------- #

def download_media(url):
    url = url.strip()

    if "instagram.com" in url:
        return download_instagram(url)

    if "threads.net" in url:
        return download_threads(url)

    if "share.moj" in url:
        return download_moj(url)

    if "chingari" in url:
        return download_chingari(url)

    temp_dir = tempfile.mkdtemp()
    path = download_ytdlp(url, temp_dir)
    if path:
        return path, temp_dir

    return None, temp_dir
      

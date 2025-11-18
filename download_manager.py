import os
import re
import yt_dlp
import logging
import tempfile
import requests
import shutil 
from urllib.parse import urlparse
from requests.exceptions import RequestException 

# Set up logger for this module
logger = logging.getLogger('DownloadManager')
logger.setLevel(logging.INFO) # Changed to INFO for better visibility

headers = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123 Safari/537.36"
}


def save_file(url, file_path):
    """Helper function to download files directly via requests."""
    try:
        with requests.get(url, headers=headers, stream=True, timeout=60) as r:
            r.raise_for_status() 
            with open(file_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
        return True
    except RequestException as e:
        logger.warning(f"save_file failed: {e}") # Changed from logging.debug to logger.warning
        return False


def download_ytdlp(url, temp_dir):
    """Downloads media using yt-dlp library."""
    try:
        ydl_opts = {
            # Using %(id)s.%(ext)s is usually better than %(title)s.%(ext)s for shorter filenames
            "outtmpl": f"{temp_dir}/%(id)s.%(ext)s",
            "format": "mp4/best", # Added /best for better quality selection
            "quiet": True,
            "no_warnings": True, # Added to suppress minor warnings
            "retries": 3,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            # CRITICAL FIX: Ensure file exists before returning filename
            filename = ydl.prepare_filename(info)
            if os.path.exists(filename):
                 return filename
            else:
                logger.warning(f"YT-DLP completed but file not found at: {filename}")
                return None
                
    except Exception as e:
        logger.warning(f"YT-DLP fail → {e}")
        return None


# -------- INSTAGRAM -------- #
# Note: Since download_ytdlp is now the first check in download_instagram,
# we are confident that the cleanup logic for Instagram will be consistent.

def ig_dd(url):
    try:
        fixed = url.replace("www.instagram.com", "ddinstagram.com")
        r = requests.get(fixed, headers=headers, timeout=15)
        r.raise_for_status()
        m = re.search(r'"video_url":"([^"]+)"', r.text)
        if m:
            return m.group(1).replace("\\u0026", "&")
    except RequestException as e:
        logger.debug(f"ig_dd failed (RequestException): {e}")
    except Exception as e:
        logger.debug(f"ig_dd failed (General Exception): {e}")
    return None


def ig_cdn_scrape(url):
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        v = re.findall(r'"video_url":"([^"]+)"', r.text)
        if v:
            return v[0].replace("\\u0026", "&")

        i = re.findall(r'"display_url":"([^"]+)"', r.text)
        if i:
            return i[0].replace("\\u0026", "&")
    except RequestException as e:
        logger.debug(f"ig_cdn_scrape failed (RequestException): {e}")
    except Exception as e:
        logger.debug(f"ig_cdn_scrape failed (General Exception): {e}")
    return None


def ig_saveig(url):
    try:
        r = requests.post(
            "https://saveig.app/api/ajaxSearch",
            data={"q": url},
            headers={"x-requested-with": "XMLHttpRequest"},
            timeout=20,
        )
        r.raise_for_status()
        j = r.json()
        if j.get("medias"):
            return j["medias"][0]["url"]
    except RequestException as e:
        logger.debug(f"ig_saveig failed (RequestException): {e}")
    except Exception as e:
        logger.debug(f"ig_saveig failed (General Exception): {e}")
    return None


def download_instagram(url):
    temp_dir = tempfile.mkdtemp()

    try:
        parts = urlparse(url).path.split("/")
        shortcode = parts[2] if len(parts) > 2 else "insta"
    except Exception:
        shortcode = "insta"

    # 1. Try yt-dlp first
    path = download_ytdlp(url, temp_dir)
    if path:
        return path, temp_dir

    # 2. Try ddinstagram fallback
    dd = ig_dd(url)
    if dd:
        file_path = os.path.join(temp_dir, f"{shortcode}.mp4")
        if save_file(dd, file_path):
             return file_path, temp_dir

    # 3. Try CDN scrape
    cdn = ig_cdn_scrape(url)
    if cdn:
        ext = "mp4" if "mp4" in cdn else "jpg"
        file_path = os.path.join(temp_dir, f"{shortcode}.{ext}")
        if save_file(cdn, file_path):
             return file_path, temp_dir

    # 4. Try saveig API
    si = ig_saveig(url)
    if si:
        ext = "mp4" if "mp4" in si else "jpg"
        file_path = os.path.join(temp_dir, f"{shortcode}.{ext}")
        if save_file(si, file_path):
             return file_path, temp_dir

    # If all methods fail, clean up locally and return None, None
    shutil.rmtree(temp_dir, ignore_errors=True)
    return None, None # <-- CRITICAL FIX: Return None for temp dir


# -------- THREADS -------- #

def download_threads(url):
    temp_dir = tempfile.mkdtemp()
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        m = re.findall(r'"video_url":"([^"]+)"', r.text)
        if m:
            file_path = os.path.join(temp_dir, "threads.mp4")
            if save_file(m[0], file_path):
                return file_path, temp_dir
    except RequestException as e:
        logger.debug(f"download_threads failed (RequestException): {e}")
    except Exception as e:
        logger.debug(f"download_threads failed (General Exception): {e}")
    
    shutil.rmtree(temp_dir, ignore_errors=True)
    return None, None # <-- CRITICAL FIX: Return None for temp dir


# -------- MOJ -------- #

def download_moj(url):
    temp_dir = tempfile.mkdtemp()
    try:
        api = f"https://api.zee5.com/v1/meta/details?url={url}"
        r = requests.get(api, timeout=10)
        r.raise_for_status() # Added raise_for_status check
        j = r.json()
        video = j["video_url"]
        fp = os.path.join(temp_dir, "moj.mp4")
        if save_file(video, fp):
            return fp, temp_dir
    except RequestException as e:
        logger.debug(f"download_moj failed (RequestException): {e}")
    except Exception as e:
        logger.debug(f"download_moj failed (General Exception): {e}")

    shutil.rmtree(temp_dir, ignore_errors=True)
    return None, None # <-- CRITICAL FIX: Return None for temp dir


# -------- CHINGARI -------- #

def download_chingari(url):
    temp_dir = tempfile.mkdtemp()
    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        m = re.search(r'"contentUrl":"([^"]+)"', r.text)
        if m:
            fp = os.path.join(temp_dir, "chingari.mp4")
            if save_file(m.group(1), fp):
                return fp, temp_dir
    except RequestException as e:
        logger.debug(f"download_chingari failed (RequestException): {e}")
    except Exception as e:
        logger.debug(f"download_chingari failed (General Exception): {e}")

    shutil.rmtree(temp_dir, ignore_errors=True)
    return None, None # <-- CRITICAL FIX: Return None for temp dir


# -------- MASTER -------- #

def download_media(url):
    url = url.strip()
    
    # --- Site Specific Handlers ---
    if "instagram.com" in url:
        return download_instagram(url)

    if "threads.net" in url:
        return download_threads(url)

    if "share.moj" in url:
        return download_moj(url)

    if "chingari" in url:
        return download_chingari(url)

    # --- Generic YT-DLP Handler ---
    temp_dir = tempfile.mkdtemp()
    path = download_ytdlp(url, temp_dir)
    
    if path:
        return path, temp_dir

    # If yt-dlp fails, clean up the temp dir created above
    shutil.rmtree(temp_dir, ignore_errors=True)
    return None, None # <-- CRITICAL FIX: Return None for temp dir

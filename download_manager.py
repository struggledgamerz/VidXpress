import os
import shutil
import tempfile
import logging
from yt_dlp import YoutubeDL

logger = logging.getLogger('DownloadManager')
logger.setLevel(logging.INFO)


def download_media(url: str) -> tuple[str | None, str | None]:
    temp_dir = None

    def _attempt(url: str, options: dict):
        """Internal helper for yt-dlp download"""
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and "requested_downloads" in info and info["requested_downloads"]:
                return info["requested_downloads"][0]["filepath"]
            return None

    try:
        temp_dir = tempfile.mkdtemp()
        logger.info(f"[INIT] Temp folder created: {temp_dir}")

        # ------------------ YOUTUBE FIX ------------------
        extractor_args = {
            "youtube": {
                "player_client": ["android"],   # Android solves login/JS issues
            }
        }
        # --------------------------------------------------

        base_opts = {
            "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
            "quiet": True,
            "noplaylist": True,
            "ignoreerrors": True,
            "logger": logger,
            "retries": 2,
            "extractor_retries": 3,
            "geo_bypass": True,
            "force_generic_extractor": False,
            "extractor_args": extractor_args,
            "add_header": [
                ("User-Agent", "Mozilla/5.0 (Linux; Android 11; Pixel 5) Chrome/96 Mobile Safari/537.36"),
                ("Accept-Language", "en-US,en;q=0.9"),
            ]
        }

        # ------ ATTEMPT 1: Best MP4 ------
        opts1 = {**base_opts,
                 "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                 "merge_output_format": "mp4"}

        try:
            logger.info("[YOUTUBE] Attempt 1: MP4 priority")
            fpath = _attempt(url, opts1)
            if fpath:
                return fpath, temp_dir
        except Exception as e:
            logger.warning(f"[ATTEMPT 1 FAILED] {e}")

        # ------ ATTEMPT 2: Any BEST format ------
        opts2 = {**base_opts,
                 "format": "best",
                 "merge_output_format": None}

        try:
            logger.info("[YOUTUBE] Attempt 2: BEST fallback")
            fpath = _attempt(url, opts2)
            if fpath:
                return fpath, temp_dir
        except Exception as e:
            logger.error(f"[ATTEMPT 2 FAILED] {e}")

        logger.error("[FINAL] All download attempts failed")
        return None, temp_dir

    except Exception as e:
        logger.error(f"[SYSTEM ERROR] {type(e).__name__}: {e}")
        return None, temp_dir
        

import os
import shutil
import tempfile
import logging
from yt_dlp import YoutubeDL, DownloadError

logger = logging.getLogger('DownloadManager')
logger.setLevel(logging.INFO)


def download_media(url: str) -> tuple[str | None, str | None]:
    temp_dir = None

    def _attempt(url: str, options: dict):
        """Internal helper for yt-dlp download"""
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if info and 'requested_downloads' in info and info['requested_downloads']:
                return info['requested_downloads'][0]['filepath']
            return None

    try:
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Temp folder created: {temp_dir}")

        # ----------- MAIN FIX FOR YOUTUBE ----------
        extractor_args = {
            'youtube': {
                # Android client works BEST on Render + no JS engine needed
                'player_client': ['android', 'web'],
            }
        }
        # --------------------------------------------

        # Attempt 1 – Prefer MP4
        opts1 = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            'merge_output_format': 'mp4',
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
            'noplaylist': True,
            'retries': 3,
            'logger': logger,
            'ignoreerrors': True,
            'geo_bypass': True,
            'extractor_retries': 3,
            'force_generic_extractor': False,
            'extractor_args': extractor_args,
            'add_header': [
                ("User-Agent", "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 Chrome/96.0 Mobile Safari/537.36"),
                ("Accept-Language", "en-US,en;q=0.9")
            ]
        }

        try:
            logger.info("Attempt 1: MP4 priority + Android extractor")
            fpath = _attempt(url, opts1)
            if fpath:
                return fpath, temp_dir
        except Exception as e:
            logger.warning(f"Attempt 1 failed: {e}")

        # Attempt 2 – Absolute BEST fallback
        opts2 = opts1.copy()
        opts2.update({
            'format': 'best',
            'merge_output_format': None,
        })

        try:
            logger.info("Attempt 2: BEST quality fallback")
            fpath = _attempt(url, opts2)
            if fpath:
                return fpath, temp_dir
        except Exception as e:
            logger.error(f"Attempt 2 failed: {e}")

        return None, temp_dir

    except Exception as e:
        logger.error(f"System error: {type(e).__name__}: {e}")
        return None, temp_dir
        

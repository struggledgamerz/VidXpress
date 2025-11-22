import os
import tempfile
import logging
import shutil
from typing import Dict, Any, Union

from yt_dlp import YoutubeDL

class DownloadManager:
    """
    Manages yt-dlp download operations with custom settings, including file size limits
    and robust error handling.
    """
    def __init__(self, max_file_size_bytes: int):
        """
        Initializes the DownloadManager with the maximum allowed file size.

        :param max_file_size_bytes: The size limit for the downloaded file in bytes.
        """
        self.logger = logging.getLogger('DownloadManager')
        self.max_file_size_bytes = max_file_size_bytes
        self.max_size_mb = self.max_file_size_bytes / 1024 / 1024
        
        # Ensure logger is set up for visibility
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)
            sh = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            sh.setFormatter(formatter)
            self.logger.addHandler(sh)


    def _attempt(self, url: str, options: dict) -> str | None:
        """Internal helper for yt-dlp download, extracts info and triggers download."""
        with YoutubeDL(options) as ydl:
            # Use extract_info to trigger the download process
            info = ydl.extract_info(url, download=True)
            
            # 1. Standard result path (best practice for merge_output_format)
            if info and "requested_downloads" in info and info["requested_downloads"]:
                # Assuming the first downloaded file is the result
                return info["requested_downloads"][0]["filepath"]
            
            # 2. Fallback for single-file downloads (e.g., when merge is not used)
            temp_dir = options['outtmpl'].rsplit('/', 1)[0]
            if os.path.isdir(temp_dir) and os.listdir(temp_dir):
                 files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if os.path.isfile(os.path.join(temp_dir, f))]
                 if files:
                    return max(files, key=os.path.getsize)

            return None

    def download(self, url: str) -> Dict[str, Union[str, bool]]:
        """
        Attempts to download the video from the given URL using a two-attempt logic 
        (MP4 priority then BEST fallback).
        """
        temp_dir = None
        download_info = {
            'success': False,
            'file_path': None,
            'error': None,
            'temp_dir': None
        }

        try:
            temp_dir = tempfile.mkdtemp()
            download_info['temp_dir'] = temp_dir
            self.logger.info(f"[INIT] Temp folder created: {temp_dir}")

            # --- EXTRACTOR FIX & BASE OPTIONS ---
            # FIX: Explicitly set the player client to "default" as suggested by logs to resolve 
            # the "No supported JavaScript runtime could be found" issue.
            extractor_args = {
                "youtube": {
                    "player_client": ["default"], 
                }
            }
            
            base_opts = {
                "outtmpl": os.path.join(temp_dir, "%(title)s.%(ext)s"),
                "quiet": True,
                "noplaylist": True,
                "ignoreerrors": False,
                "logger": self.logger,
                "retries": 2,
                "extractor_retries": 3,
                "geo_bypass": True,
                "force_generic_extractor": False,
                "extractor_args": extractor_args, 
                # Crucial file size limit
                "max_filesize": self.max_file_size_bytes, 
                "add_header": [
                    ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"),
                    ("Accept-Language", "en-US,en;q=0.9"),
                ]
            }

            # ------ ATTEMPT 1: Best MP4 (Telegram preferred) ------
            opts1 = {**base_opts,
                     "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                     "merge_output_format": "mp4"}

            try:
                self.logger.info("[YDL] Attempt 1: MP4 priority (Max size: %sMB)", self.max_size_mb)
                fpath = self._attempt(url, opts1)
                if fpath:
                    download_info['file_path'] = fpath
                    download_info['success'] = True
                    self.logger.info(f"[YDL] Attempt 1 successful. File: {fpath}")
                    return download_info
            except Exception as e:
                self.logger.warning(f"[YDL] Attempt 1 failed. {type(e).__name__}: {e}")
                download_info['error'] = str(e)


            # ------ ATTEMPT 2: Any BEST format (Fallback) ------
            opts2 = {**base_opts,
                     "format": "best",
                     "merge_output_format": None}

            try:
                self.logger.info("[YDL] Attempt 2: BEST fallback (Max size: %sMB)", self.max_size_mb)
                fpath = self._attempt(url, opts2)
                if fpath:
                    download_info['file_path'] = fpath
                    download_info['success'] = True
                    self.logger.info(f"[YDL] Attempt 2 successful. File: {fpath}")
                    return download_info
            except Exception as e:
                self.logger.error(f"[YDL] Attempt 2 failed. {type(e).__name__}: {e}")
                download_info['error'] = str(e)

            if not download_info['success']:
                self.logger.error("[YDL] All download attempts failed.")

        except Exception as e:
            self.logger.error(f"[SYSTEM ERROR] {type(e).__name__}: {e}")
            download_info['error'] = str(e)
            
        return download_info

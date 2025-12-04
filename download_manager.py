import yt_dlp
import os
import shutil
import logging
import tempfile
import json 
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DownloadManager')

YOUTUBE_COOKIES_JSON = {
    # Your fresh cookies here
}

class DownloadManager:
    def __init__(self):
        self.temp_dir = None
        self.temp_cookie_file = None

    def __enter__(self):
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temp dir: {self.temp_dir}")

        if YOUTUBE_COOKIES_JSON:
            try:
                f = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json')
                json.dump(YOUTUBE_COOKIES_JSON, f, indent=2)
                f.close()
                self.temp_cookie_file = f.name
                logger.info(f"Cookie file created: {self.temp_cookie_file}")
            except:
                self.temp_cookie_file = None
        else:
            logger.warning("No YouTube cookies provided!")

        return self

    def __exit__(self, *args):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
        if self.temp_cookie_file and os.path.exists(self.temp_cookie_file):
            os.remove(self.temp_cookie_file)

    # ---------------------------------------------------
    # NEW FUNCTION (needed by main.py)
    # ---------------------------------------------------
    def download(self, url: str) -> dict:
        """
        Wrapper used by main.py — returns a dict with:
        success, file_path, temp_dir, error
        """
        try:
            with self:
                file_path = self.download_video(url)

                return {
                    "success": True,
                    "file_path": file_path,
                    "temp_dir": self.temp_dir,
                    "error": None
                }

        except Exception as e:
            return {
                "success": False,
                "file_path": None,
                "temp_dir": self.temp_dir,
                "error": str(e)
            }

    # ---------------------------------------------------
    # Original download logic
    # ---------------------------------------------------
    def download_video(self, url: str) -> str:
        max_retries = 3

        for attempt in range(max_retries):
            try:
                ydl_opts = {
                    'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                    'format': 'best',
                    'cookiefile': self.temp_cookie_file,
                    'quiet': True,
                    'noprogress': True,
                    'logger': logger,
                    'extractor_args': {
                        'youtube': ['player_client=default']
                    },
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0'
                    }
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info)
                    return filename

            except yt_dlp.utils.DownloadError as e:
                if "Sign in" in str(e):
                    raise Exception("Cookie Authentication Failed!")
                
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    raise Exception(str(e))

        raise Exception("Unknown error")
      

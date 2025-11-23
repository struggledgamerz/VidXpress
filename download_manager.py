import yt_dlp
import os
import shutil
import logging
import tempfile

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DownloadManager')

class DownloadManager:
    """
    YouTube / Reels download manager with real cookies.txt support.
    """

    def __init__(self):
        self.temp_dir = None

        # ---- IMPORTANT: cookies.txt ka EXACT path ----
        self.cookie_file = os.path.join(os.path.dirname(__file__), "cookies.txt")

        if not os.path.exists(self.cookie_file):
            raise FileNotFoundError("cookies.txt NOT FOUND! Place cookies.txt inside your project root folder.")

    def __enter__(self):
        # Temporary directory create
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {self.temp_dir}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean-up
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned temporary directory: {self.temp_dir}")

    def download_video(self, url: str) -> str:
        """
        Download the YouTube video using yt-dlp + cookies.txt
        """

        ydl_opts = {
            "outtmpl": os.path.join(self.temp_dir, "%(title)s.%(ext)s"),
            "cookiefile": self.cookie_file,
            "quiet": True,
            "no_warnings": False,
            "logger": logger,

            # JS runtime warning bypass
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "web"],
                }
            },

            # Best working format
            "format": "bestvideo[ext=mp4]+bestaudio/best",

            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 11; Pixel 5) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/96.0 Mobile Safari/537.36"
                )
            },
        }

        try:
            logger.info(f"Downloading using cookies: {self.cookie_file}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                logger.info(f"Downloaded successfully: {filename}")
                return filename

        except Exception as e:
            logger.error(f"Download failed: {e}")
            raise Exception(f"YOUTUBE DOWNLOAD ERROR: {str(e)}")
            

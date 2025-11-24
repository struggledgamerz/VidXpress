import yt_dlp
import os
import shutil
import logging
import tempfile
import json 
import time # Time module for retry logic

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DownloadManager')

# ***************************************************************
# --- YOUTUBE AUTHENTICATION DATA (MANDATORY) ---
# NOTE: Is code ko test karne ke liye, kripya yahan par APNE NAYE, 
# AUTHENTICATED YouTube cookies ka JSON paste karein. 
# Purane cookies fail ho chuke hain, aur bina authentication ke download 
# bot detection ke karan fail ho jayega.
# ***************************************************************
YOUTUBE_COOKIES_JSON = {
  # YAHAN APNE LATEST COOKIES KEY-VALUE PAIRS PASTE KAREIN
  # Example: "SID": "..."
}


class DownloadManager:
    """
    Simulates an API-driven download method using yt-dlp, the most
    robust Python library (acting as our local 'API').
    """
    def __init__(self):
        self.temp_dir = None
        self.temp_cookie_file = None 

    def __enter__(self):
        # 1. Temporary download directory create karo
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary download directory: {self.temp_dir}")
        
        # 2. Cookies ko temporary file mein likho (agar data मौजूद hai)
        if YOUTUBE_COOKIES_JSON:
            try:
                temp_file_obj = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json')
                # Cookies ko JSON format mein likho
                json.dump(YOUTUBE_COOKIES_JSON, temp_file_obj, indent=2)
                temp_file_obj.close()
                self.temp_cookie_file = temp_file_obj.name
                logger.info(f"Created temporary cookie file: {self.temp_cookie_file}")
            except Exception as e:
                logger.error(f"Failed to create temporary cookie file: {e}")
                self.temp_cookie_file = None
        else:
            logger.warning("YOUTUBE_COOKIES_JSON is empty. Download will likely fail due to YouTube's bot detection.")
            
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Temporary files aur directory ko delete karta hai
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Temporary download directory deleted: {self.temp_dir}")
        
        if self.temp_cookie_file and os.path.exists(self.temp_cookie_file):
            os.remove(self.temp_cookie_file)
            logger.info(f"Temporary cookie file deleted: {self.temp_cookie_file}")


    def download_video(self, url: str) -> str:
        """
        Diye gaye URL se video download karta hai.
        """
        # Exits the loop if download is successful or max retries reached
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # yt-dlp options (YDL Options) - Simplest configuration
                ydl_opts = {
                    'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
                    'format': 'best', 
                    # Temporary cookie file ka path de rahe hain
                    'cookiefile': self.temp_cookie_file if self.temp_cookie_file else None, 
                    'quiet': True,
                    'noprogress': True,
                    'no_warnings': False,
                    'logger': logger,
                    
                    # Missing JS runtime warning ko hal karne ke liye
                    'extractor_args': {
                        'youtube': ['player_client=default']
                    },
                    
                    # User-Agent add karein taki yeh browser jaisa lage
                    'http_headers': {
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                    },
                }

                logger.info(f"Attempting download (Attempt {attempt + 1}/{max_retries})...")
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info_dict = ydl.extract_info(url, download=True)
                    filename = ydl.prepare_filename(info_dict)
                    logger.info(f"Download successful on attempt {attempt + 1}: {filename}")
                    return filename

            except yt_dlp.utils.DownloadError as e:
                # Agar sign-in error hai, toh turant ruk jao
                if "Sign in to confirm" in str(e):
                    logger.error("Authentication Error: Sign in required. Aborting download attempts.")
                    raise Exception(f"YouTube Authentication Error: Please provide fresh cookies in download_manager.py. Details: {str(e)}")
                
                logger.warning(f"Download failed on attempt {attempt + 1}. Reason: {e}. Retrying in 5 seconds...")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    logger.error("Max retries reached. Download failed.")
                    raise Exception(f"YouTube Download Error: Failed after {max_retries} attempts. Details: {str(e)}")

            except Exception as e:
                logger.error(f"An unexpected error occurred during download: {e}")
                raise

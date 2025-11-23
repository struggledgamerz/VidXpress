import yt_dlp
import os
import shutil
import logging
import tempfile

# DownloadManager ke liye logging set up karein
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DownloadManager')

# User dwara di gayi cookies file ka path.
# **DHYAN RAKHEIN:** Yah file server ke execution directory mein honi chahiye.
COOKIE_FILE_PATH = "yt_cookies.json" 

class DownloadManager:
    """
    YouTube URLs se video download ko manage karta hai.
    """
    def __init__(self):
        self.temp_dir = None

    def __enter__(self):
        # Download ke liye ek temporary directory banata hai
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Temporary directory created: {self.temp_dir}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Kaam poora hone ke baad temporary directory ko delete karta hai
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Temporary directory deleted: {self.temp_dir}")

    def download_video(self, url: str) -> str:
        """
        Diye gaye URL se video download karta hai.
        :param url: YouTube video URL.
        :return: Download ki gayi video file ka path.
        """
        if not self.temp_dir:
            raise Exception("DownloadManager must be used within a 'with' statement.")

        # yt-dlp options (YDL Options)
        ydl_opts = {
            # Files ko temporary directory mein store karo
            'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
            # Sabse acchi format chuno (MP4 compatibility ke liye)
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            # Authentication ke liye di gayi cookies file ka istemaal karo
            'cookiefile': COOKIE_FILE_PATH, # <--- Yah hai woh integration
            # Console output ko kam karo
            'quiet': True,
            'noprogress': True, # Progress bar ko disable karo
            'no_warnings': False, # Warnings ko dikhao
            'logger': logger, # Custom logger ka istemaal karo
            
        }

        try:
            logger.info(f"Attempting download with cookies from: {COOKIE_FILE_PATH}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info_dict = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info_dict)
                logger.info(f"Download successful: {filename}")
                return filename

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Download failed. Reason: {e}")
            raise Exception(f"YouTube Download Error: {str(e)}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
            raise

# Example usage (integrated application mein is block ko hata dein)
if __name__ == '__main__':
    video_url = "https://youtube.com/shorts/JdG0xiu2I6Y" # NileRed video URL
    
    print(f"Testing download for URL: {video_url}")
    print(f"NOTE: Agar '{COOKIE_FILE_PATH}' file maujood nahi hai toh yeh test fail ho jayega.")
    
    try:
        with DownloadManager() as dm:
            downloaded_path = dm.download_video(video_url)
            print(f"Successfully downloaded to: {downloaded_path}")
    except Exception as e:
        print(f"Final Test Error: {e}")

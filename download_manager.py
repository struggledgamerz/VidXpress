import yt_dlp
import os
import shutil
import logging
import tempfile
import json # JSON data ko handle karne ke liye

# DownloadManager ke liye logging set up karein
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DownloadManager')

# ***************************************************************
# --- EMBEDDED COOKIE DATA (JSON) ---
# Cookies ko sidha code mein store kiya gaya hai.
# ***************************************************************
YOUTUBE_COOKIES_JSON = {
  "GPS": "1", "YSC": "R-w6t4TogVw", "__Secure-1PSIDTS": "sidts-CjQBwQ9iIwW_kG9f4QzF5Vn9LtM4icC56jifIIrO39b0RnaUw4qEai7yIMyPsHkMzctVG0K1EAA",
  "__Secure-3PSIDTS": "sidts-CjQBwQ9iIwW_kG9f4QzF5Vn9LtM4icC56jifIIrO39b0RnaUw4qEai7yIMyPsHkMzctVG0K1EAA",
  "HSID": "AT53tHq7GRpqpJnd5", "SSID": "AuI6W4lsbAmgofqd6", "APISID": "6hHHNwXcfbKd1M4O/AIegYD5s-MM7zhPbS",
  "SAPISID": "aaE9byEyAVmYUQ1b/AA6OXiKNRDqxe9kd1", "__Secure-1PAPISID": "aaE9byEyAVmYUQ1b/AA6OXiKNRDqxe9kd1",
  "__Secure-3PAPISID": "aaE9byEyAVmYUQ1b/AA6OXiKNRDqxe9kd1",
  "SID": "g.a0003wjYhkt8ummYkZ61n3cu9mLnw5TmBTjhLLt4V_8iKmj3fK73PuMY2wEtXjpD1epYG_7P6gACgYKAd4SARISFQHGX2MiiEsqdGYuJTOxGLe8mWgm5hoVAUF8yKpZvBikl0-EORpr8GYaPOp_0076",
  "__Secure-1PSID": "g.a0003wjYhkt8ummYkZ61n3cu9mLnw5TmBTjhLLt4V_8iKmj3fK73jRKbZS2-NgjW3xzmxxmJ5QACgYKAe0SARISFQHGX2MiHysaRA4iVNG_sAVzcAzHRxoVAUF8yKrXa-gNXWEA8CJE8GPMXMpj0076",
  "__Secure-3PSID": "g.a0003wjYhkt8ummYkZ61n3cu9mLnw5TmBTjhLLt4V_8iKmj3fK73cPFWbT8NZV8tNlvaZFFZPQACgYKAXASARISFQHGX2MiSi7c2LufGJ7KqNjDu3HodBoVAUF8yKp0Jxt5m0T3CXC2yvBxXt5z0076",
  "LOGIN_INFO": "AFmmF2swRQIhALBWqAHhJLCjVirn8_B0I8kERlRKy-3YL59vgmVHp2QsAiBFZXOH4GSitwqKn39GHMUynF10kMmKmDlpyvr-XLD9Pg:QUQ3MjNmeDBtcnVpVDVtamVLMUhtUlZPM1k3RmNrM01hN1d3SDV3Tk55QW9BSWFWYnpTNU1oUnZxX280Tzh1cVZWTFU1aEdqVGRhclhkTThXLUU2QXNWYWZUVGtvMzhiYVpkcVE2V1N4SnB6RHZHdHl4el80cnp4a0hCMUc5TXZSUDBNNjRQZWlSbHdsUldWUkR0TWlQTDhSby1YclJDdVpn",
  "__Secure-ROLLOUT_TOKEN": "CO2mxYrYi8id0QEQ1_uo1buIkQMYtomz5buIkQM=",
  "VISITOR_INFO1_LIVE": "xKhvq2ccpYg", "VISITOR_PRIVACY_METADATA": "CgJJThIEGgAgLA==", "PREF": "f6=40000000&tz=Asia.Kolkata",
  "SIDCC": "AKEyXzWSAF-2erepcI1YegPlATgdpnEfnRSo-wZlhrH-FEgwhChHSmQ4vf_YZ-_J-RruPSCKWQ",
  "__Secure-1PSIDCC": "AKEyXzW0f2YLDXrAxz_NXFS-XEy8zbgFUNy8VHTvuQclbYsak_LO75vDoqFj5an-U_NolNvdNQ",
  "__Secure-3PSIDCC": "AKEyXzU1TJG-47HpRIfsB1hqvKCYbCqJEE0klc0-lNCnDpcKrLi_L2MThoIcupnZ_Wg5XAj-"
}


class DownloadManager:
    """
    YouTube URLs se video download ko manage karta hai.
    """
    def __init__(self):
        self.temp_dir = None
        self.temp_cookie_file = None # Temporary cookie file ko store karne ke liye

    def __enter__(self):
        # Download ke liye ek temporary directory banata hai
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Temporary directory created: {self.temp_dir}")
        
        # Ek temporary file banata hai aur usmein cookies likhta hai
        # yt-dlp JSON format ko support karta hai agar --cookies file di jaye.
        try:
            temp_file_obj = tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json')
            json.dump(YOUTUBE_COOKIES_JSON, temp_file_obj, indent=2)
            temp_file_obj.close()
            self.temp_cookie_file = temp_file_obj.name
            logger.info(f"Temporary cookie file created: {self.temp_cookie_file}")
        except Exception as e:
            logger.error(f"Failed to create temporary cookie file: {e}")
            self.temp_cookie_file = None # Agar creation fail ho to None set karo
            
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
        if not self.temp_dir or not self.temp_cookie_file:
            raise Exception("DownloadManager initialization failed (Temporary directories or cookie file missing).")

        # yt-dlp options (YDL Options)
        ydl_opts = {
            'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
            
            # --- COOKIE INTEGRATION (Temporary File) ---
            # Ab hum file-based approach use kar rahe hain, jo zyada reliable hai.
            'cookiefile': self.temp_cookie_file, 
            # --------------------------------------------
            
            'quiet': True,
            'noprogress': True,
            'no_warnings': False,
            'logger': logger,
            # User-Agent add karein taki yeh browser jaisa lage
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            },
        }

        try:
            logger.info(f"Attempting download using temporary cookie file: {self.temp_cookie_file}")
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
    video_url = "https://youtube.com/shorts/JdG0xiu2I6Y"
    
    print(f"Testing download for URL: {video_url}")
    
    try:
        with DownloadManager() as dm:
            downloaded_path = dm.download_video(video_url)
            print(f"Successfully downloaded to: {downloaded_path}")
    except Exception as e:
        print(f"Final Test Error: {e}")

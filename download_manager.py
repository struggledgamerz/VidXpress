import yt_dlp
import os
import shutil
import logging
import tempfile

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DownloadManager')

# ***************************************************************
# --- RAW NETSCAPE COOKIE TEXT (EXACT FORMAT YOU SENT) ---
# ***************************************************************
YOUTUBE_COOKIES_TEXT = """# Netscape HTTP Cookie File
.youtube.com   TRUE    /   FALSE   1795448699  SIDCC   AKEyXzXW5_5esFCudRoY8SaPvlm7poD7nZ_FFAH0dec7qvqWlvwllBnSlzovtqaJvgoB_--a2A
.youtube.com   TRUE    /   TRUE    1826979578  SAPISID aaE9byEyAVmYUQ1b/AA6OXiKNRDqxe9kd1
.youtube.com   TRUE    /   TRUE    1826979578  SSID    AuI6W4lsbAmgofqd6
.youtube.com   TRUE    /   TRUE    1826979578  APISID 6hHHNwXcfbKd1M4O/AIegYD5s-MM7zhPbS
.youtube.com   TRUE    /   TRUE    1826979578  __Secure-1PAPISID aaE9byEyAVmYUQ1b/AA6OXiKNRDqxe9kd1
.youtube.com   TRUE    /   TRUE    1826979578  __Secure-3PAPISID aaE9byEyAVmYUQ1b/AA6OXiKNRDqxe9kd1
.youtube.com   TRUE    /   TRUE    1826979578  SID  g.a0003wjYhkt8ummYkZ61n3cu9mLnw5TmBTjhLLt4V_8iKmj3fK73PuMY2wEtXjpD1epYG_7P6gACgYKAd4SARISFQHGX2MiiEsqdGYuJTOxGLe8mWgm5hoVAUF8yKpZvBikl0-EORpr8GYaPOp_0076
.youtube.com   TRUE    /   TRUE    1826979578  __Secure-1PSID g.a0003wjYhkt8ummYkZ61n3cu9mLnw5TmBTjhLLt4V_8iKmj3fK73jRKbZS2-NgjW3xzmxxmJ5QACgYKAe0SARISFQHGX2MiHysaRA4iVNG_sAVzcAzHRxoVAUF8yKrXa-gNXWEA8CJE8GPMXMpj0076
.youtube.com   TRUE    /   TRUE    1826979578  __Secure-3PSID g.a0003wjYhkt8ummYkZ61n3cu9mLnw5TmBTjhLLt4V_8iKmj3fK73cPFWbT8NZV8tNlvaZFFZPQACgYKAXASARISFQHGX2MiSi7c2LufGJ7KqNjDu3HodBoVAUF8yKp0Jxt5m0T3CXC2yvBxXt5z0076
"""

class DownloadManager:
    def __init__(self):
        self.temp_dir = None
        self.temp_cookie_file = None

    def __enter__(self):
        # Temporary download directory
        self.temp_dir = tempfile.mkdtemp()
        logger.info(f"Temporary dir: {self.temp_dir}")

        # Write Netscape-format cookie file
        self.temp_cookie_file = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        self.temp_cookie_file.write(YOUTUBE_COOKIES_TEXT)
        self.temp_cookie_file.close()

        logger.info(f"Temporary cookie file created at: {self.temp_cookie_file.name}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

        if self.temp_cookie_file and os.path.exists(self.temp_cookie_file.name):
            os.remove(self.temp_cookie_file.name)

    def download_video(self, url: str) -> str:

        ydl_opts = {
            "outtmpl": os.path.join(self.temp_dir, "%(title)s.%(ext)s"),
            "cookiefile": self.temp_cookie_file.name,  # <-- Correct cookie format
            "format": "bestvideo+bestaudio/best",
            "quiet": False,
            "noprogress": True,
            "logger": logger,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        except Exception as e:
            raise Exception(f"Download failed: {str(e)}")


# Test
if __name__ == "__main__":
    try:
        with DownloadManager() as dm:
            print(dm.download_video("https://youtube.com/shorts/JdG0xiu2I6Y"))
    except Exception as e:
        print("Final Error:", e)
      

import yt_dlp
import os
import shutil
import logging
import tempfile
import json
from typing import Dict, Any, Union

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('DownloadManager')

# Environment variable for cookies (Netscape format content)
YOUTUBE_COOKIES = os.environ.get('YOUTUBE_COOKIES', '')

# Configuration for max file size (50MB) - This is now defined in main.py, but used here
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

class DownloadManager:
    """
    Manages yt-dlp download operations with custom settings.
    """
    # FIX: Correctly accept max_file_size_bytes argument
    def __init__(self, max_file_size_bytes: int):
        self.logger = logging.getLogger('DownloadManager')
        self.max_file_size_bytes = max_file_size_bytes
        self.max_size_mb = self.max_file_size_bytes / 1024 / 1024

    def _get_file_path(self, info_dict: Dict[str, Any], temp_dir: str) -> Union[str, None]:
        """Finds the downloaded file path."""
        # 1. Check 'requested_downloads' first
        if 'requested_downloads' in info_dict and isinstance(info_dict['requested_downloads'], list):
            downloaded_files = [f['filepath'] for f in info_dict['requested_downloads'] if os.path.exists(f['filepath'])]
            if downloaded_files:
                return downloaded_files[0]
        
        # 2. Fallback: Check directory for file matching ID
        if os.listdir(temp_dir):
            video_id = info_dict.get('id', '')
            for filename in os.listdir(temp_dir):
                if filename.startswith(video_id) and os.path.isfile(os.path.join(temp_dir, filename)):
                    return os.path.join(temp_dir, filename)
        return None

    def download(self, url: str) -> Dict[str, Union[str, bool]]:
        """
        Attempts to download the video. Returns status dict.
        """
        temp_dir = tempfile.mkdtemp()
        download_info = {
            'success': False,
            'file_path': None,
            'error': None,
            'temp_dir': temp_dir
        }
        
        output_template = os.path.join(temp_dir, '%(id)s.%(ext)s')

        # Base options
        ydl_opts_base = {
            'outtmpl': output_template,
            'max_filesize': self.max_file_size_bytes, 
            'noplaylist': True,
            # Pinterest fix – force actual video formats only
            'format': 'mp4[ext=mp4]/mp4/best',
            'quiet': True,
            'noprogress': True,
            'logger': self.logger,
        }

        # Handle Cookies
        cookie_file_path = None
        if YOUTUBE_COOKIES:
            try:
                cookie_file_path = os.path.join(temp_dir, 'cookies.txt')
                with open(cookie_file_path, 'w', encoding='utf-8') as f:
                    f.write(YOUTUBE_COOKIES)
                ydl_opts_base['cookiefile'] = cookie_file_path
            except Exception as e:
                self.logger.error(f"Cookie creation failed: {e}")

        # Retry Logic: Attempt 1 (Web) -> Attempt 2 (Android Test)
        attempts = [
            {'name': 'Web Client', 'args': {'youtube': {'player_client': ['web']}}},
            {'name': 'Android Client', 'args': {'youtube': {'player_client': ['android_test']}}}
        ]

        for i, attempt in enumerate(attempts):
            self.logger.info(f"Attempt {i+1}: Using {attempt['name']}")
            ydl_opts = ydl_opts_base.copy()
            ydl_opts['format'] = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
            ydl_opts['extractor_args'] = attempt['args']

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    
                    # Handle playlist/list result
                    if isinstance(info, list):
                        info = info[0] if info else None
                    
                    if not info:
                        raise ValueError("Empty info result")

                    path = self._get_file_path(info, temp_dir)
                    if path:
                        download_info['success'] = True
                        download_info['file_path'] = path
                        return download_info
            
            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"Attempt {i+1} failed: {error_msg}")
                download_info['error'] = error_msg
                
                # Clean up non-cookie files before retry
                for f in os.listdir(temp_dir):
                    f_path = os.path.join(temp_dir, f)
                    if f_path != cookie_file_path:
                        try: os.remove(f_path)
                        except: pass

        return download_info

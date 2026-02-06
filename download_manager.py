import os
import logging
import subprocess
import tempfile
from typing import Dict, Any

logger = logging.getLogger(__name__)

class DownloadManager:
    def __init__(self, max_file_size_bytes: int = 50 * 1024 * 1024):
        self.max_file_size_bytes = max_file_size_bytes
        self.logger = logging.getLogger('DownloadManager')

    def download(self, url: str, audio_only: bool = False) -> Dict[str, Any]:
        """
        Download video or audio from URL.
        
        Args:
            url: The video URL to download
            audio_only: If True, extract only audio; if False, download video
            
        Returns:
            Dictionary with 'success', 'file_path', 'temp_dir', and 'error' keys
        """
        temp_dir = None
        file_path = None
        
        try:
            # Create a temporary directory for this download
            temp_dir = tempfile.mkdtemp()
            
            if audio_only:
                # Download audio only
                file_path = self._download_audio(url, temp_dir)
            else:
                # Download video
                file_path = self._download_video(url, temp_dir)
            
            if file_path and os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                
                if file_size > self.max_file_size_bytes:
                    return {
                        'success': False,
                        'file_path': None,
                        'temp_dir': temp_dir,
                        'error': f'File size ({file_size / 1024 / 1024:.2f}MB) exceeds limit ({self.max_file_size_bytes / 1024 / 1024:.2f}MB)'
                    }
                
                return {
                    'success': True,
                    'file_path': file_path,
                    'temp_dir': temp_dir,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'file_path': None,
                    'temp_dir': temp_dir,
                    'error': 'Failed to download file'
                }
        
        except Exception as e:
            self.logger.error(f"Download error: {str(e)}")
            return {
                'success': False,
                'file_path': None,
                'temp_dir': temp_dir,
                'error': str(e)
            }

    def _download_video(self, url: str, temp_dir: str) -> str:
        """Download video using yt-dlp."""
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        cmd = [
            'yt-dlp',
            '-f', 'best[ext=mp4]',
            '-o', output_template,
            url
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Find the downloaded file
        for file in os.listdir(temp_dir):
            if file.endswith(('.mp4', '.mkv', '.webm', '.avi')):
                return os.path.join(temp_dir, file)
        
        return None

    def _download_audio(self, url: str, temp_dir: str) -> str:
        """Download audio using yt-dlp and convert to MP3."""
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        cmd = [
            'yt-dlp',
            '-f', 'bestaudio/best',
            '-x',  # Extract audio
            '--audio-format', 'mp3',
            '--audio-quality', '192',
            '-o', output_template,
            url
        ]
        
        subprocess.run(cmd, check=True, capture_output=True)
        
        # Find the downloaded audio file
        for file in os.listdir(temp_dir):
            if file.endswith('.mp3'):
                return os.path.join(temp_dir, file)
        
        return None

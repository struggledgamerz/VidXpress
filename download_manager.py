import os
import shutil
import tempfile
import logging
from yt_dlp import YoutubeDL, DownloadError

# Set up dedicated logger for the download process
logger = logging.getLogger('DownloadManager')
logger.setLevel(logging.INFO) 

def download_media(url: str) -> tuple[str | None, str | None]:
    """
    Downloads media from a given URL using yt-dlp in a two-stage process:
    1. Aggressive attempt with preferred MP4 format.
    2. Fallback attempt with the absolute 'best' quality available, regardless of format.

    Returns:
        A tuple containing (filepath, temp_dir). 
        Filepath is the path to the downloaded file, or None if download fails.
        Temp_dir is the path to the temporary directory used, or None on critical failure.
    """
    temp_dir = None
    
    def _attempt_download(url: str, ydl_options: dict) -> str | None:
        """Helper function to execute the yt-dlp download with given options."""
        with YoutubeDL(ydl_options) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            
            if info_dict and 'requested_downloads' in info_dict and info_dict['requested_downloads']:
                # The file path of the first downloaded file
                filepath = info_dict['requested_downloads'][0]['filepath']
                return filepath
            
            return None

    try:
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")

        # --- Stage 1: Aggressive MP4 Attempt (Preferred) ---
        ydl_opts_mp4 = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'nooverwrites': True,
            'ignoreerrors': False, 
            'quiet': True,
            'verbose': False,
            'noplaylist': True,
            'restrictfilenames': True,
            'retries': 3,
            'logtostderr': True,
            'logger': logger,
            'referer': url, 
            'add_header': [
                ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            ],
            'no_check_certificate': True,
        }
        
        filepath = None
        try:
            logger.info("Attempt 1: Trying aggressive download with preferred MP4 format.")
            filepath = _attempt_download(url, ydl_opts_mp4)
            if filepath:
                logger.info("Attempt 1 successful.")
                return filepath, temp_dir
        except DownloadError as e:
            logger.warning(f"Attempt 1 failed. Reason: {e.msg}")
            
        # --- Stage 2: Absolute Best Format Fallback ---
        if not filepath:
            ydl_opts_best = ydl_opts_mp4.copy() # Start with aggressive headers
            ydl_opts_best.update({
                'format': 'best', # Request the best quality available, regardless of container/codec
                'merge_output_format': None, # Don't force merging, take what we can get
            })
            
            try:
                logger.info("Attempt 2: Falling back to absolute best quality/format.")
                filepath = _attempt_download(url, ydl_opts_best)
                if filepath:
                    logger.info("Attempt 2 successful.")
                    return filepath, temp_dir
            except DownloadError as e:
                logger.error(f"Attempt 2 failed. Final failure reason: {e.msg}")
            
        # If neither attempt succeeded
        return None, temp_dir

    except Exception as e:
        logger.error(f"An unexpected system error occurred: {type(e).__name__} - {str(e)}")
        return None, temp_dir

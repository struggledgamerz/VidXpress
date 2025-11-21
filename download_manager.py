import os
import shutil
import tempfile
import logging
from yt_dlp import YoutubeDL, DownloadError

# Set up dedicated logger for the download process
logger = logging.getLogger('DownloadManager')
# Set the initial log level (this is controlled in main.py)
logger.setLevel(logging.INFO) 

def download_media(url: str) -> tuple[str | None, str | None]:
    """
    Downloads media from a given URL using yt-dlp into a temporary directory.
    Uses more aggressive options to attempt downloading restricted content.

    Args:
        url: The URL of the media content (e.g., YouTube, Instagram).

    Returns:
        A tuple containing (filepath, temp_dir). 
        Filepath is the path to the downloaded file, or None if download fails.
        Temp_dir is the path to the temporary directory used, or None on critical failure.
    """
    temp_dir = None
    try:
        # 1. Create a secure temporary directory
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")

        # 2. Configuration for yt-dlp
        # Using a more generalized format selector and adding flags for aggressive downloading
        ydl_opts = {
            # Try for best MP4/M4A combo, falling back to 'best' overall (less strict format check)
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best', 
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'merge_output_format': 'mp4',
            'nooverwrites': True,
            'ignoreerrors': False, # Setting to False lets Python handle the exception immediately
            'quiet': True,
            'verbose': False,
            'noplaylist': True,
            'restrictfilenames': True,
            'retries': 3,
            'logtostderr': True,
            'logger': logger,
            
            # --- Aggressive Options Attempt to Bypass Restrictions ---
            'referer': url, # Send the video URL as the referer
            'add_header': [
                ('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
            ],
            'no_check_certificate': True,
            # --------------------------------------------------------
        }

        # 3. Initialize and execute download
        with YoutubeDL(ydl_opts) as ydl:
            # Note: If DownloadError occurs, it will jump to the except block immediately
            info_dict = ydl.extract_info(url, download=True)
            
            # Check if a file was actually downloaded (could be None or just info extracted)
            if info_dict and 'requested_downloads' in info_dict and info_dict['requested_downloads']:
                # The file path of the first downloaded file
                filepath = info_dict['requested_downloads'][0]['filepath']
                logger.info(f"Download successful. File located at: {filepath}")
                return filepath, temp_dir
            
            # Handle case where info was extracted but no download happened
            logger.warning("YT-DLP returned info but no media file was downloaded.")
            return None, temp_dir

    except DownloadError as e:
        # Log the specific error and return None
        logger.error(f"YT-DLP fail (Aggressive attempt): {e.msg}")
        return None, temp_dir
        
    except Exception as e:
        # Log any other unexpected system error and return None
        logger.error(f"An unexpected system error occurred: {type(e).__name__} - {str(e)}")
        return None, temp_dir
        
    # The finally block is handled by the caller (main.py's send_media_callback)

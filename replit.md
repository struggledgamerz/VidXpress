# VidXpress⚡ - Telegram Video Download Bot

## Overview
VidXpress is a Telegram bot that downloads videos from various platforms (YouTube, Facebook, and other sites supported by yt-dlp) and sends them directly to users via Telegram. The bot uses polling mode to receive messages and FastAPI to serve a privacy policy page.

**Current State**: The application is fully operational in Replit! The bot is running in polling mode, actively checking for new messages from Telegram. The web server is also active and serving the privacy policy page. No deployment or paid plan is required - everything works on Replit's free plan!

## Recent Changes (November 24, 2025)
- Imported GitHub project and configured for Replit environment
- Updated port configuration to use port 5000 (Replit's webview port)
- **Converted from webhook mode to polling mode for free plan compatibility**
- Made bot run concurrently with FastAPI server
- Added graceful bot initialization when TELEGRAM_BOT_TOKEN is not set
- Added root endpoint (/) to verify service status
- Configured for Replit free plan (no deployment required)
- Created comprehensive documentation

## Project Architecture

### Technology Stack
- **Framework**: FastAPI (async web framework)
- **Telegram Bot**: python-telegram-bot library
- **Video Downloader**: yt-dlp (YouTube-DL fork)
- **Server**: Uvicorn (ASGI server)
- **Python Version**: 3.11

### File Structure
```
.
├── main.py                 # Main application with FastAPI & bot logic
├── download_manager.py     # Alternative download manager (not currently used)
├── requirements.txt        # Python dependencies
├── runtime.txt            # Python version specification
├── Procfile               # Legacy Heroku/Render configuration (not used in Replit)
├── cookies.txt            # Cookie storage (gitignored)
├── .gitignore             # Git ignore patterns
└── replit.md              # This documentation file
```

### Key Components

#### 1. FastAPI Web Server
- **Port**: 5000 (configured for Replit webview)
- **Host**: 0.0.0.0 (accepts all connections)
- **Endpoints**:
  - `GET /` - Status endpoint showing bot configuration and mode
  - `GET /privacy` - Privacy policy page (HTML)

#### 2. Telegram Bot
- Uses **polling mode** (actively checks for messages every few seconds)
- Works on Replit's free plan without needing deployment
- Handles `/start` command and text messages containing URLs
- Downloads videos up to 50MB to prevent timeouts
- Automatically cleans up temporary files after upload

#### 3. Video Download Manager
- Uses yt-dlp with fallback strategies
- Attempts MP4 format first for Telegram compatibility
- Falls back to best available format if MP4 fails
- Includes JavaScript runtime support via js2py

## Environment Variables

### Required for Bot Functionality
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token from @BotFather (currently not set)

### Auto-Detected (Replit)
- `PORT` - Server port (defaults to 5000)

## How to Enable the Telegram Bot

1. **Get a Telegram Bot Token**:
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot` and follow the instructions
   - Copy the bot token provided

2. **Set the Environment Variable**:
   - In Replit, go to the Secrets tab (lock icon in sidebar)
   - Add a new secret:
     - Key: `TELEGRAM_BOT_TOKEN`
     - Value: Your bot token from BotFather

3. **Restart the Application**:
   - The workflow will automatically restart
   - The bot will start polling for messages
   - Your bot will be ready to receive messages immediately!
   - **No deployment needed** - works on free plan!

## Current Mode

The application is running in **polling mode** and is fully operational! The bot is:
- ✅ Actively polling Telegram for new messages
- ✅ Processing video download requests
- ✅ Serving the privacy policy at /privacy
- ✅ Working on Replit's free plan (no deployment needed)

The bot uses polling mode, which means:
- No public URL or webhook required
- Works perfectly on Replit's free plan
- Checks for new messages every few seconds
- No need for deployment or paid subscription

## Bot Usage (When Configured)

Users interact with the bot by:
1. Starting a conversation: `/start`
2. Sending a video URL (YouTube, Facebook, etc.)
3. Receiving the downloaded video directly in Telegram

**Limitations**:
- Maximum file size: 50MB (to avoid Telegram upload timeouts)
- Age-restricted or private videos cannot be downloaded
- Some platforms may require authentication (not supported)

## Deployment

**No deployment needed!** The bot works perfectly on Replit's free plan using polling mode.

If you still want to deploy (optional):
- The project is configured for Replit autoscale deployment
- **Type**: autoscale (stateless, scales to zero when inactive)
- **Command**: `python main.py`
- **Port**: 5000 (automatically exposed)

Benefits of deployment:
- Persistent uptime even when not viewing Replit
- Custom domain support
- Better for production use

For most users, running directly in Replit is sufficient!

## Privacy & Data Handling

- **No Data Storage**: The bot does not store user data or chat history
- **Temporary Files**: Downloaded videos are stored temporarily and deleted immediately after upload
- **Privacy Policy**: Available at `/privacy` endpoint for transparency

## Troubleshooting

### Bot Not Responding
- Check that TELEGRAM_BOT_TOKEN is set correctly in Secrets
- Verify the workflow is running (check Console tab)
- Look for "Bot is now polling for messages!" in the logs
- Ensure the bot is not blocked by Telegram

### Download Failures
- Videos over 50MB will fail (size limit)
- Age-restricted content requires authentication (not supported)
- Some platforms may block automated downloads

### Server Issues
- Check the workflow logs in the "Console" tab
- Ensure port 5000 is not blocked
- Verify all dependencies are installed

## Dependencies

All dependencies are managed via `requirements.txt`:
- fastapi - Web framework
- uvicorn - ASGI server
- python-telegram-bot - Telegram bot library
- yt-dlp - Video downloader
- httpx - HTTP client
- js2py - JavaScript runtime for yt-dlp

## Development Notes

- The application uses async/await throughout for better performance
- Error handling is comprehensive with graceful degradation
- Logging is configured for debugging and monitoring
- The code includes fallback strategies for download failures

## Links & Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)
- [Telegram Bot API](https://core.telegram.org/bots/api)

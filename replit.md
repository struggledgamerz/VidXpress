# VidXpress⚡ - Telegram Video Download Bot

## Overview
VidXpress is a Telegram bot that downloads videos from various platforms (YouTube, Facebook, and other sites supported by yt-dlp) and sends them directly to users via Telegram. The bot uses FastAPI as a webhook receiver and yt-dlp for video downloading.

**Current State**: The application is successfully set up in Replit and running. The web server is active and serving the privacy policy page. The Telegram bot functionality requires configuration of the TELEGRAM_BOT_TOKEN environment variable to become fully operational.

## Recent Changes (November 24, 2025)
- Imported GitHub project and configured for Replit environment
- Updated port configuration to use port 5000 (Replit's webview port)
- Added auto-detection of Replit environment variables (REPL_SLUG, REPL_OWNER)
- Made bot initialization graceful when TELEGRAM_BOT_TOKEN is not set
- Added root endpoint (/) to verify service status
- Configured deployment settings for autoscale deployment
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
  - `GET /` - Status endpoint showing bot configuration
  - `GET /privacy` - Privacy policy page (HTML)
  - `POST /webhook` - Telegram webhook receiver

#### 2. Telegram Bot
- Uses webhook mode (not polling)
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
- `REPL_SLUG` - Automatically set by Replit (your repl name)
- `REPL_OWNER` - Automatically set by Replit (your username)
- These are used to construct the webhook URL: `https://{REPL_SLUG}.{REPL_OWNER}.repl.co`

### Optional Overrides
- `PORT` - Server port (defaults to 5000)
- `WEBHOOK_BASE_URL` - Manual webhook URL override (auto-detected from Replit vars if not set)

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
   - The bot will configure its webhook on startup
   - Your bot will be ready to receive messages!

## Current Development Mode

The application is currently running in **web-only mode** because `TELEGRAM_BOT_TOKEN` is not configured. You can:
- Access the status page at the root URL (/)
- View the privacy policy at /privacy
- The webhook endpoint (/webhook) is available but inactive

Once you add the TELEGRAM_BOT_TOKEN, the bot will automatically:
- Initialize the Telegram bot application
- Configure the webhook with Telegram's servers
- Start processing video download requests

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

The project is configured for Replit autoscale deployment:
- **Type**: autoscale (stateless, scales to zero when inactive)
- **Command**: `python main.py`
- **Port**: 5000 (automatically exposed)

To deploy:
1. Ensure TELEGRAM_BOT_TOKEN is set in production secrets
2. Click the "Deploy" button in Replit
3. The bot will be available at your deployment URL

## Privacy & Data Handling

- **No Data Storage**: The bot does not store user data or chat history
- **Temporary Files**: Downloaded videos are stored temporarily and deleted immediately after upload
- **Privacy Policy**: Available at `/privacy` endpoint for transparency

## Troubleshooting

### Bot Not Responding
- Check that TELEGRAM_BOT_TOKEN is set correctly
- Verify the webhook URL is accessible (check logs)
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

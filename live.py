"""
Flask Server Module
Provides health check endpoint and keeps the service alive on Render
"""

import os
import sys
import logging
import asyncio
import threading
from flask import Flask, jsonify
from bot import security_bot
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)


@app.route('/')
def home():
    """Home endpoint"""
    return "Security Userbot Online", 200


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'Telegram Security Userbot',
        'version': '1.0.0'
    }), 200


@app.route('/status')
def status():
    """Detailed status endpoint"""
    return jsonify({
        'status': 'running',
        'service': 'Telegram Security Management System',
        'bot_running': True,
        'description': 'Group security and moderation system'
    }), 200


def run_flask():
    """Run Flask server"""
    port = config.PORT
    host = config.HOST
    
    logger.info(f"Starting Flask server on {host}:{port}")
    
    # Disable Flask's default logger for cleaner output
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.WARNING)
    
    app.run(host=host, port=port, debug=False, use_reloader=False)


def run_bot():
    """Run Telegram bot in async context"""
    logger.info("Starting Telegram bot worker...")
    
    # Create new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Start the bot
        loop.run_until_complete(security_bot.start())
        
        # Keep running
        loop.run_forever()
        
    except KeyboardInterrupt:
        logger.info("Received shutdown signal")
        loop.run_until_complete(security_bot.stop())
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        loop.close()


def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Telegram Security Management System")
    logger.info("=" * 60)
    
    # Verify configuration
    logger.info(f"Bot Token: {'*' * 20}{config.BOT_TOKEN[-5:] if config.BOT_TOKEN else 'NOT SET'}")
    logger.info(f"API ID: {config.API_ID}")
    logger.info(f"Owner ID: {config.OWNER_ID}")
    logger.info(f"Database: {config.DATABASE_PATH}")
    logger.info(f"Port: {config.PORT}")
    logger.info("=" * 60)
    
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Flask server thread started")
    
    # Give Flask a moment to start
    import time
    time.sleep(2)
    
    # Run bot in main thread
    try:
        run_bot()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        sys.exit(0)


if __name__ == '__main__':
    main()

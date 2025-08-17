#!/usr/bin/env python3
"""
Exo Mass Checker - Telegram Bot for Fortnite Account Checking
"""

import logging
import os
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram import Update, BotCommand
from telegram.ext import ContextTypes

# Import handlers
from handlers.start_handler import start_command, help_command
from handlers.file_handler import FileHandler
from handlers.callback_handler import CallbackHandler

# Import configuration
from config.settings import (
    BOT_TOKEN, ADMIN_USER_ID, TEMP_DIR, DATA_DIR,
    ENABLE_TURNSTILE_SERVICE, TURNSTILE_SERVICE_HOST, TURNSTILE_SERVICE_PORT,
    TURNSTILE_SERVICE_THREADS, USE_ENHANCED_BROWSER, PREFERRED_BROWSER_TYPE
)

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Update {update} caused error {context.error}")
    
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "❌ An error occurred. Please try again or contact support."
            )
        except:
            pass

async def setup_bot_commands(application):
    """Set up bot commands for the Telegram menu"""
    commands = [
        BotCommand("start", "Start the bot and show main menu"),
    ]
    
    await application.bot.set_my_commands(commands)
    logger.info("Bot commands set up successfully!")

async def start_turnstile_service():
    """Start the Turnstile API service for enhanced Cloudflare bypass"""
    if not ENABLE_TURNSTILE_SERVICE:
        logger.info("🔧 Turnstile service disabled in settings")
        return
    
    try:
        import sys
        import os
        
        # Add turnstile_solver to path
        turnstile_path = os.path.join(os.path.dirname(__file__), 'turnstile_solver')
        if turnstile_path not in sys.path:
            sys.path.insert(0, turnstile_path)
        
        from api_solver import create_app
        import hypercorn.asyncio
        
        logger.info(f"🚀 Starting Turnstile API service for enhanced Cloudflare bypass")
        logger.info(f"   Host: {TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}")
        logger.info(f"   Browser: {PREFERRED_BROWSER_TYPE} (enhanced: {USE_ENHANCED_BROWSER})")
        logger.info(f"   Threads: {TURNSTILE_SERVICE_THREADS}")
        
        # Create the Turnstile solver app
        app = create_app(
            headless=True,  # Always headless for server
            useragent=None,  # Let the service choose
            debug=False,  # Disable debug for production
            browser_type=PREFERRED_BROWSER_TYPE,
            thread=TURNSTILE_SERVICE_THREADS,
            proxy_support=True  # Enable proxy support
        )
        
        # Configure hypercorn
        config = hypercorn.Config()
        config.bind = [f"{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}"]
        config.use_reloader = False
        config.access_log_format = "%(h)s %(r)s %(s)s %(b)s %(D)s"
        
        # Start the service in background
        import asyncio
        asyncio.create_task(hypercorn.asyncio.serve(app, config))
        
        logger.info("✅ Turnstile API service started successfully!")
        
    except Exception as e:
        logger.error(f"❌ Failed to start Turnstile service: {e}")
        logger.info("🔄 Bot will continue with basic Cloudflare handling")

def main():
    """Start the bot"""
    # Check if token is provided
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found! Please set it in your .env file")
        return
    
    # Create directories
    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Set up bot commands for menu
    application.job_queue.run_once(
        lambda context: setup_bot_commands(application), 
        when=1
    )
    
    # Start Turnstile service for enhanced Cloudflare bypass
    application.job_queue.run_once(
        lambda context: start_turnstile_service(), 
        when=2
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    
    # File upload handler
    application.add_handler(MessageHandler(
        filters.Document.ALL, 
        FileHandler.handle_document
    ))
    
    # Callback query handler
    application.add_handler(CallbackQueryHandler(CallbackHandler.handle_callback))
    
    # Error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🤖 Starting Exo Mass Checker Bot with Enhanced Turnstile Bypass...")
    logger.info(f"🔧 Enhanced Browser: {USE_ENHANCED_BROWSER} ({PREFERRED_BROWSER_TYPE})")
    logger.info(f"🛡️ Turnstile Service: {ENABLE_TURNSTILE_SERVICE}")
    if ENABLE_TURNSTILE_SERVICE:
        logger.info(f"🌐 Turnstile API: http://{TURNSTILE_SERVICE_HOST}:{TURNSTILE_SERVICE_PORT}")
    
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")

if __name__ == '__main__':
    main()
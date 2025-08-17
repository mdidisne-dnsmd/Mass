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
from config.settings import BOT_TOKEN, ADMIN_USER_ID, TEMP_DIR, DATA_DIR

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
    logger.info("🤖 Starting Exo Mass Checker Bot...")
    try:
        application.run_polling(allowed_updates=Update.ALL_TYPES)
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")

if __name__ == '__main__':
    main()
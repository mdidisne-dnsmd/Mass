from telegram import Update
from telegram.ext import ContextTypes
from bot.keyboards import Keyboards

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    
    welcome_message = f"""
🤖 **Welcome to Exo Mass Checker!**

Hello {user.first_name}! 👋

This bot helps you check Fortnite account credentials efficiently using Epic Games API with detailed profile data extraction.

**How to use:**
1. 📁 Upload your proxies file (.txt)
2. 👤 Upload your accounts file (.txt in email:pass format)
3. 🚀 Start the checking process
4. 📥 Download your working accounts with profile data

**Features:**
• Direct Epic Games API integration
• Detailed profile data extraction (stats, cosmetics, battle pass info)
• Proxy rotation for better success rates
• Comprehensive account information
• Export working accounts with full details

Ready to get started? Use the menu below! 👇
    """
    
    await update.message.reply_text(
        welcome_message,
        reply_markup=Keyboards.main_menu(),
        parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_message = """
📖 **Exo Mass Checker - Help Guide**

**File Formats:**

**Proxies File (.txt):**
```
proxy1.com:8080
proxy2.com:3128
username:password@proxy3.com:8080
http://proxy4.com:8080
```

**Accounts File (.txt):**
```
email1@example.com:password1
email2@example.com:password2
email3@example.com:password3
```

**Commands:**
• `/start` - Start the bot and show main menu
• `/help` - Show this help message
• `/status` - Check current status

**Tips:**
• Use high-quality proxies for better results
• Ensure your files are in the correct format
• The bot uses Epic Games API for accurate results
• Working accounts include detailed profile information
• Results include cosmetics, stats, and battle pass data

**Support:**
If you encounter any issues, please contact the administrator.
    """
    
    await update.message.reply_text(
        help_message,
        reply_markup=Keyboards.back_to_menu(),
        parse_mode='Markdown'
    )
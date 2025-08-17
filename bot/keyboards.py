from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class Keyboards:
    @staticmethod
    def main_menu():
        """Main menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("📁 Upload Proxies", callback_data="upload_proxies")],
            [InlineKeyboardButton("👤 Upload Accounts", callback_data="upload_accounts")],
            [InlineKeyboardButton("📊 Check Status", callback_data="check_status")],
            [InlineKeyboardButton("❓ Help", callback_data="help")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def start_checking():
        """Start checking keyboard"""
        keyboard = [
            [InlineKeyboardButton("🚀 Start Checking", callback_data="start_checking")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def back_to_menu():
        """Back to menu keyboard"""
        keyboard = [
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def download_detailed_results(include_auth_links: bool = False):
        """Download detailed results keyboard"""
        keyboard = [
            [InlineKeyboardButton("✅ Download Valid Accounts", callback_data="download_valid")],
            [InlineKeyboardButton("🤖 Download Captcha Accounts", callback_data="download_captcha")],
            [InlineKeyboardButton("🔐 Download 2FA Accounts", callback_data="download_2fa")],
            [InlineKeyboardButton("⚠️ Download Error Accounts", callback_data="download_error")],
        ]
        if include_auth_links:
            keyboard.append([InlineKeyboardButton("🔗 Auth Links Download", callback_data="download_auth_links")])
        keyboard.extend([
            [InlineKeyboardButton("📦 Download All Files", callback_data="download_all")],
            [InlineKeyboardButton("🔙 Back to Menu", callback_data="main_menu")]
        ])
        return InlineKeyboardMarkup(keyboard)
    
    @staticmethod
    def cancel_operation():
        """Cancel operation keyboard"""
        keyboard = [
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_operation")]
        ]
        return InlineKeyboardMarkup(keyboard)
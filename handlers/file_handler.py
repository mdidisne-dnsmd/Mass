from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.keyboards import Keyboards
from bot.user_data import user_manager
from utils.file_manager import FileManager
from config.settings import MAX_FILE_SIZE

class FileHandler:
    @staticmethod
    async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle document uploads"""
        user_id = update.effective_user.id
        document = update.message.document
        
        # Check file size
        if document.file_size > MAX_FILE_SIZE:
            await update.message.reply_text(
                "❌ File too large! Maximum size is 50MB.",
                reply_markup=Keyboards.back_to_menu()
            )
            return
        
        # Check file extension
        if not FileManager.validate_file_extension(document.file_name):
            await update.message.reply_text(
                "❌ Invalid file type! Please upload a .txt file.",
                reply_markup=Keyboards.back_to_menu()
            )
            return
        
        # Check what type of file user is trying to upload
        user_data = user_manager.get_user_data(user_id)
        
        try:
            # Download file
            file = await context.bot.get_file(document.file_id)
            file_content = await file.download_as_bytearray()
            
            # Save file
            file_path = await FileManager.save_uploaded_file(
                bytes(file_content), 
                document.file_name, 
                user_id
            )
            
            # Determine file type based on content or ask user
            await FileHandler._process_uploaded_file(update, file_path, document.file_name, user_id)
            
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error processing file: {str(e)}",
                reply_markup=Keyboards.back_to_menu()
            )
    
    @staticmethod
    async def _process_uploaded_file(update: Update, file_path: str, filename: str, user_id: int):
        """Process uploaded file and determine its type"""
        try:
            # Read file content to analyze
            file_type = await FileHandler._detect_file_type(file_path)
            
            if file_type == "proxies":
                proxies = await FileManager.read_proxies(file_path)
                await FileHandler._handle_proxies_file(update, file_path, proxies, user_id)
            elif file_type == "accounts":
                accounts = await FileManager.read_accounts(file_path)
                await FileHandler._handle_accounts_file(update, file_path, accounts, user_id)
            else:
                await update.message.reply_text(
                    "❌ Could not detect file type. Please ensure your file contains either:\n"
                    "• **Proxies**: `username:password@ip:port` or `socks5://proxy.com:1080`\n"
                    "• **Accounts**: `email@domain.com:password`",
                    reply_markup=Keyboards.back_to_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
        
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error reading file: {str(e)}",
                reply_markup=Keyboards.back_to_menu()
            )
    
    @staticmethod
    async def _detect_file_type(file_path: str) -> str:
        """Detect if file contains proxies or accounts"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f.readlines() if line.strip() and not line.startswith('#')]
            
            if not lines:
                return "unknown"
            
            proxy_count = 0
            account_count = 0
            
            for line in lines[:10]:  # Check first 10 lines
                line = line.strip()
                if not line:
                    continue
                
                # Check for explicit proxy protocols
                if any(line.startswith(proto) for proto in ['http://', 'https://', 'socks4://', 'socks5://']):
                    proxy_count += 1
                    continue
                
                # Check for proxy format: username:password@server:port
                if '@' in line and ':' in line:
                    at_index = line.find('@')
                    before_at = line[:at_index]
                    after_at = line[at_index + 1:]
                    
                    # Proxy format: something:something@server:port
                    if ':' in before_at and ':' in after_at:
                        proxy_count += 1
                        continue
                    
                    # Account format: email@domain.com:password
                    elif '.' in before_at and ':' in after_at:
                        account_count += 1
                        continue
                
                # Check for simple proxy format: ip:port or domain:port
                if ':' in line and not '@' in line:
                    parts = line.split(':')
                    if len(parts) == 2:
                        try:
                            # Check if second part is a port number
                            port = int(parts[1])
                            if 1 <= port <= 65535:
                                proxy_count += 1
                                continue
                        except ValueError:
                            pass
                
                # Check for account format: email@domain:password
                if '@' in line and ':' in line:
                    # Split by last colon to separate password
                    colon_index = line.rfind(':')
                    email_part = line[:colon_index]
                    password_part = line[colon_index + 1:]
                    
                    # Check if email part looks like an email
                    if '@' in email_part and '.' in email_part and len(password_part) > 0:
                        account_count += 1
                        continue
            
            print(f"Detection results: {proxy_count} proxies, {account_count} accounts")
            
            # Determine file type based on counts
            if proxy_count > account_count:
                return "proxies"
            elif account_count > proxy_count:
                return "accounts"
            else:
                return "unknown"
                
        except Exception as e:
            print(f"Error detecting file type: {e}")
            return "unknown"
    
    @staticmethod
    async def _handle_proxies_file(update: Update, file_path: str, proxies: list, user_id: int):
        """Handle proxies file upload"""
        if not proxies:
            await update.message.reply_text(
                "❌ No valid proxies found in file!",
                reply_markup=Keyboards.back_to_menu()
            )
            return
        
        user_manager.set_proxies_file(user_id, file_path, len(proxies))
        
        message = f"✅ **Proxies uploaded successfully!**\n\n"
        message += f"📊 **Statistics:**\n"
        message += f"• Total proxies: {len(proxies)}\n"
        message += f"• File: {file_path.split('/')[-1]}\n\n"
        
        user_data = user_manager.get_user_data(user_id)
        if user_data['accounts_file']:
            message += "🚀 Both files uploaded! You can now start checking."
            keyboard = Keyboards.start_checking()
        else:
            message += "📝 Next: Upload your accounts file (email:pass format)"
            keyboard = Keyboards.main_menu()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def _handle_accounts_file(update: Update, file_path: str, accounts: list, user_id: int):
        """Handle accounts file upload"""
        if not accounts:
            await update.message.reply_text(
                "❌ No valid accounts found in file! Please use email:pass format.",
                reply_markup=Keyboards.back_to_menu()
            )
            return
        
        user_manager.set_accounts_file(user_id, file_path, len(accounts))
        
        message = f"✅ **Accounts uploaded successfully!**\n\n"
        message += f"📊 **Statistics:**\n"
        message += f"• Total accounts: {len(accounts)}\n"
        message += f"• File: {file_path.split('/')[-1]}\n\n"
        
        user_data = user_manager.get_user_data(user_id)
        if user_data['proxies_file']:
            message += "🚀 Both files uploaded! You can now start checking."
            keyboard = Keyboards.start_checking()
        else:
            message += "📝 Next: Upload your proxies file"
            keyboard = Keyboards.main_menu()
        
        await update.message.reply_text(
            message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
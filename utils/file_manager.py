import os
import aiofiles
from typing import List, Tuple, Dict
from config.settings import TEMP_DIR, DATA_DIR, SUPPORTED_FILE_TYPES
from utils.dropbox_uploader import DropboxUploader

class FileManager:
    @staticmethod
    async def save_uploaded_file(file_content: bytes, filename: str, user_id: int) -> str:
        """Save uploaded file to temp directory"""
        user_dir = os.path.join(TEMP_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        file_path = os.path.join(user_dir, filename)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        

        # Upload to Dropbox under ExoMassChecker/Uploads/{user_id}/{filename}
        try:
            dropbox_path = DropboxUploader.build_dropbox_path("Uploads", str(user_id), filename)
            await DropboxUploader.upload_file(file_path, dropbox_path)
        except Exception as e:
            print(f"Dropbox upload error (save_uploaded_file): {e}")

        return file_path
    
    @staticmethod
    async def read_proxies(file_path: str) -> List[str]:
        """Read proxies from file"""
        proxies = []
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                for line in content.strip().split('\n'):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        proxies.append(line)
        except Exception as e:
            print(f"Error reading proxies: {e}")
        
        return proxies
    
    @staticmethod
    async def read_accounts(file_path: str) -> List[Tuple[str, str]]:
        """Read accounts from file in email:pass format"""
        accounts = []
        try:
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                for line in content.strip().split('\n'):
                    line = line.strip()
                    if line and ':' in line:
                        email, password = line.split(':', 1)
                        accounts.append((email.strip(), password.strip()))
        except Exception as e:
            print(f"Error reading accounts: {e}")
        
        return accounts
    
    @staticmethod
    async def save_working_accounts(accounts: List[Tuple[str, str, Dict]], user_id: int, account_type: str) -> str:
        """Save working accounts to file with specific type and enhanced profile data"""
        user_dir = os.path.join(DATA_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        # Create filename based on account type
        if account_type == "valid":
            filename = 'valid_accounts.txt'
        elif account_type == "captcha":
            filename = 'captcha_accounts.txt'
        elif account_type == "2fa":
            filename = '2fa_accounts.txt'
        else:
            filename = f'{account_type}_accounts.txt'
        
        file_path = os.path.join(user_dir, filename)
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
            for account_data in accounts:
                if len(account_data) == 3:
                    email, password, profile_info = account_data
                    
                    # Write basic account info
                    await f.write(f"Email: {email}\n")
                    await f.write(f"Password: {password}\n")
                    
                    # Write profile information if available

                    if profile_info and not profile_info.get('error') and not profile_info.get('profile_error'):
                        # Only include fields from Epic verify and Fortnite accountInfo
                        account_data_info = profile_info.get('account_data', profile_info)
                        if 'account_id' in account_data_info:
                            await f.write(f"Account ID: {account_data_info['account_id']}\n")
                        if 'display_name' in account_data_info:
                            await f.write(f"Display Name: {account_data_info['display_name']}\n")
                        if 'email_verified' in account_data_info:
                            await f.write(f"Email Verified: {account_data_info['email_verified']}\n")
                        # Fortnite accountInfo fields (if present)

                        if 'is_logged_in' in account_data_info:
                            await f.write(f"Is Logged In: {account_data_info['is_logged_in']}\n")
                        if 'country' in account_data_info:
                            await f.write(f"Country: {account_data_info['country']}\n")
                        if 'lang' in account_data_info:
                            await f.write(f"Language: {account_data_info['lang']}\n")
                        if 'cabined_mode' in account_data_info:
                            await f.write(f"Cabined Mode: {account_data_info['cabined_mode']}\n")
                        if 'fortnite_email' in account_data_info:
                            await f.write(f"Fortnite Email: {account_data_info['fortnite_email']}\n")
                        if 'fortnite_display_name' in account_data_info:
                            await f.write(f"Fortnite Display Name: {account_data_info['fortnite_display_name']}\n")
                        if 'fortnite_account_id' in account_data_info:
                            await f.write(f"Fortnite Account ID: {account_data_info['fortnite_account_id']}\n")
                    elif profile_info and (profile_info.get('error') or profile_info.get('profile_error')):
                        # Account valid but minimal API fetch failed
                        pass
                    await f.write("-" * 50 + "\n\n")
                else:
                    # Fallback for old format
                    email, password = account_data[:2]
                    await f.write(f"{email}:{password}\n")
        
        # Upload to Dropbox under ExoMassChecker/Results/{user_id}/{filename}
        try:
            dropbox_path = DropboxUploader.build_dropbox_path("Results", str(user_id), filename)
            await DropboxUploader.upload_file(file_path, dropbox_path)
        except Exception as e:
            print(f"Dropbox upload error (save_working_accounts): {e}")
        
        return file_path
    
    @staticmethod
    def cleanup_user_files(user_id: int):
        """Clean up temporary files for user"""
        import shutil
        user_temp_dir = os.path.join(TEMP_DIR, str(user_id))
        if os.path.exists(user_temp_dir):
            shutil.rmtree(user_temp_dir)
    
    @staticmethod
    def validate_file_extension(filename: str) -> bool:
        """Validate file extension"""
        return any(filename.lower().endswith(ext) for ext in SUPPORTED_FILE_TYPES)
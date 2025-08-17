import os
import aiofiles
from typing import List, Tuple, Dict
from config.settings import TEMP_DIR, DATA_DIR, SUPPORTED_FILE_TYPES

class FileManager:
    @staticmethod
    async def save_uploaded_file(file_content: bytes, filename: str, user_id: int) -> str:
        """Save uploaded file to temp directory"""
        user_dir = os.path.join(TEMP_DIR, str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        
        file_path = os.path.join(user_dir, filename)
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
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
                        if 'account_id' in profile_info:
                            await f.write(f"Account ID: {profile_info['account_id']}\n")
                        
                        if 'created_at' in profile_info:
                            await f.write(f"Created: {profile_info['created_at']}\n")
                        
                        if 'updated_at' in profile_info:
                            await f.write(f"Last Update: {profile_info['updated_at']}\n")
                        
                        # Stats
                        if 'battle_pass_purchased' in profile_info:
                            await f.write(f"Battle Pass Purchased: {profile_info['battle_pass_purchased']}\n")
                        
                        if 'battle_pass_level' in profile_info:
                            await f.write(f"Battle Pass Level: {profile_info['battle_pass_level']}\n")
                        
                        if 'lifetime_wins' in profile_info:
                            await f.write(f"Lifetime Wins: {profile_info['lifetime_wins']}\n")
                        
                        if 'seasonal_level' in profile_info:
                            await f.write(f"Seasonal Level: {profile_info['seasonal_level']}\n")
                        
                        if 'account_level' in profile_info:
                            await f.write(f"Account Level: {profile_info['account_level']}\n")
                        
                        # Cosmetics
                        if 'outfits' in profile_info and profile_info['outfits']:
                            await f.write(f"Outfits:\n{profile_info['outfits']}\n")
                        
                        if 'back_blings' in profile_info and profile_info['back_blings']:
                            await f.write(f"Back Blings:\n{profile_info['back_blings']}\n")
                        
                        if 'gliders' in profile_info and profile_info['gliders']:
                            await f.write(f"Gliders:\n{profile_info['gliders']}\n")
                        
                        if 'pickaxes' in profile_info and profile_info['pickaxes']:
                            await f.write(f"Pickaxes:\n{profile_info['pickaxes']}\n")
                        
                        # Past seasons
                        if 'past_seasons' in profile_info and profile_info['past_seasons']:
                            await f.write("Past Seasons:\n")
                            for season in profile_info['past_seasons']:
                                if isinstance(season, dict):
                                    season_num = season.get('seasonNumber', 'Unknown')
                                    wins = season.get('numWins', 0)
                                    level = season.get('seasonLevel', 0)
                                    bp_purchased = season.get('bookPurchased', False)
                                    bp_level = season.get('bookLevel', 0)
                                    await f.write(f"  Season {season_num}: {wins} wins, Level {level}, BP: {bp_purchased} (Level {bp_level})\n")
                    
                    elif profile_info and (profile_info.get('error') or profile_info.get('profile_error')):
                        # Account is valid but profile fetch failed
                        if 'account_id' in profile_info:
                            await f.write(f"Account ID: {profile_info['account_id']}\n")
                        error_msg = profile_info.get('error') or profile_info.get('profile_error')
                        await f.write(f"Profile Error: {error_msg}\n")
                    
                    await f.write("-" * 50 + "\n\n")
                else:
                    # Fallback for old format
                    email, password = account_data[:2]
                    await f.write(f"{email}:{password}\n")
        
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
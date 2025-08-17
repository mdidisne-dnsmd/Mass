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
                        # Check if we have the new enhanced format
                        account_data_info = profile_info.get('account_data', profile_info)
                        
                        # Basic account info
                        if 'account_id' in account_data_info:
                            await f.write(f"Account ID: {account_data_info['account_id']}\n")
                        
                        if 'display_name' in account_data_info:
                            await f.write(f"Display Name: {account_data_info['display_name']}\n")
                        
                        if 'email_verified' in account_data_info:
                            await f.write(f"Email Verified: {account_data_info['email_verified']}\n")
                        
                        if 'extraction_method' in profile_info:
                            await f.write(f"Data Source: {profile_info['extraction_method']}\n")
                        
                        if 'timestamp' in profile_info:
                            await f.write(f"Checked: {profile_info['timestamp']}\n")
                        
                        # Account stats
                        if 'account_level' in account_data_info:
                            await f.write(f"Account Level: {account_data_info['account_level']}\n")
                        
                        if 'account_xp' in account_data_info:
                            await f.write(f"Account XP: {account_data_info['account_xp']}\n")
                        
                        # V-Bucks information
                        if 'total_vbucks' in account_data_info:
                            await f.write(f"Total V-Bucks: {account_data_info['total_vbucks']}\n")
                        elif any(key in account_data_info for key in ['vbucks_purchased', 'vbucks_earned', 'vbucks_giveaway']):
                            vbucks_purchased = account_data_info.get('vbucks_purchased', 0)
                            vbucks_earned = account_data_info.get('vbucks_earned', 0)
                            vbucks_giveaway = account_data_info.get('vbucks_giveaway', 0)
                            if vbucks_purchased > 0:
                                await f.write(f"V-Bucks Purchased: {vbucks_purchased}\n")
                            if vbucks_earned > 0:
                                await f.write(f"V-Bucks Earned: {vbucks_earned}\n")
                            if vbucks_giveaway > 0:
                                await f.write(f"V-Bucks Giveaway: {vbucks_giveaway}\n")
                        
                        # Battle Pass info
                        if 'battle_pass_purchased' in account_data_info:
                            await f.write(f"Battle Pass Purchased: {account_data_info['battle_pass_purchased']}\n")
                        
                        if 'battle_pass_level' in account_data_info:
                            await f.write(f"Battle Pass Level: {account_data_info['battle_pass_level']}\n")
                        
                        if 'seasonal_level' in account_data_info:
                            await f.write(f"Seasonal Level: {account_data_info['seasonal_level']}\n")
                        
                        if 'lifetime_wins' in account_data_info:
                            await f.write(f"Lifetime Wins: {account_data_info['lifetime_wins']}\n")
                        
                        # Enhanced Cosmetics with counts
                        if 'total_cosmetics' in account_data_info:
                            await f.write(f"Total Cosmetics: {account_data_info['total_cosmetics']}\n")
                        
                        # Skins (Outfits)
                        if 'skins' in account_data_info and account_data_info['skins']:
                            skins = account_data_info['skins']
                            await f.write(f"Skins ({len(skins)}):\n")
                            for skin in skins:
                                await f.write(f"  • {skin}\n")
                        elif 'outfits' in account_data_info and account_data_info['outfits']:
                            # Fallback to old format
                            await f.write(f"Skins:\n{account_data_info['outfits']}\n")
                        
                        # Back Blings
                        if 'back_blings' in account_data_info and account_data_info['back_blings']:
                            back_blings = account_data_info['back_blings']
                            if isinstance(back_blings, list):
                                await f.write(f"Back Blings ({len(back_blings)}):\n")
                                for back_bling in back_blings:
                                    await f.write(f"  • {back_bling}\n")
                            else:
                                await f.write(f"Back Blings:\n{back_blings}\n")
                        
                        # Gliders
                        if 'gliders' in account_data_info and account_data_info['gliders']:
                            gliders = account_data_info['gliders']
                            if isinstance(gliders, list):
                                await f.write(f"Gliders ({len(gliders)}):\n")
                                for glider in gliders:
                                    await f.write(f"  • {glider}\n")
                            else:
                                await f.write(f"Gliders:\n{gliders}\n")
                        
                        # Pickaxes
                        if 'pickaxes' in account_data_info and account_data_info['pickaxes']:
                            pickaxes = account_data_info['pickaxes']
                            if isinstance(pickaxes, list):
                                await f.write(f"Pickaxes ({len(pickaxes)}):\n")
                                for pickaxe in pickaxes:
                                    await f.write(f"  • {pickaxe}\n")
                            else:
                                await f.write(f"Pickaxes:\n{pickaxes}\n")
                        
                        # Linked accounts
                        if 'linked_accounts' in account_data_info and account_data_info['linked_accounts']:
                            linked = account_data_info['linked_accounts']
                            if linked:
                                await f.write("Linked Accounts:\n")
                                for account in linked:
                                    if isinstance(account, dict):
                                        account_type = account.get('type', 'Unknown')
                                        external_display_name = account.get('externalDisplayName', 'N/A')
                                        await f.write(f"  • {account_type}: {external_display_name}\n")
                        
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
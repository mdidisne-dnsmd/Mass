from typing import Dict, Any, Optional
import os

class UserDataManager:
    def __init__(self):
        self.user_data: Dict[int, Dict[str, Any]] = {}
    
    def get_user_data(self, user_id: int) -> Dict[str, Any]:
        """Get user data, create if doesn't exist"""
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                'proxies_file': None,
                'accounts_file': None,
                'proxies_count': 0,
                'accounts_count': 0,
                'is_checking': False,
                'last_results': None,
                'result_files': None
            }
        return self.user_data[user_id]
    
    def set_proxies_file(self, user_id: int, file_path: str, count: int):
        """Set proxies file for user"""
        data = self.get_user_data(user_id)
        data['proxies_file'] = file_path
        data['proxies_count'] = count
    
    def set_accounts_file(self, user_id: int, file_path: str, count: int):
        """Set accounts file for user"""
        data = self.get_user_data(user_id)
        data['accounts_file'] = file_path
        data['accounts_count'] = count
    
    def set_checking_status(self, user_id: int, status: bool):
        """Set checking status for user"""
        data = self.get_user_data(user_id)
        data['is_checking'] = status
    
    def set_detailed_results(self, user_id: int, results: dict, files_created: dict):
        """Set detailed checking results for user"""
        data = self.get_user_data(user_id)
        error_count = len(results.get('error', []))
        data['last_results'] = {
            'valid_count': len(results['valid']),
            'invalid_count': len(results['invalid']),
            'captcha_count': len(results['captcha']),
            'twofa_count': len(results['2fa']),
            'error_count': error_count,
            'total_count': len(results['valid']) + len(results['invalid']) + len(results['captcha']) + len(results['2fa']) + error_count
        }
        data['result_files'] = files_created
    
    def can_start_checking(self, user_id: int) -> bool:
        """Check if user can start checking (only accounts file required, proxies optional)"""
        data = self.get_user_data(user_id)
        return (data['accounts_file'] is not None and 
                not data['is_checking'])
    
    def get_status_message(self, user_id: int) -> str:
        """Get status message for user"""
        data = self.get_user_data(user_id)
        
        status_lines = []
        status_lines.append("📊 **Current Status:**\n")
        
        # Proxies status
        if data['proxies_file']:
            status_lines.append(f"✅ Proxies: {data['proxies_count']} loaded")
        else:
            status_lines.append("🚫 Proxies: Not uploaded (will use direct connection)")
        
        # Accounts status
        if data['accounts_file']:
            status_lines.append(f"✅ Accounts: {data['accounts_count']} loaded")
        else:
            status_lines.append("❌ Accounts: Not uploaded")
        
        # Checking status
        if data['is_checking']:
            status_lines.append("🔄 Status: Currently checking...")
        elif data['last_results']:
            results = data['last_results']
            status_lines.append(f"✅ Last check completed:")
            
            status_lines.append(f"   • ✅ Valid: {results['valid_count']}")
            status_lines.append(f"   • ❌ Invalid: {results['invalid_count']}")
            status_lines.append(f"   • 🤖 Captcha: {results['captcha_count']}")
            status_lines.append(f"   • 🔐 2FA: {results['twofa_count']}")
            if results.get('error_count', 0) > 0:
                status_lines.append(f"   • ⚠️ Errors: {results['error_count']}")
            status_lines.append(f"   • Total: {results['total_count']}")
        else:
            status_lines.append("⏳ Status: Ready to start")
        
        return "\n".join(status_lines)
    
    def clear_user_data(self, user_id: int):
        """Clear all user data"""
        if user_id in self.user_data:
            # Clean up files
            data = self.user_data[user_id]
            for file_key in ['proxies_file', 'accounts_file']:
                file_path = data.get(file_key)
                if file_path and os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except:
                        pass
            
            # Clean up result files
            if data.get('result_files'):
                for file_path in data['result_files'].values():
                    if file_path and os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except:
                            pass
            
            del self.user_data[user_id]

# Global instance
user_manager = UserDataManager()
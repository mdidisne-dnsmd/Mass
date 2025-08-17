"""
Epic Games API Client for fetching account details and cosmetics
Uses auth codes extracted from browser login to access Epic Games APIs
"""
import aiohttp
import asyncio
import json
from typing import Dict, Any, Optional, Tuple
from .cosmetic_parser import CosmeticParser

class EpicAPIClient:
    """Client for Epic Games API to fetch account details and cosmetics"""
    
    def __init__(self):
        self.cosmetic_parser = CosmeticParser()
        self.session = None
        
        # Epic Games API endpoints
        self.base_url = "https://fortnite-public-service-prod11.ol.epicgames.com"
        self.account_url = "https://account-public-service-prod.ol.epicgames.com"
        
    async def __aenter__(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
    
    async def get_account_details(self, auth_token: str, email: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Fetch detailed account information using auth token
        Returns (success, details_dict)
        """
        try:
            print(f"🔍 {email} - Fetching account details with auth token...")
            
            # First, get account info
            account_info = await self._get_account_info(auth_token)
            if not account_info:
                return False, {'error': 'Failed to get account info'}
            
            account_id = account_info.get('id')
            if not account_id:
                return False, {'error': 'No account ID found'}
            
            print(f"🆔 {email} - Account ID: {account_id}")
            
            # Get profile data (cosmetics, stats, etc.)
            profile_data = await self._get_profile_data(auth_token, account_id)
            
            # Combine account info with profile data
            details = {
                'account_id': account_id,
                'display_name': account_info.get('displayName', ''),
                'email': account_info.get('email', email),
                'created_at': account_info.get('dateOfBirth', ''),
                'updated_at': account_info.get('lastLogin', ''),
                **profile_data
            }
            
            print(f"✅ {email} - Account details retrieved successfully")
            return True, details
            
        except Exception as e:
            print(f"❌ {email} - Error fetching account details: {str(e)}")
            return False, {'error': f'API error: {str(e)}'}
    
    async def _get_account_info(self, auth_token: str) -> Optional[Dict[str, Any]]:
        """Get basic account information"""
        try:
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'Content-Type': 'application/json'
            }
            
            # Try multiple endpoints for account info
            endpoints = [
                f"{self.account_url}/account/api/public/account",
                f"{self.account_url}/account/api/oauth/verify",
                "https://account-public-service-prod03.ol.epicgames.com/account/api/public/account"
            ]
            
            for endpoint in endpoints:
                try:
                    async with self.session.get(endpoint, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            if isinstance(data, list) and len(data) > 0:
                                return data[0]
                            elif isinstance(data, dict):
                                return data
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error getting account info: {e}")
            return None
    
    async def _get_profile_data(self, auth_token: str, account_id: str) -> Dict[str, Any]:
        """Get profile data including cosmetics and stats"""
        try:
            headers = {
                'Authorization': f'Bearer {auth_token}',
                'Content-Type': 'application/json'
            }
            
            profile_data = {}
            
            # Get Athena profile (Battle Royale cosmetics and stats)
            athena_profile = await self._get_profile(auth_token, account_id, 'athena', headers)
            if athena_profile:
                profile_data.update(self._parse_athena_profile(athena_profile))
            
            # Get Common Core profile (account level, V-Bucks, etc.)
            common_core = await self._get_profile(auth_token, account_id, 'common_core', headers)
            if common_core:
                profile_data.update(self._parse_common_core_profile(common_core))
            
            # Get Creative profile if available
            creative_profile = await self._get_profile(auth_token, account_id, 'creative', headers)
            if creative_profile:
                profile_data.update(self._parse_creative_profile(creative_profile))
            
            return profile_data
            
        except Exception as e:
            print(f"Error getting profile data: {e}")
            return {'profile_error': str(e)}
    
    async def _get_profile(self, auth_token: str, account_id: str, profile_id: str, headers: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """Get specific profile data"""
        try:
            # Try multiple profile endpoints
            endpoints = [
                f"{self.base_url}/fortnite/api/game/v2/profile/{account_id}/client/{profile_id}?profileId={profile_id}",
                f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{account_id}/client/{profile_id}",
                f"https://fngw-mcp-gc-livefn.ol.epicgames.com/fortnite/api/game/v2/profile/{account_id}/client/{profile_id}"
            ]
            
            for endpoint in endpoints:
                try:
                    # Use POST request as Epic Games API often requires it
                    payload = {
                        "profileId": profile_id,
                        "rvn": -1
                    }
                    
                    async with self.session.post(endpoint, headers=headers, json=payload) as response:
                        if response.status == 200:
                            return await response.json()
                        elif response.status == 404:
                            # Profile not found, try next endpoint
                            continue
                except:
                    continue
            
            return None
            
        except Exception as e:
            print(f"Error getting {profile_id} profile: {e}")
            return None
    
    def _parse_athena_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Athena profile for cosmetics and Battle Royale stats"""
        try:
            result = {}
            
            # Get profile stats
            profile_stats = profile_data.get('profileChanges', [{}])[0].get('profile', {}).get('stats', {}).get('attributes', {})
            
            # Battle Pass info
            result['battle_pass_level'] = profile_stats.get('book_level', 0)
            result['battle_pass_purchased'] = profile_stats.get('book_purchased', False)
            result['seasonal_level'] = profile_stats.get('season_match_boost', 0)
            result['account_level'] = profile_stats.get('accountLevel', 0)
            
            # Lifetime stats
            result['lifetime_wins'] = profile_stats.get('lifetime_wins', 0)
            
            # Get items (cosmetics)
            items = profile_data.get('profileChanges', [{}])[0].get('profile', {}).get('items', {})
            
            if items:
                # Parse cosmetics using the cosmetic parser
                result['outfits'] = self.cosmetic_parser.get_outfits(items)
                result['back_blings'] = self.cosmetic_parser.get_back_blings(items)
                result['gliders'] = self.cosmetic_parser.get_gliders(items)
                result['pickaxes'] = self.cosmetic_parser.get_pickaxes(items)
            
            # Past seasons data
            past_seasons = profile_stats.get('past_seasons', [])
            if past_seasons:
                result['past_seasons'] = past_seasons
            
            return result
            
        except Exception as e:
            print(f"Error parsing Athena profile: {e}")
            return {'athena_parse_error': str(e)}
    
    def _parse_common_core_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Common Core profile for account-wide data"""
        try:
            result = {}
            
            # Get profile stats
            profile_stats = profile_data.get('profileChanges', [{}])[0].get('profile', {}).get('stats', {}).get('attributes', {})
            
            # V-Bucks and currency
            result['vbucks'] = profile_stats.get('current_mtx_platform', {}).get('EpicPC', 0)
            
            # Account creation info
            result['created_at'] = profile_stats.get('created', '')
            result['updated_at'] = profile_stats.get('last_applied_loadout', '')
            
            return result
            
        except Exception as e:
            print(f"Error parsing Common Core profile: {e}")
            return {'common_core_parse_error': str(e)}
    
    def _parse_creative_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Creative profile data"""
        try:
            result = {}
            
            # Get creative-specific stats if available
            profile_stats = profile_data.get('profileChanges', [{}])[0].get('profile', {}).get('stats', {}).get('attributes', {})
            
            # Creative mode stats
            result['creative_plots'] = len(profile_stats.get('creative_dynamic_builds', {}))
            
            return result
            
        except Exception as e:
            print(f"Error parsing Creative profile: {e}")
            return {'creative_parse_error': str(e)}

# Alternative method using different auth approach
class EpicWebAPIClient:
    """Alternative Epic API client using web-based authentication"""
    
    def __init__(self):
        self.cosmetic_parser = CosmeticParser()
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def get_account_details_from_cookies(self, cookies: Dict[str, str], email: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Alternative method: Extract account details using session cookies
        This might work better with browser-extracted auth data
        """
        try:
            print(f"🔍 {email} - Fetching account details using session cookies...")
            
            # Convert cookies to proper format
            cookie_header = '; '.join([f"{name}={value}" for name, value in cookies.items()])
            
            headers = {
                'Cookie': cookie_header,
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Referer': 'https://www.epicgames.com/',
                'Accept': 'application/json, text/plain, */*'
            }
            
            # Try to access Epic Games account page
            account_endpoints = [
                'https://www.epicgames.com/account/v2/api/public/account',
                'https://www.epicgames.com/id/api/account',
                'https://account-public-service-prod.ol.epicgames.com/account/api/public/account'
            ]
            
            for endpoint in account_endpoints:
                try:
                    async with self.session.get(endpoint, headers=headers) as response:
                        if response.status == 200:
                            data = await response.json()
                            print(f"✅ {email} - Account data retrieved from {endpoint}")
                            return True, {
                                'account_id': data.get('id', ''),
                                'display_name': data.get('displayName', ''),
                                'email': data.get('email', email),
                                'created_at': data.get('dateOfBirth', ''),
                                'message': 'Account details retrieved via web API'
                            }
                except Exception as e:
                    print(f"Failed endpoint {endpoint}: {e}")
                    continue
            
            # If direct API fails, try to extract from Epic Games web pages
            return await self._extract_from_web_pages(headers, email)
            
        except Exception as e:
            print(f"❌ {email} - Error with cookie-based auth: {str(e)}")
            return False, {'error': f'Cookie auth error: {str(e)}'}
    
    async def _extract_from_web_pages(self, headers: Dict[str, str], email: str) -> Tuple[bool, Dict[str, Any]]:
        """Extract account info from Epic Games web pages"""
        try:
            # Try Epic Games account page
            async with self.session.get('https://www.epicgames.com/account/personal', headers=headers) as response:
                if response.status == 200:
                    html_content = await response.text()
                    
                    # Basic extraction from HTML (this is a fallback method)
                    details = {
                        'message': 'Account accessible via web interface',
                        'login_successful': True,
                        'account_page_accessible': True
                    }
                    
                    # Try to extract basic info from HTML
                    if 'displayName' in html_content:
                        import re
                        display_name_match = re.search(r'"displayName":"([^"]+)"', html_content)
                        if display_name_match:
                            details['display_name'] = display_name_match.group(1)
                    
                    print(f"✅ {email} - Account page accessible, basic info extracted")
                    return True, details
            
            return False, {'error': 'Could not access account pages'}
            
        except Exception as e:
            print(f"Error extracting from web pages: {e}")
            return False, {'error': f'Web extraction error: {str(e)}'}
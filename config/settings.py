"""
Bot Configuration Settings
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Bot credentials
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0') or '0')

# File paths
TEMP_DIR = 'temp'
DATA_DIR = 'data'

# Bot settings
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
SUPPORTED_FILE_TYPES = ['.txt']
MAX_CONCURRENT_CHECKS = 10
REQUEST_TIMEOUT = 30

# Browser scraper settings
LOGIN_URL = "https://www.epicgames.com/id/login"
HEADLESS = bool(int(os.getenv('HEADLESS', '1')))
NAVIGATION_TIMEOUT = int(os.getenv('NAVIGATION_TIMEOUT', '30000'))  # ms
BLOCK_RESOURCE_TYPES = ['image', 'font', 'media']
BROWSER_SLOWMO = int(os.getenv('BROWSER_SLOWMO', '0'))  # ms for debugging

# Debug settings
FORCE_NO_PROXY = bool(int(os.getenv('FORCE_NO_PROXY', '0')))  # Test without proxies

# Proxy format examples (tested working formats):
# Proxy-Jet: username-session-country:password@host:port
# Example: 250712La4qP-resi-US:049NOA7a4VNHoIM@ca.proxy-jet.io:1010
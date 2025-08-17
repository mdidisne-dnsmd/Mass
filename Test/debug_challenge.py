#!/usr/bin/env python3
"""
Debug what elements are actually present on the Cloudflare challenge page
"""
import asyncio
from playwright.async_api import async_playwright

async def debug_challenge_page():
    """Debug what elements are present on the challenge page"""
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox", 
                "--disable-dev-shm-usage",
                "--disable-blink-features=AutomationControlled",
                "--disable-automation",
                "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
            ]
        )
        
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            extra_http_headers={
                "Sec-Ch-Ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Google Chrome";v="128"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"Windows"'
            }
        )
        
        page = await context.new_page()
        
        print("🔍 Navigating to Epic Games login...")
        await page.goto("https://www.epicgames.com/id/login", wait_until="networkidle")
        await asyncio.sleep(5)
        
        print(f"📄 Page title: {await page.title()}")
        print(f"🌐 Current URL: {page.url}")
        
        # Get page HTML to analyze
        print("\n🔍 Analyzing page structure...")
        
        # Check for iframes
        iframes = await page.query_selector_all("iframe")
        print(f"📦 Found {len(iframes)} iframe(s)")
        
        for i, iframe in enumerate(iframes):
            src = await iframe.get_attribute("src")
            data_sitekey = await iframe.get_attribute("data-sitekey")
            class_name = await iframe.get_attribute("class")
            id_attr = await iframe.get_attribute("id")
            
            print(f"  Iframe {i+1}:")
            print(f"    src: {src}")
            print(f"    data-sitekey: {data_sitekey}")
            print(f"    class: {class_name}")
            print(f"    id: {id_attr}")
        
        # Check for Turnstile elements
        turnstile_selectors = [
            "input[name='cf-turnstile-response']",
            ".cf-turnstile",
            "[data-sitekey]",
            ".cf-challenge-container",
            ".cf-challenge"
        ]
        
        print("\n🎯 Checking for Turnstile elements...")
        for selector in turnstile_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                print(f"  ✅ Found {len(elements)} element(s) with selector: {selector}")
                for j, elem in enumerate(elements):
                    outer_html = await elem.evaluate("el => el.outerHTML")
                    print(f"    Element {j+1}: {outer_html[:200]}...")
            else:
                print(f"  ❌ No elements found for: {selector}")
        
        # Get all elements with 'cf' or 'turnstile' in class/id
        print("\n🔍 Searching for CF/Turnstile related elements...")
        cf_elements = await page.evaluate("""
            () => {
                const elements = [];
                const allElements = document.querySelectorAll('*');
                for (let el of allElements) {
                    const className = el.className || '';
                    const id = el.id || '';
                    const tagName = el.tagName.toLowerCase();
                    
                    if (className.includes('cf') || className.includes('turnstile') || 
                        id.includes('cf') || id.includes('turnstile') ||
                        (tagName === 'iframe' && el.src && (el.src.includes('cloudflare') || el.src.includes('turnstile')))) {
                        elements.push({
                            tag: tagName,
                            className: className,
                            id: id,
                            src: el.src || '',
                            outerHTML: el.outerHTML.substring(0, 200)
                        });
                    }
                }
                return elements;
            }
        """)
        
        if cf_elements:
            print(f"  ✅ Found {len(cf_elements)} CF/Turnstile related elements:")
            for elem in cf_elements:
                print(f"    {elem['tag']} - class: {elem['className']} - id: {elem['id']}")
                if elem['src']:
                    print(f"      src: {elem['src']}")
                print(f"      HTML: {elem['outerHTML']}...")
        else:
            print("  ❌ No CF/Turnstile elements found")
        
        # Take a screenshot for analysis
        await page.screenshot(path="challenge_debug.png")
        print("\n📸 Screenshot saved as challenge_debug.png")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug_challenge_page())
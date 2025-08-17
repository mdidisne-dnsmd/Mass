#!/usr/bin/env python3
"""
Test the new Cloudflare challenge handler
"""
import asyncio
from utils.account_checker_cf import AccountCheckerCF

async def test_challenge_handler():
    """Test the enhanced challenge handling"""
    
    print("🎯 Testing enhanced Cloudflare challenge handling...")
    
    async with AccountCheckerCF() as checker:
        # Test with a dummy account to see challenge handling
        print("🔍 Testing challenge detection and interaction...")
        status, details = await checker.check_account("test@example.com", "dummypassword")
        
        print(f"\n📊 RESULTS:")
        print(f"Status: {status}")
        print(f"Details: {details}")
        
        # Analyze results
        if status.name == "CAPTCHA":
            if "timeout" in details.get('error', '').lower():
                print("\n❌ Challenge timeout - may need longer wait times")
            elif "challenge" in details.get('error', '').lower():
                print("\n⚠️ Challenge detected but not resolved - interaction may need improvement")
            else:
                print(f"\n🤔 Unexpected captcha result: {details}")
        elif status.name == "INVALID":
            print("\n🎉 SUCCESS! Got past Cloudflare to login form (invalid credentials expected)")
        else:
            print(f"\n🤔 Unexpected status: {status}")

if __name__ == "__main__":
    asyncio.run(test_challenge_handler())
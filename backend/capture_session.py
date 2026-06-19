"""
OmniFood - Session Capture Script
Run this script to log into Zomato, Swiggy, or EatSure in a visible browser window.
Your session cookies will be saved so the agent can use your membership benefits.

Usage:
    python capture_session.py zomato
    python capture_session.py swiggy
    python capture_session.py eatsure
"""

import asyncio
import sys

async def main():
    if len(sys.argv) < 2:
        print("\nUsage: python capture_session.py <platform>")
        print("  Platforms: zomato, swiggy, eatsure")
        print("\nExample: python capture_session.py zomato")
        return
    
    platform = sys.argv[1].lower()
    
    if platform not in ("zomato", "swiggy", "eatsure"):
        print(f"Unknown platform: {platform}")
        print("Supported: zomato, swiggy, eatsure")
        return
    
    from session_manager import get_session_manager
    sm = get_session_manager()
    print(f"Starting manual login for {platform}...")
    result = await sm.start_login(platform)
    if not result["success"]:
        print(f"Error: {result.get('error')}")
        return
    
    print("\n" + "="*50)
    print(result["message"])
    print("="*50)
    print("\nPress Enter here ONLY AFTER you have finished logging in and can see your profile/account page...")
    input()
    
    print(f"Confirming login for {platform}...")
    confirm_result = await sm.confirm_login(platform)
    if confirm_result["success"]:
        print(f"Success! {confirm_result['message']}")
    else:
        print(f"Failed: {confirm_result.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())

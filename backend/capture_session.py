"""
OmniFood - Session Capture Script
Run this script to log into Zomato or Swiggy in a visible browser window.
Your session cookies will be saved so the agent can use your membership benefits.

Usage:
    python capture_session.py zomato
    python capture_session.py swiggy
"""

import asyncio
import sys

async def main():
    if len(sys.argv) < 2:
        print("\nUsage: python capture_session.py <platform>")
        print("  Platforms: zomato, swiggy")
        print("\nExample: python capture_session.py zomato")
        return
    
    platform = sys.argv[1].lower()
    
    if platform not in ("zomato", "swiggy"):
        print(f"Unknown platform: {platform}")
        print("Supported: zomato, swiggy")
        return
    
    from scraper import SessionCapture
    await SessionCapture.capture(platform)

if __name__ == "__main__":
    asyncio.run(main())

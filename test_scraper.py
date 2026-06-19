import asyncio
from backend.scraper import BrowserManager
from backend.config import get_settings

async def main():
    settings = get_settings()
    print("Demo mode:", settings.demo_mode)
    bm = BrowserManager()
    ok, msg = await bm.can_scrape_live()
    print("can_scrape_live:", ok, msg)
    
    intent = {"restaurant": "Punjabi Tadka", "items": ["Butter Chicken", "Garlic Naan"], "city": "Mumbai"}
    res = await bm.scrape_zomato(intent)
    print("Zomato result:", res)
    
asyncio.run(main())

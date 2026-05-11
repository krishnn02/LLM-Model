"""
OmniFood Agent - Production Playwright Scraper
Uses stealth browser automation with AI-driven locators to fetch real prices
from Zomato, Swiggy, and EatSure checkout pages.
"""

import asyncio
import logging
import os
import json
import re
from typing import Dict, Any, Optional, Callable, Awaitable

try:
    from playwright.async_api import async_playwright, Page, BrowserContext, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from config import get_settings

logger = logging.getLogger("omnifood.scraper")

# ── Callback type for streaming logs back to the agent ──
LogCallback = Callable[[str], Awaitable[None]]

async def _noop_log(msg: str):
    logger.info(msg)


class BrowserManager:
    """
    Manages headless Playwright browser instances with persistent session state.
    Uses storageState to inherit logged-in sessions (Zomato Gold / Swiggy One).
    Falls back to demo mode with realistic simulated prices when Playwright is unavailable.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self._playwright: Optional[Playwright] = None
    
    # ─────────────────────────────────────────────────────────
    # Demo Mode — Realistic price simulation
    # ─────────────────────────────────────────────────────────
    def _should_use_demo(self) -> bool:
        """Check if we should use demo mode instead of real scraping."""
        return self.settings.demo_mode or not PLAYWRIGHT_AVAILABLE
    
    def _generate_demo_price(self, intent: Dict[str, Any], platform: str) -> Dict[str, Any]:
        """Generate realistic, varied prices based on the query for demo mode."""
        import hashlib
        import random
        
        # Create a seed from the query content so results are consistent per query
        # but different for different queries
        items = intent.get("items", [])
        restaurant = intent.get("restaurant", "Restaurant")
        seed_str = f"{platform}:{restaurant}:{':'.join(items)}"
        seed = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        
        # Base price varies by number of items and platform
        num_items = len(items) if items else 1
        per_item_base = rng.randint(120, 350)
        base_price = per_item_base * num_items
        
        # Platform-specific price multipliers (Zomato tends slightly higher, EatSure slightly lower)
        platform_multipliers = {
            "Zomato": rng.uniform(0.95, 1.10),
            "Swiggy": rng.uniform(0.90, 1.05),
            "EatSure": rng.uniform(0.85, 1.00),
        }
        multiplier = platform_multipliers.get(platform, 1.0)
        base_price = round(base_price * multiplier)
        
        # Taxes: 5-18% GST + platform fee
        gst_rate = rng.choice([0.05, 0.05, 0.12, 0.18])
        platform_fee = rng.choice([0, 5, 7, 10, 15])
        delivery_fee = rng.choice([0, 0, 20, 25, 30, 35, 40, 49])
        taxes = round(base_price * gst_rate) + platform_fee + delivery_fee
        
        # Discounts: sometimes a coupon applies
        discount = 0
        coupon_applied = None
        membership = None
        
        # 40% chance of coupon
        if rng.random() < 0.4:
            discount_pct = rng.choice([10, 15, 20, 25])
            max_discount = rng.choice([50, 75, 100, 120, 150])
            discount = min(round(base_price * discount_pct / 100), max_discount)
            coupon_applied = rng.choice(["SAVE20", "FEAST15", "WELCOME50", "TASTY25", "DEAL10"])
        
        # 30% chance of membership
        membership_map = {"Zomato": "Zomato Gold", "Swiggy": "Swiggy One", "EatSure": None}
        if rng.random() < 0.3 and membership_map.get(platform):
            membership = membership_map[platform]
            if delivery_fee > 0:
                taxes -= delivery_fee  # Free delivery with membership
                delivery_fee = 0
        
        final_total = max(base_price + taxes - discount, base_price * 0.6)
        final_total = round(final_total)
        
        delivery_time = f"{rng.randint(20, 55)} mins"
        
        return {
            "platform": platform,
            "base_price": base_price,
            "taxes": taxes,
            "discount": discount,
            "final_total": final_total,
            "delivery_time": delivery_time,
            "coupon_applied": coupon_applied,
            "membership": membership,
            "error": None,
        }
    
    async def _demo_scrape(self, intent: Dict[str, Any], platform: str, 
                           emoji: str, log: LogCallback) -> Dict[str, Any]:
        """Simulate a scraping session with realistic delays and log messages."""
        restaurant = intent.get("restaurant", "Restaurant")
        items = intent.get("items", [])
        
        await log(f"{emoji} {platform}: Navigating to {platform.lower()}.com...")
        await asyncio.sleep(0.4)
        
        await log(f"{emoji} {platform}: Searching for '{restaurant}'...")
        await asyncio.sleep(0.6)
        
        await log(f"{emoji} {platform}: Restaurant page loaded. Adding items to cart...")
        await asyncio.sleep(0.3)
        
        for item_name in items:
            await log(f"{emoji} {platform}: Adding '{item_name}' to cart ✓")
            await asyncio.sleep(0.25)
        
        await log(f"{emoji} {platform}: Navigating to checkout...")
        await asyncio.sleep(0.5)
        
        # Check membership
        result = self._generate_demo_price(intent, platform)
        if result["membership"]:
            await log(f"{emoji} {platform}: {result['membership']} membership detected! ✓")
        
        # Check coupon
        if result["coupon_applied"]:
            await log(f"{emoji} {platform}: Coupon '{result['coupon_applied']}' applied ✓")
        else:
            await log(f"{emoji} {platform}: No better coupons available")
        
        await log(f"{emoji} {platform}: Reading final checkout totals...")
        await asyncio.sleep(0.3)
        
        await log(
            f"{emoji} {platform}: Final → Base ₹{result['base_price']}, "
            f"Tax ₹{result['taxes']}, "
            f"Discount ₹{result['discount']}, "
            f"Total ₹{result['final_total']}"
        )
        
        return result
    
    async def _ensure_user_data_dir(self):
        user_data_dir = self.settings.user_data_dir
        if not os.path.exists(user_data_dir):
            os.makedirs(user_data_dir, exist_ok=True)
        return user_data_dir

    async def _launch_context(self, platform: str):
        """Launch a stealth browser context with persistent session data."""
        if not PLAYWRIGHT_AVAILABLE:
            raise NotImplementedError("Playwright is not installed")
            
        p = await async_playwright().start()
        
        user_data_dir = await self._ensure_user_data_dir()
        platform_dir = os.path.join(user_data_dir, platform)
        os.makedirs(platform_dir, exist_ok=True)
        
        # Load storage state if exists (logged-in session cookies/tokens)
        storage_state_file = os.path.join(platform_dir, "storageState.json")
        storage_state = storage_state_file if os.path.exists(storage_state_file) else None
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=platform_dir,
            headless=self.settings.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-web-security",
            ],
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
            ignore_https_errors=True,
        )
        
        # Stealth: mask webdriver property
        await context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            window.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
        """)
        
        return p, context
    
    async def _safe_close(self, playwright_instance: Playwright, context: BrowserContext):
        """Safely close browser resources."""
        try:
            await context.close()
        except Exception:
            pass
        try:
            await playwright_instance.stop()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────
    # Zomato Scraper
    # ─────────────────────────────────────────────────────────
    async def scrape_zomato(
        self, intent: Dict[str, Any], log: LogCallback = _noop_log
    ) -> Dict[str, Any]:
        """
        Scrape Zomato for the given restaurant and items.
        Uses AI-driven locators (get_by_text, get_by_role) for resilience.
        """
        p, context = None, None
        try:
            p, context = await self._launch_context("zomato")
            page = await context.new_page()
            page.set_default_timeout(self.settings.browser_timeout)
            
            restaurant = intent.get("restaurant", "")
            items = intent.get("items", [])
            address = intent.get("delivery_address", "")
            
            await log(f"🔴 Zomato: Navigating to zomato.com...")
            await page.goto("https://www.zomato.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # ── Step 1: Search for the restaurant ──
            await log(f"🔴 Zomato: Searching for '{restaurant}'...")
            search_input = page.get_by_placeholder("Search for restaurant")
            if await search_input.count() == 0:
                # Fallback: try alternative placeholder text
                search_input = page.get_by_placeholder("Search")
            if await search_input.count() == 0:
                search_input = page.locator('input[type="text"]').first
            
            await search_input.click()
            await search_input.fill(restaurant)
            await asyncio.sleep(2)
            
            # Click first search result
            search_results = page.locator('[class*="search"] a, [data-testid*="search"] a').first
            if await search_results.count() > 0:
                await search_results.click()
            else:
                # Fallback: press Enter
                await search_input.press("Enter")
            await asyncio.sleep(3)
            
            # Try to click on the restaurant from results page
            restaurant_link = page.get_by_text(restaurant, exact=False).first
            if await restaurant_link.count() > 0:
                await restaurant_link.click()
                await asyncio.sleep(3)
            
            await log(f"🔴 Zomato: Restaurant page loaded. Adding items to cart...")
            
            # ── Step 2: Add items to cart ──
            for item_name in items:
                await log(f"🔴 Zomato: Looking for '{item_name}'...")
                item_el = page.get_by_text(item_name, exact=False).first
                if await item_el.count() > 0:
                    # Find the nearest "Add" button
                    add_btn = page.get_by_role("button", name=re.compile(r"add", re.IGNORECASE)).first
                    if await add_btn.count() > 0:
                        await add_btn.click()
                        await asyncio.sleep(1)
                        await log(f"🔴 Zomato: Added '{item_name}' to cart ✓")
                    else:
                        await log(f"🔴 Zomato: Could not find Add button for '{item_name}'")
                else:
                    await log(f"🔴 Zomato: Item '{item_name}' not found on menu")
            
            await asyncio.sleep(2)
            
            # ── Step 3: Navigate to checkout ──
            await log("🔴 Zomato: Navigating to checkout...")
            checkout_btn = page.get_by_text("View Cart", exact=False)
            if await checkout_btn.count() == 0:
                checkout_btn = page.get_by_text("Checkout", exact=False)
            if await checkout_btn.count() == 0:
                checkout_btn = page.locator('[class*="cart"] button, [class*="Cart"] button').first
            
            if await checkout_btn.count() > 0:
                await checkout_btn.click()
                await asyncio.sleep(3)
            
            # ── Step 4: Check for membership benefits ──
            await log("🔴 Zomato: Checking Zomato Gold benefits...")
            membership = None
            gold_badge = page.get_by_text("Gold", exact=False)
            if await gold_badge.count() > 0:
                membership = "Zomato Gold"
                await log("🔴 Zomato: Zomato Gold membership detected! ✓")
            
            # ── Step 5: Try to apply best coupon ──
            await log("🔴 Zomato: Checking available coupons...")
            coupon_applied = None
            coupon_btn = page.get_by_text("Apply Coupon", exact=False)
            if await coupon_btn.count() > 0:
                await coupon_btn.click()
                await asyncio.sleep(2)
                # Try to click the first available coupon
                apply_btns = page.get_by_role("button", name=re.compile(r"apply", re.IGNORECASE))
                if await apply_btns.count() > 0:
                    await apply_btns.first.click()
                    await asyncio.sleep(1)
                    coupon_applied = "AUTO_BEST"
                    await log("🔴 Zomato: Best coupon applied ✓")
            
            # ── Step 6: Extract final prices from checkout page ──
            await log("🔴 Zomato: Reading final checkout totals...")
            price_data = await self._extract_zomato_prices(page)
            price_data["platform"] = "Zomato"
            price_data["membership"] = membership
            price_data["coupon_applied"] = coupon_applied
            
            await log(
                f"🔴 Zomato: Final → Base ₹{price_data['base_price']}, "
                f"Tax ₹{price_data['taxes']}, "
                f"Discount ₹{price_data['discount']}, "
                f"Total ₹{price_data['final_total']}"
            )
            
            # Save storage state for next run
            storage_path = os.path.join(self.settings.user_data_dir, "zomato", "storageState.json")
            await context.storage_state(path=storage_path)
            
            return price_data
            
        except Exception as e:
            logger.error(f"Zomato scraper error: {e}")
            await log(f"🔴 Zomato: Error during scraping — {str(e)[:100]}")
            return self._error_result("Zomato", str(e))
        finally:
            if p and context:
                await self._safe_close(p, context)
    
    async def _extract_zomato_prices(self, page: Page) -> Dict[str, Any]:
        """Extract price breakdown from Zomato checkout page using AI-driven locators."""
        base_price = 0
        taxes = 0
        discount = 0
        final_total = 0
        delivery_time = "N/A"
        
        try:
            # Item total / subtotal
            for label in ["Item Total", "Subtotal", "Items total"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    base_price = self._parse_price(row_text)
                    if base_price > 0:
                        break
            
            # Taxes and charges
            for label in ["Taxes", "GST", "Taxes and Charges", "Restaurant charges"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    taxes += self._parse_price(row_text)
            
            # Delivery fee
            for label in ["Delivery Fee", "Delivery charge"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    fee = self._parse_price(row_text)
                    if fee > 0:
                        taxes += fee  # Include delivery fee in taxes/fees
            
            # Discounts
            for label in ["Discount", "Savings", "You saved", "Coupon"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    discount += self._parse_price(row_text)
            
            # Grand total
            for label in ["Grand Total", "To Pay", "Total", "Amount"]:
                el = page.get_by_text(label, exact=True)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    parsed = self._parse_price(row_text)
                    if parsed > 0:
                        final_total = parsed
                        break
            
            # Delivery time
            for label in ["min", "mins", "minutes"]:
                el = page.get_by_text(re.compile(rf"\d+\s*{label}"), exact=False)
                if await el.count() > 0:
                    time_text = await el.first.text_content()
                    delivery_time = time_text.strip() if time_text else "N/A"
                    break
            
            # If we couldn't extract final_total, calculate it
            if final_total == 0 and base_price > 0:
                final_total = base_price + taxes - discount
                
        except Exception as e:
            logger.warning(f"Price extraction fallback: {e}")
        
        return {
            "base_price": base_price,
            "taxes": taxes,
            "discount": discount,
            "final_total": final_total,
            "delivery_time": delivery_time,
        }

    # ─────────────────────────────────────────────────────────
    # Swiggy Scraper
    # ─────────────────────────────────────────────────────────
    async def scrape_swiggy(
        self, intent: Dict[str, Any], log: LogCallback = _noop_log
    ) -> Dict[str, Any]:
        """
        Scrape Swiggy for the given restaurant and items.
        """
        p, context = None, None
        try:
            p, context = await self._launch_context("swiggy")
            page = await context.new_page()
            page.set_default_timeout(self.settings.browser_timeout)
            
            restaurant = intent.get("restaurant", "")
            items = intent.get("items", [])
            
            await log("🟠 Swiggy: Navigating to swiggy.com...")
            await page.goto("https://www.swiggy.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # ── Step 1: Search for restaurant ──
            await log(f"🟠 Swiggy: Searching for '{restaurant}'...")
            search_input = page.get_by_placeholder("Search for restaurants")
            if await search_input.count() == 0:
                search_input = page.get_by_placeholder("Search")
            if await search_input.count() == 0:
                # Click the search icon first
                search_icon = page.locator('[data-testid="search-icon"], [class*="search"]').first
                if await search_icon.count() > 0:
                    await search_icon.click()
                    await asyncio.sleep(1)
                search_input = page.locator('input[type="text"], input[type="search"]').first
            
            await search_input.click()
            await search_input.fill(restaurant)
            await asyncio.sleep(2)
            
            # Click first result
            search_results = page.locator('a[href*="restaurant"], [class*="RestaurantResult"] a').first
            if await search_results.count() > 0:
                await search_results.click()
            else:
                await search_input.press("Enter")
            await asyncio.sleep(3)
            
            # Try to find and click restaurant
            restaurant_link = page.get_by_text(restaurant, exact=False).first
            if await restaurant_link.count() > 0:
                await restaurant_link.click()
                await asyncio.sleep(3)
            
            await log(f"🟠 Swiggy: Restaurant page loaded. Adding items...")
            
            # ── Step 2: Add items ──
            for item_name in items:
                await log(f"🟠 Swiggy: Looking for '{item_name}'...")
                item_el = page.get_by_text(item_name, exact=False).first
                if await item_el.count() > 0:
                    add_btn = page.get_by_role("button", name=re.compile(r"add", re.IGNORECASE)).first
                    if await add_btn.count() > 0:
                        await add_btn.click()
                        await asyncio.sleep(1)
                        await log(f"🟠 Swiggy: Added '{item_name}' to cart ✓")
                    else:
                        await log(f"🟠 Swiggy: Could not find Add button for '{item_name}'")
                else:
                    await log(f"🟠 Swiggy: Item '{item_name}' not found")
            
            await asyncio.sleep(2)
            
            # ── Step 3: Go to checkout ──
            await log("🟠 Swiggy: Navigating to checkout...")
            checkout_btn = page.get_by_text("View Cart", exact=False)
            if await checkout_btn.count() == 0:
                checkout_btn = page.get_by_text("Checkout", exact=False)
            if await checkout_btn.count() == 0:
                checkout_btn = page.locator('[class*="cart"] button, [class*="Cart"] button, [data-testid*="cart"]').first
            
            if await checkout_btn.count() > 0:
                await checkout_btn.click()
                await asyncio.sleep(3)
            
            # ── Step 4: Check membership ──
            await log("🟠 Swiggy: Checking Swiggy One benefits...")
            membership = None
            one_badge = page.get_by_text("ONE", exact=True)
            if await one_badge.count() > 0:
                membership = "Swiggy One"
                await log("🟠 Swiggy: Swiggy One membership detected! FREE_DELIVERY perk ✓")
            
            # ── Step 5: Apply coupon ──
            await log("🟠 Swiggy: Checking available coupons...")
            coupon_applied = None
            coupon_btn = page.get_by_text("Apply Coupon", exact=False)
            if await coupon_btn.count() > 0:
                await coupon_btn.click()
                await asyncio.sleep(2)
                apply_btns = page.get_by_role("button", name=re.compile(r"apply", re.IGNORECASE))
                if await apply_btns.count() > 0:
                    await apply_btns.first.click()
                    await asyncio.sleep(1)
                    coupon_applied = "AUTO_BEST"
                    await log("🟠 Swiggy: Best coupon applied ✓")
            
            # ── Step 6: Extract prices ──
            await log("🟠 Swiggy: Reading final checkout totals...")
            price_data = await self._extract_swiggy_prices(page)
            price_data["platform"] = "Swiggy"
            price_data["membership"] = membership
            price_data["coupon_applied"] = coupon_applied
            
            await log(
                f"🟠 Swiggy: Final → Base ₹{price_data['base_price']}, "
                f"Tax ₹{price_data['taxes']}, "
                f"Discount ₹{price_data['discount']}, "
                f"Total ₹{price_data['final_total']}"
            )
            
            # Save storage state
            storage_path = os.path.join(self.settings.user_data_dir, "swiggy", "storageState.json")
            await context.storage_state(path=storage_path)
            
            return price_data
            
        except Exception as e:
            logger.error(f"Swiggy scraper error: {e}")
            await log(f"🟠 Swiggy: Error during scraping — {str(e)[:100]}")
            return self._error_result("Swiggy", str(e))
        finally:
            if p and context:
                await self._safe_close(p, context)
    
    async def _extract_swiggy_prices(self, page: Page) -> Dict[str, Any]:
        """Extract price breakdown from Swiggy checkout page."""
        base_price = 0
        taxes = 0
        discount = 0
        final_total = 0
        delivery_time = "N/A"
        
        try:
            # Item total
            for label in ["Item Total", "Subtotal"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    base_price = self._parse_price(row_text)
                    if base_price > 0:
                        break
            
            # Taxes
            for label in ["Taxes", "GST", "Govt Taxes"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    taxes += self._parse_price(row_text)
            
            # Delivery fee
            for label in ["Delivery Fee", "Delivery charge", "Partner fee"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    fee_text = await el.locator("..").text_content()
                    if "free" in (fee_text or "").lower():
                        pass  # Free delivery
                    else:
                        taxes += self._parse_price(row_text)
            
            # Discount
            for label in ["Discount", "Savings", "You saved", "Coupon savings"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    discount += self._parse_price(row_text)
            
            # Grand total
            for label in ["Grand Total", "TO PAY", "Total"]:
                el = page.get_by_text(label, exact=True)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    parsed = self._parse_price(row_text)
                    if parsed > 0:
                        final_total = parsed
                        break
            
            # Delivery time
            for label in ["min", "mins"]:
                el = page.get_by_text(re.compile(rf"\d+\s*{label}"), exact=False)
                if await el.count() > 0:
                    time_text = await el.first.text_content()
                    delivery_time = time_text.strip() if time_text else "N/A"
                    break
            
            if final_total == 0 and base_price > 0:
                final_total = base_price + taxes - discount
                
        except Exception as e:
            logger.warning(f"Swiggy price extraction fallback: {e}")
        
        return {
            "base_price": base_price,
            "taxes": taxes,
            "discount": discount,
            "final_total": final_total,
            "delivery_time": delivery_time,
        }

    # ─────────────────────────────────────────────────────────
    # EatSure Scraper
    # ─────────────────────────────────────────────────────────
    async def scrape_eatsure(
        self, intent: Dict[str, Any], log: LogCallback = _noop_log
    ) -> Dict[str, Any]:
        """
        Scrape EatSure for the given restaurant and items.
        EatSure is a multi-brand cloud kitchen platform by Rebel Foods.
        """
        p, context = None, None
        try:
            p, context = await self._launch_context("eatsure")
            page = await context.new_page()
            page.set_default_timeout(self.settings.browser_timeout)
            
            restaurant = intent.get("restaurant", "")
            items = intent.get("items", [])
            address = intent.get("delivery_address", "")
            
            await log("🟢 EatSure: Navigating to eatsure.com...")
            await page.goto("https://www.eatsure.com", wait_until="domcontentloaded")
            await asyncio.sleep(2)
            
            # ── Step 1: Search for the restaurant / items ──
            await log(f"🟢 EatSure: Searching for '{restaurant}'...")
            search_input = page.get_by_placeholder("Search for dishes")
            if await search_input.count() == 0:
                search_input = page.get_by_placeholder("Search")
            if await search_input.count() == 0:
                search_input = page.locator('input[type="text"], input[type="search"]').first
            
            if await search_input.count() > 0:
                await search_input.click()
                search_query = restaurant if restaurant else (items[0] if items else "food")
                await search_input.fill(search_query)
                await asyncio.sleep(2)
                
                # Click first result
                search_result = page.locator('a[href*="restaurant"], [class*="search-result"], [class*="SearchResult"]').first
                if await search_result.count() > 0:
                    await search_result.click()
                else:
                    await search_input.press("Enter")
                await asyncio.sleep(3)
            
            # Try to click on the restaurant link
            restaurant_link = page.get_by_text(restaurant, exact=False).first
            if await restaurant_link.count() > 0:
                await restaurant_link.click()
                await asyncio.sleep(3)
            
            await log(f"🟢 EatSure: Page loaded. Adding items to cart...")
            
            # ── Step 2: Add items ──
            for item_name in items:
                await log(f"🟢 EatSure: Looking for '{item_name}'...")
                item_el = page.get_by_text(item_name, exact=False).first
                if await item_el.count() > 0:
                    add_btn = page.get_by_role("button", name=re.compile(r"add", re.IGNORECASE)).first
                    if await add_btn.count() > 0:
                        await add_btn.click()
                        await asyncio.sleep(1)
                        await log(f"🟢 EatSure: Added '{item_name}' to cart ✓")
                    else:
                        await log(f"🟢 EatSure: Could not find Add button for '{item_name}'")
                else:
                    await log(f"🟢 EatSure: Item '{item_name}' not found")
            
            await asyncio.sleep(2)
            
            # ── Step 3: Go to checkout ──
            await log("🟢 EatSure: Navigating to checkout...")
            checkout_btn = page.get_by_text("View Cart", exact=False)
            if await checkout_btn.count() == 0:
                checkout_btn = page.get_by_text("Checkout", exact=False)
            if await checkout_btn.count() == 0:
                checkout_btn = page.locator('[class*="cart"] button, [class*="Cart"] button').first
            
            if await checkout_btn.count() > 0:
                await checkout_btn.click()
                await asyncio.sleep(3)
            
            # ── Step 4: Check membership ──
            membership = None
            
            # ── Step 5: Apply coupon ──
            await log("🟢 EatSure: Checking available coupons...")
            coupon_applied = None
            coupon_btn = page.get_by_text("Apply Coupon", exact=False)
            if await coupon_btn.count() > 0:
                await coupon_btn.click()
                await asyncio.sleep(2)
                apply_btns = page.get_by_role("button", name=re.compile(r"apply", re.IGNORECASE))
                if await apply_btns.count() > 0:
                    await apply_btns.first.click()
                    await asyncio.sleep(1)
                    coupon_applied = "AUTO_BEST"
                    await log("🟢 EatSure: Best coupon applied ✓")
            
            # ── Step 6: Extract prices ──
            await log("🟢 EatSure: Reading final checkout totals...")
            price_data = await self._extract_eatsure_prices(page)
            price_data["platform"] = "EatSure"
            price_data["membership"] = membership
            price_data["coupon_applied"] = coupon_applied
            
            await log(
                f"🟢 EatSure: Final → Base ₹{price_data['base_price']}, "
                f"Tax ₹{price_data['taxes']}, "
                f"Discount ₹{price_data['discount']}, "
                f"Total ₹{price_data['final_total']}"
            )
            
            # Save storage state
            storage_path = os.path.join(self.settings.user_data_dir, "eatsure", "storageState.json")
            await context.storage_state(path=storage_path)
            
            return price_data
            
        except Exception as e:
            logger.error(f"EatSure scraper error: {e}")
            await log(f"🟢 EatSure: Error during scraping — {str(e)[:100]}")
            return self._error_result("EatSure", str(e))
        finally:
            if p and context:
                await self._safe_close(p, context)
    
    async def _extract_eatsure_prices(self, page: Page) -> Dict[str, Any]:
        """Extract price breakdown from EatSure checkout page."""
        base_price = 0
        taxes = 0
        discount = 0
        final_total = 0
        delivery_time = "N/A"
        
        try:
            # Item total
            for label in ["Item Total", "Subtotal", "Cart Total"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    base_price = self._parse_price(row_text)
                    if base_price > 0:
                        break
            
            # Taxes
            for label in ["Taxes", "GST", "Taxes & charges"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    taxes += self._parse_price(row_text)
            
            # Delivery fee
            for label in ["Delivery Fee", "Delivery charge"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    fee_text = await el.locator("..").text_content()
                    if "free" in (fee_text or "").lower():
                        pass
                    else:
                        taxes += self._parse_price(row_text)
            
            # Discount
            for label in ["Discount", "Savings", "You saved"]:
                el = page.get_by_text(label, exact=False)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    discount += self._parse_price(row_text)
            
            # Grand total
            for label in ["Grand Total", "To Pay", "Total"]:
                el = page.get_by_text(label, exact=True)
                if await el.count() > 0:
                    row_text = await el.locator("..").text_content()
                    parsed = self._parse_price(row_text)
                    if parsed > 0:
                        final_total = parsed
                        break
            
            # Delivery time
            for label in ["min", "mins"]:
                el = page.get_by_text(re.compile(rf"\d+\s*{label}"), exact=False)
                if await el.count() > 0:
                    time_text = await el.first.text_content()
                    delivery_time = time_text.strip() if time_text else "N/A"
                    break
            
            if final_total == 0 and base_price > 0:
                final_total = base_price + taxes - discount
                
        except Exception as e:
            logger.warning(f"EatSure price extraction fallback: {e}")
        
        return {
            "base_price": base_price,
            "taxes": taxes,
            "discount": discount,
            "final_total": final_total,
            "delivery_time": delivery_time,
        }

    # ─────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def _parse_price(text: str) -> float:
        """Extract numeric price value from a text string like '₹ 460.00' or 'Rs. 460'."""
        if not text:
            return 0
        # Remove currency symbols and labels, extract the last number
        numbers = re.findall(r'[\d,]+\.?\d*', text.replace(',', ''))
        if numbers:
            try:
                return float(numbers[-1])
            except ValueError:
                return 0
        return 0
    
    @staticmethod
    def _error_result(platform: str, error: str) -> Dict[str, Any]:
        """Return a structured error result when scraping fails."""
        return {
            "platform": platform,
            "base_price": 0,
            "taxes": 0,
            "discount": 0,
            "final_total": 0,
            "delivery_time": "N/A",
            "error": error[:200],
            "membership": None,
            "coupon_applied": None,
        }


class SessionCapture:
    """
    Utility to capture logged-in session state for Zomato/Swiggy.
    Run this once manually to log in and save cookies.
    Usage: python -c "from scraper import SessionCapture; import asyncio; asyncio.run(SessionCapture.capture('zomato'))"
    """
    
    @staticmethod
    async def capture(platform: str):
        """Open a visible browser for the user to log in, then save the session."""
        settings = get_settings()
        p = await async_playwright().start()
        
        user_data_dir = os.path.join(settings.user_data_dir, platform)
        os.makedirs(user_data_dir, exist_ok=True)
        
        urls = {
            "zomato": "https://www.zomato.com/login",
            "swiggy": "https://www.swiggy.com",
            "eatsure": "https://www.eatsure.com",
        }
        
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,  # Visible so user can log in
            args=["--disable-blink-features=AutomationControlled"],
            viewport={"width": 1366, "height": 768},
        )
        
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(urls.get(platform, "https://www.google.com"))
        
        print(f"\n{'='*60}")
        print(f"  🔑 Log into {platform.upper()} in the browser window.")
        print(f"  Once logged in, press ENTER here to save the session.")
        print(f"{'='*60}\n")
        
        input("Press ENTER after logging in...")
        
        storage_path = os.path.join(user_data_dir, "storageState.json")
        await context.storage_state(path=storage_path)
        await context.close()
        await p.stop()
        
        print(f"✅ Session saved to {storage_path}")

"""
OmniFood - Session Manager
Manages authenticated sessions for Zomato, Swiggy, and EatSure.
Handles login via Playwright (visible browser), session persistence,
and session status checks using persistent browser profiles.

Uses the async Playwright API directly so browser sessions can be opened
and confirmed safely inside the FastAPI event loop on Windows.
"""

import asyncio
import json
import logging
import os
import threading
from typing import Dict, Any, Optional
from datetime import datetime
import traceback

try:
    from playwright.async_api import async_playwright, BrowserContext, Playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from config import get_settings

logger = logging.getLogger("omnifood.session")


# Platform login URLs and identifiers
PLATFORM_CONFIG = {
    "zomato": {
        "name": "Zomato",
        "login_url": "https://www.zomato.com/login",
        "home_url": "https://www.zomato.com",
        "color": "#e23744",
        "icon": "🔴",
        "login_indicators": ["My Account", "Profile", "Log Out", "Logout", "Hi,"],
        "membership_indicators": ["Gold", "Zomato Gold", "Pro", "Zomato Pro", "Pro Plus"],
    },
    "swiggy": {
        "name": "Swiggy",
        "login_url": "https://www.swiggy.com",
        "home_url": "https://www.swiggy.com",
        "color": "#fc8019",
        "icon": "🟠",
        "login_indicators": ["My Account", "Profile", "Sign Out", "Logout", "Hi "],
        "membership_indicators": ["ONE", "Swiggy One", "Swiggy ONE"],
    },
    "eatsure": {
        "name": "EatSure",
        "login_url": "https://www.eatsure.com",
        "home_url": "https://www.eatsure.com",
        "color": "#2ecc71",
        "icon": "🟢",
        "login_indicators": ["My Account", "Profile", "Logout", "Hi,"],
        "membership_indicators": [],
    },
}


class SessionManager:
    """
    Manages persistent browser sessions for each food delivery platform.
    Uses Playwright persistent contexts to maintain login state across app restarts.
    """

    def __init__(self):
        self.settings = get_settings()
        # Track active login browser instances (for manual login flow)
        # Each entry: { "playwright": Playwright, "context": BrowserContext, "page": Page, ... }
        self._active_logins: Dict[str, Dict[str, Any]] = {}
        # Lock for thread-safe access
        self._lock = threading.Lock()
        # Cached session status
        self._session_cache: Dict[str, Dict[str, Any]] = {}

    def _get_platform_dir(self, platform_key: str) -> str:
        """Get the persistent user data directory for a platform."""
        base = self.settings.user_data_dir
        platform_dir = os.path.join(base, platform_key)
        os.makedirs(platform_dir, exist_ok=True)
        return platform_dir

    def _get_session_meta_path(self, platform_key: str) -> str:
        """Get the path to the session metadata file."""
        return os.path.join(self._get_platform_dir(platform_key), "session_meta.json")

    def _save_session_meta(self, platform_key: str, meta: Dict[str, Any]):
        """Save session metadata to disk."""
        path = self._get_session_meta_path(platform_key)
        with open(path, "w") as f:
            json.dump(meta, f, indent=2)

    def _load_session_meta(self, platform_key: str) -> Optional[Dict[str, Any]]:
        """Load session metadata from disk."""
        path = self._get_session_meta_path(platform_key)
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                return None
        return None

    def get_all_sessions_status(self) -> Dict[str, Dict[str, Any]]:
        """Get the status of all platform sessions (from metadata files)."""
        statuses = {}
        for platform_key, config in PLATFORM_CONFIG.items():
            meta = self._load_session_meta(platform_key)
            login_in_progress = platform_key in self._active_logins

            if meta and meta.get("logged_in"):
                statuses[platform_key] = {
                    "platform": config["name"],
                    "connected": True,
                    "user_info": meta.get("user_info", "Connected"),
                    "phone": meta.get("phone", None),
                    "membership": meta.get("membership", None),
                    "connected_at": meta.get("connected_at", None),
                    "login_in_progress": login_in_progress,
                }
            else:
                statuses[platform_key] = {
                    "platform": config["name"],
                    "connected": False,
                    "user_info": None,
                    "phone": None,
                    "membership": None,
                    "connected_at": None,
                    "login_in_progress": login_in_progress,
                }
        return statuses

    async def _async_start_login(self, platform_key: str, platform_dir: str, config: dict) -> Dict[str, Any]:
        """
        Open a visible Playwright browser for manual login.
        Uses the async API so it can safely run inside the app's event loop.
        """
        try:
            p = await async_playwright().start()

            # Use a slightly different approach for Python 3.14 compatibility
            logger.info(f"Launching visible context for {config['name']} in {platform_dir}")

            logger.info(f"Calling launch_persistent_context for {platform_key}...")
            context = await p.chromium.launch_persistent_context(
                user_data_dir=platform_dir,
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--start-maximized",
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
                timeout=15000, # 15s timeout for launch
            )
            logger.info(f"Context launched for {platform_key}.")

            await context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                window.chrome = { runtime: {} };
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-IN', 'en-US', 'en'] });
            """)

            page = context.pages[0] if context.pages else await context.new_page()
            logger.info(f"Navigating to {config['login_url']}...")
            await page.goto(config["login_url"], wait_until="domcontentloaded", timeout=20000)
            logger.info(f"Navigation complete for {platform_key}.")

            with self._lock:
                self._active_logins[platform_key] = {
                    "playwright": p,
                    "context": context,
                    "page": page,
                    "started_at": datetime.utcnow().isoformat(),
                }

            logger.info(f"Login browser opened for {config['name']}")
            return {
                "success": True,
                "platform": config["name"],
                "message": (
                    f"Browser window opened for {config['name']}. "
                    "Please log in with your phone number/credentials. "
                    "Click 'Confirm Login' in OmniFood when done."
                ),
            }
        except Exception as e:
            logger.error(f"Failed to start login for {platform_key}: {e}")
            logger.error(traceback.format_exc())
            err_msg = str(e) if str(e) else e.__class__.__name__
            if "Target page, context or browser has been closed" in err_msg:
                err_msg = "Browser closed unexpectedly or already in use. Try again."
            elif "user data directory is already in use" in err_msg.lower():
                err_msg = f"The {platform_key} browser is already open in another window. Close it and try again."
            return {"success": False, "error": err_msg}


    async def start_login(self, platform_key: str) -> Dict[str, Any]:
        """
        Start a login session for the given platform.
        Opens a visible browser window where the user can log in.
        """
        if platform_key not in PLATFORM_CONFIG:
            return {"success": False, "error": f"Unknown platform: {platform_key}"}

        if not PLAYWRIGHT_AVAILABLE:
            return {"success": False, "error": "Playwright is not installed. Run: pip install playwright && python -m playwright install chromium"}

        # If there's already a login in progress for this platform, close it first
        if platform_key in self._active_logins:
            await self.cancel_login(platform_key)

        config = PLATFORM_CONFIG[platform_key]
        platform_dir = self._get_platform_dir(platform_key)

        try:
            return await self._async_start_login(platform_key, platform_dir, config)
        except Exception as e:
            logger.error(f"Failed to start login for {platform_key}: {e}")
            return {"success": False, "error": str(e)}

    async def _async_close_login_browser(self, platform_key: str):
        """Close an active login browser and clean up the stored references."""
        with self._lock:
            login_data = self._active_logins.pop(platform_key, None)

        if not login_data:
            return

        context = login_data.get("context")
        p = login_data.get("playwright")

        try:
            if context:
                await context.close()
        except Exception:
            pass
        try:
            if p:
                await p.stop()
        except Exception:
            pass

    async def confirm_login(self, platform_key: str) -> Dict[str, Any]:
        """
        After the user has logged in via the visible browser, confirm and save the session.
        """
        if platform_key not in PLATFORM_CONFIG:
            return {"success": False, "error": f"Unknown platform: {platform_key}"}

        with self._lock:
            if platform_key not in self._active_logins:
                return {"success": False, "error": "No login session in progress. Start a login first."}
            login_data = self._active_logins[platform_key]

        config = PLATFORM_CONFIG[platform_key]
        context = login_data["context"]
        page = login_data["page"]

        try:
            page_text = await page.text_content("body") or ""

            user_info = None
            for indicator in config["login_indicators"]:
                if indicator.lower() in page_text.lower():
                    user_info = indicator
                    break

            membership = None
            for indicator in config.get("membership_indicators", []):
                if indicator.lower() in page_text.lower():
                    membership = indicator
                    break

            import re
            # Only match explicitly formatted Indian phone numbers to avoid grabbing random 10-digit IDs
            phone_match = re.search(r'(?:\+91|91)[\s-]?(\d{10})', page_text)
            phone = phone_match.group(1) if phone_match else None
            
            if not phone:
                phone = "Authenticated User"

            storage_path = os.path.join(self._get_platform_dir(platform_key), "storageState.json")
            await context.storage_state(path=storage_path)

            meta = {
                "logged_in": True,
                "platform": config["name"],
                "user_info": user_info or "Logged In",
                "phone": phone,
                "membership": membership,
                "connected_at": datetime.utcnow().isoformat(),
                "storage_state_path": storage_path,
            }
            self._save_session_meta(platform_key, meta)

            await self._async_close_login_browser(platform_key)

            logger.info(f"Session confirmed and saved for {config['name']}")
            return {
                "success": True,
                "platform": config["name"],
                "user_info": meta["user_info"],
                "phone": phone,
                "membership": membership,
                "message": f"Successfully connected to {config['name']}! Your session has been saved.",
            }

        except Exception as e:
            logger.error(f"Failed to confirm login for {platform_key}: {e}")
            try:
                storage_path = os.path.join(self._get_platform_dir(platform_key), "storageState.json")
                await context.storage_state(path=storage_path)
                meta = {
                    "logged_in": True,
                    "platform": config["name"],
                    "user_info": "Connected (manual)",
                    "phone": None,
                    "membership": None,
                    "connected_at": datetime.utcnow().isoformat(),
                    "storage_state_path": storage_path,
                }
                self._save_session_meta(platform_key, meta)
                await self._async_close_login_browser(platform_key)
                return {
                    "success": True,
                    "platform": config["name"],
                    "message": f"Session saved for {config['name']} (could not verify login status).",
                    "warning": str(e),
                }
            except Exception as inner_e:
                await self._async_close_login_browser(platform_key)
                return {"success": False, "error": f"Failed to save session: {inner_e}"}

    async def cancel_login(self, platform_key: str) -> Dict[str, Any]:
        """Cancel an in-progress login and close the browser window."""
        if platform_key not in self._active_logins:
            return {"success": True, "message": "No login in progress."}

        config = PLATFORM_CONFIG.get(platform_key, {})
        await self._async_close_login_browser(platform_key)
        
        logger.info(f"Login cancelled for {config.get('name', platform_key)}")

        return {
            "success": True,
            "message": f"Login cancelled for {config.get('name', platform_key)}.",
        }

    async def disconnect(self, platform_key: str) -> Dict[str, Any]:
        """Disconnect a platform by removing saved session data."""
        if platform_key not in PLATFORM_CONFIG:
            return {"success": False, "error": f"Unknown platform: {platform_key}"}

        config = PLATFORM_CONFIG[platform_key]

        # Close any active login browser
        if platform_key in self._active_logins:
            await self.cancel_login(platform_key)

        # Remove session metadata
        meta_path = self._get_session_meta_path(platform_key)
        if os.path.exists(meta_path):
            os.remove(meta_path)

        # Remove storage state
        storage_path = os.path.join(self._get_platform_dir(platform_key), "storageState.json")
        if os.path.exists(storage_path):
            os.remove(storage_path)

        # Clear cached status
        if platform_key in self._session_cache:
            del self._session_cache[platform_key]

        logger.info(f"Session disconnected for {config['name']}")

        return {
            "success": True,
            "platform": config["name"],
            "message": f"Disconnected from {config['name']}. Session data removed.",
        }

    def is_connected(self, platform_key: str) -> bool:
        """Check if a platform has a saved authenticated session."""
        meta = self._load_session_meta(platform_key)
        if not meta or not meta.get("logged_in"):
            return False
        # Also check if storage state file exists
        storage_path = os.path.join(self._get_platform_dir(platform_key), "storageState.json")
        return os.path.exists(storage_path)

    def get_session_info(self, platform_key: str) -> Optional[Dict[str, Any]]:
        """Get session info for a platform (phone, membership, etc.)."""
        return self._load_session_meta(platform_key)


# Singleton instance
_session_manager: Optional[SessionManager] = None

def get_session_manager() -> SessionManager:
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager

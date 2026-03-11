"""
JARVIS Zepto Café Agent
Based on the open-source zepto-cafe-mcp by Pranav Chandra Prodduturi (Zepto engineer)
GitHub: https://github.com/proddnav/zepto-cafe-mcp

Orders from Zepto Café using Playwright — real browser, no bot blocking.

SETUP (run once):
    pip install playwright python-dotenv
    playwright install firefox
    python zepto_agent.py --login

Add to .env:
    ZEPTO_PHONE=9XXXXXXXXX
    ZEPTO_ADDRESS=Home   (label of your saved address on Zepto)
"""

import os
import sys
import re
import asyncio
import threading
from dotenv import load_dotenv

load_dotenv(r"D:\JARVIS\.env")

# ── Config ────────────────────────────────────────────────────────
ZEPTO_URL     = "https://www.zeptonow.com"
SESSION_DIR   = r"D:\JARVIS\zepto_session"
PHONE_NUMBER  = os.getenv("ZEPTO_PHONE", "")
DEFAULT_ADDR  = os.getenv("ZEPTO_ADDRESS", "")

# ── Callbacks ─────────────────────────────────────────────────────
_speak_fn  = None
_listen_fn = None
_notify_fn = None

def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn

def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Zepto] {text}")

def _listen(timeout=15):
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return ""


# ── Helpers ───────────────────────────────────────────────────────
def is_logged_in():
    marker = os.path.join(SESSION_DIR, "Default", "Cookies")
    return os.path.exists(marker)


async def _make_browser(playwright, headless=False):
    """Launch Firefox with persistent session — Zepto works best with Firefox."""
    os.makedirs(SESSION_DIR, exist_ok=True)
    return await playwright.firefox.launch_persistent_context(
        SESSION_DIR,
        headless=headless,
        viewport={"width": 1280, "height": 800},
        locale="en-IN",
        timezone_id="Asia/Kolkata",
    )


# ── Login — run once ──────────────────────────────────────────────
async def _do_login():
    from playwright.async_api import async_playwright
    print("[Zepto] Opening Firefox for Zepto login...")

    async with async_playwright() as p:
        ctx  = await _make_browser(p, headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        await page.goto(ZEPTO_URL, wait_until="domcontentloaded", timeout=30000)
        print("\n[Zepto] Browser is open.")

        # Auto-fill phone if set
        if PHONE_NUMBER:
            try:
                phone_input = await page.wait_for_selector(
                    'input[type="tel"], input[placeholder*="phone"], input[placeholder*="mobile"]',
                    timeout=5000
                )
                await phone_input.fill(PHONE_NUMBER)
                print(f"[Zepto] Phone {PHONE_NUMBER} filled — check your OTP now.")
            except Exception:
                print("[Zepto] Please enter your phone number manually in the browser.")

        print("\n>> Log into Zepto Café in the browser.")
        print(">> Press Enter here once you are logged in: ", end="", flush=True)
        await asyncio.get_event_loop().run_in_executor(None, input)
        await ctx.close()

    print("[Zepto] Session saved! You can now use voice commands.")


# ── Order flow ────────────────────────────────────────────────────
async def _run_order(item_query: str):
    from playwright.async_api import async_playwright, TimeoutError as PWT

    _speak(f"Opening Zepto Café to order {item_query}.")

    async with async_playwright() as p:
        ctx  = await _make_browser(p, headless=False)
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        try:
            # Step 1 — Load Zepto
            await page.goto(ZEPTO_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000)

            # Step 2 — Set address if needed
            if DEFAULT_ADDR:
                try:
                    addr_btn = await page.wait_for_selector(
                        '[class*="address"], [data-testid*="address"], '
                        'button[aria-label*="address"]',
                        timeout=4000
                    )
                    await addr_btn.click()
                    await page.wait_for_timeout(1000)

                    saved_addrs = await page.query_selector_all(
                        '[class*="saved-address"], [class*="savedAddress"]'
                    )
                    for addr in saved_addrs:
                        txt = (await addr.inner_text()).strip()
                        if DEFAULT_ADDR.lower() in txt.lower():
                            await addr.click()
                            await page.wait_for_timeout(1500)
                            break
                except PWT:
                    pass

            # Init store info
            store_name = ""

            # Step 3 — Search for item
            try:
                search = await page.wait_for_selector(
                    'input[placeholder*="Search"], input[type="search"], '
                    '[data-testid="search-input"]',
                    timeout=6000
                )
                await search.click()
                await search.fill(item_query)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(3000)
            except PWT:
                _speak(f"Couldn't find the search bar on Zepto.")
                await ctx.close()
                return

            # Step 4 — Find products
            product_selectors = [
                '[class*="ProductCard"]',
                '[class*="product-card"]',
                '[data-testid="product-card"]',
                '[class*="item-card"]',
            ]
            products = []
            for sel in product_selectors:
                products = await page.query_selector_all(sel)
                if products: break

            if not products:
                _speak(f"No results found for {item_query} on Zepto Café.")
                await ctx.close()
                return

            # Extract product names + prices
            items = []
            for prod in products[:8]:
                for ns in ['h3', 'h4', 'p', '[class*="name"]', '[class*="title"]']:
                    el = await prod.query_selector(ns)
                    if el:
                        name = (await el.inner_text()).strip()
                        if name and len(name) > 2 and len(name) < 100:
                            price_el = await prod.query_selector(
                                '[class*="price"], [class*="Price"], span'
                            )
                            price = ""
                            if price_el:
                                price = re.sub(r'[^\d₹]', '',
                                    (await price_el.inner_text()).strip())
                            items.append({"name": name, "price": price, "el": prod})
                            break

            if not items:
                _speak("Found results but couldn't read product names. Please use the Zepto app.")
                await ctx.close()
                return

            # Read top items to user with full detail
            top = items[:4]

            # Try to get store/restaurant name
            store_name = ""
            try:
                store_el = await page.query_selector(
                    '[class*="storeName"], [class*="store-name"], '
                    '[class*="restaurantName"], [class*="outlet-name"], h1, h2'
                )
                if store_el:
                    store_name = (await store_el.inner_text()).strip()
            except Exception:
                pass

            if store_name:
                _speak(f"Ordering from {store_name} on Zepto Café.")
            else:
                _speak("Found items on Zepto Café.")

            items_str = ". ".join([
                f"{i+1}: {m['name']}" + (f", {m['price']} rupees" if m['price'] else "")
                for i, m in enumerate(top)
            ])
            _speak(f"Available items: {items_str}. Which one would you like Shivank?")
            choice = _listen()
            if not choice:
                _speak("Order cancelled.")
                await ctx.close()
                return

            # Match item
            chosen = None
            for m in items:
                if any(w in m["name"].lower()
                       for w in choice.lower().split() if len(w) > 2):
                    chosen = m
                    break
            if not chosen:
                num = re.search(r'\b([1-4])\b', choice)
                if num:
                    idx = int(num.group(1)) - 1
                    chosen = top[idx] if 0 <= idx < len(top) else top[0]
                else:
                    chosen = top[0]

            price_str = f" for {chosen['price']} rupees" if chosen['price'] else ""
            store_info = f" from {store_name}" if store_name else " from Zepto Café"
            _speak(
                f"Order summary: {chosen['name']}{store_info}{price_str}. "
                f"Payment will be as per your saved method. "
                f"Say yes to place the order or cancel to stop."
            )
            confirm = _listen()
            if not confirm or any(w in confirm.lower() for w in ["no", "cancel", "stop"]):
                _speak("Order cancelled.")
                await ctx.close()
                return

            # Step 5 — Add to cart
            add_btn = await chosen["el"].query_selector(
                'button[class*="add"], button[class*="Add"], '
                '[class*="addBtn"], [data-testid*="add-to-cart"]'
            )
            if add_btn:
                await add_btn.click()
                await page.wait_for_timeout(2000)
            else:
                await chosen["el"].click()
                await page.wait_for_timeout(1500)

            # Step 6 — Go to cart
            try:
                cart_btn = await page.wait_for_selector(
                    'a[href*="cart"], [data-testid*="cart"], [class*="cart-icon"]',
                    timeout=5000
                )
                await cart_btn.click()
                await page.wait_for_timeout(2000)
            except PWT:
                await page.goto(f"{ZEPTO_URL}/cart", timeout=15000)
                await page.wait_for_timeout(2000)

            # Step 7 — Place order
            try:
                place_btn = await page.wait_for_selector(
                    'button[class*="place"], button[class*="Proceed"], '
                    'button[class*="checkout"], [data-testid*="place-order"]',
                    timeout=6000
                )
                await place_btn.click()
                await page.wait_for_timeout(3000)

                price_info = f" for {chosen['price']} rupees" if chosen['price'] else ""
                store_info2 = f" from {store_name}" if store_name else ""
                _speak(
                    f"Order placed Shivank! "
                    f"{chosen['name']}{store_info2}{price_info}. "
                    f"Track it in the Zepto app."
                )
                if _notify_fn:
                    store_tag = f" from {store_name}" if store_name else ""
                    _notify_fn(
                        f"Zepto Café: {chosen['name']}{store_tag}"
                        + (f" — ₹{chosen['price']}" if chosen['price'] else "")
                    )

            except PWT:
                _speak(
                    f"Added {chosen['name']} to your Zepto cart Shivank. "
                    f"Please open Zepto to complete checkout."
                )

        except Exception as e:
            print(f"[Zepto] Error: {e}")
            _speak("Something went wrong with Zepto. Please order in the app.")
        finally:
            await ctx.close()


# ── Public API ────────────────────────────────────────────────────
def handle(user_text: str) -> str:
    if not is_logged_in():
        return (
            "Zepto is not set up yet Shivank. "
            "Run python zepto_agent.py --login in your terminal first."
        )

    query = user_text.lower()
    for w in ["order", "zepto", "get me", "i want to order", "i want",
              "from zepto", "order from zepto", "zepto cafe", "zepto café"]:
        query = re.sub(rf'\b{re.escape(w)}\b', '', query).strip()
    query = query.strip(" .,?")

    if not query:
        def _ask():
            _speak("What would you like to order from Zepto Café Shivank?")
            q = _listen()
            if q: asyncio.run(_run_order(q))
            else: _speak("Order cancelled.")
        threading.Thread(target=_ask, daemon=True).start()
    else:
        threading.Thread(
            target=lambda: asyncio.run(_run_order(query)),
            daemon=True
        ).start()
    return ""


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--login" in sys.argv:
        print("\n=== Zepto Café Login Setup ===")
        print("Firefox will open — log into Zepto normally.")
        print("Press Enter in terminal once done.\n")
        asyncio.run(_do_login())
    else:
        print("Usage:  python zepto_agent.py --login")
        print("Run once to save your Zepto login session.")
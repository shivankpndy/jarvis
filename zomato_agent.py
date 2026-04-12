"""
JARVIS Zomato Agent — Official Zomato MCP Server
=================================================
Tools confirmed working:
  get_restaurants_for_keyword
  get_restaurant_menu_by_categories
  get_menu_items_listing
  get_saved_addresses_for_user
  create_cart
  checkout_cart
  get_order_history
  get_order_tracking_info
  get_cart_offers

SETUP (one-time):
    1. Install Node.js 18+ from nodejs.org
    2. npx mcp-remote https://mcp-server.zomato.com/mcp
       (browser opens → log in with Zomato account → done)
    3. .env must have HOME_LAT and HOME_LNG
"""

import os, sys, re, json, subprocess, threading, time, base64, tempfile, platform
from dotenv import load_dotenv
load_dotenv(r"D:\JARVIS\.env")

HOME_LAT       = float(os.getenv("HOME_LAT", "26.8467"))
HOME_LNG       = float(os.getenv("HOME_LNG", "80.9462"))
ZOMATO_MCP_URL = "https://mcp-server.zomato.com/mcp"
IS_WINDOWS     = platform.system() == "Windows"

_speak_fn  = None
_listen_fn = None
_notify_fn = None

def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_listen(fn): global _listen_fn; _listen_fn = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn

def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Zomato] {text}")

def _listen(timeout=25):
    if _listen_fn: return _listen_fn(timeout=timeout) or ""
    return input("[Zomato] Your response: ").strip()


# ── MCP JSON-RPC bridge ───────────────────────────────────────────
class ZomatoMCP:
    def __init__(self):
        self._proc = None
        self._id   = 0
        self._lock = threading.Lock()

    def _next_id(self):
        self._id += 1
        return self._id

    def _start(self):
        if self._proc and self._proc.poll() is None:
            return
        print("[Zomato] Starting MCP bridge...")
        cmd = f"npx -y mcp-remote {ZOMATO_MCP_URL}" if IS_WINDOWS else \
              ["npx", "-y", "mcp-remote", ZOMATO_MCP_URL]
        self._proc = subprocess.Popen(
            cmd, shell=IS_WINDOWS,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        self._send_raw({
            "jsonrpc": "2.0", "method": "initialize", "id": self._next_id(),
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "JARVIS", "version": "1.0"},
            }
        })
        resp = self._read_one(timeout=15)
        if resp:
            name = resp.get("result", {}).get("serverInfo", {}).get("name", "Zomato")
            print(f"[Zomato] Connected to {name}")
        self._send_raw({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        time.sleep(0.3)

    def _send_raw(self, obj):
        try:
            self._proc.stdin.write(json.dumps(obj) + "\n")
            self._proc.stdin.flush()
        except Exception as e:
            print(f"[Zomato] Send error: {e}")

    def _read_one(self, timeout=20):
        start = time.time()
        while time.time() - start < timeout:
            try:
                line = self._proc.stdout.readline()
                if not line:
                    time.sleep(0.05)
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    return json.loads(line)
                except:
                    if line:
                        print(f"[Zomato] log: {line[:100]}")
            except Exception as e:
                print(f"[Zomato] Read error: {e}")
                return None
        print("[Zomato] Timeout waiting for response")
        return None

    def call(self, tool: str, args: dict, timeout=25) -> dict | None:
        with self._lock:
            self._start()
            self._send_raw({
                "jsonrpc": "2.0", "method": "tools/call",
                "id": self._next_id(),
                "params": {"name": tool, "arguments": args}
            })
            resp = self._read_one(timeout=timeout)
            if not resp:
                return None
            if "error" in resp:
                print(f"[Zomato] Tool error ({tool}): {resp['error']}")
                return None
            return resp.get("result", {})

    def list_tools(self):
        with self._lock:
            self._start()
            self._send_raw({"jsonrpc": "2.0", "method": "tools/list",
                            "id": self._next_id(), "params": {}})
            resp = self._read_one(timeout=15)
            if resp and "result" in resp:
                return resp["result"].get("tools", [])
        return []


_mcp = ZomatoMCP()


# ── Parse MCP content blocks ──────────────────────────────────────
def _text(result: dict) -> str:
    """Extract text from MCP content array."""
    if not result:
        return ""
    parts = []
    for block in result.get("content", []):
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif block.get("type") == "image":
            data = block.get("data", "")
            mime = block.get("mimeType", "image/png")
            if data:
                ext  = mime.split("/")[-1]
                path = os.path.join(tempfile.gettempdir(), f"zomato_qr.{ext}")
                with open(path, "wb") as f:
                    f.write(base64.b64decode(data))
                parts.append(f"[QR:{path}]")
                try: os.startfile(path)
                except: pass
    return "\n".join(parts)


def _llm_parse(prompt: str) -> str:
    from llm import chat_raw
    r = chat_raw(prompt).strip()
    return re.sub(r'^```(?:json)?\s*|\s*```$', '', r).strip()


# ── Get saved address ─────────────────────────────────────────────
def _get_address_id() -> tuple[str, str]:
    """Returns (address_id, label) from user's saved Zomato addresses."""
    result = _mcp.call("get_saved_addresses_for_user", {})
    raw = _text(result)
    print(f"[Zomato] Addresses: {raw[:300]}")

    parsed = _llm_parse(
        f"Extract address list from this Zomato response.\n"
        f"Return ONLY JSON array: "
        f'[{{"id":"...","label":"Home","full_address":"..."}}]\n\n{raw[:2000]}'
    )
    try:
        addrs = json.loads(parsed)
        if addrs:
            preferred = os.getenv("ZEPTO_ADDRESS", "Home").lower()
            for a in addrs:
                if preferred in a.get("label", "").lower():
                    return a.get("id", ""), a.get("label", "Home")
            return addrs[0].get("id", ""), addrs[0].get("label", "")
    except:
        pass
    return "", ""


# ── Full order flow ───────────────────────────────────────────────
def _order_flow(food_query: str):

    # ── 1. Get address ────────────────────────────────────────────
    _speak(f"Searching Zomato for {food_query} near you sir.")
    addr_id, addr_label = _get_address_id()
    if addr_id:
        print(f"[Zomato] Using address: {addr_label} ({addr_id})")
    else:
        print("[Zomato] No saved address found, using lat/lng directly")

    # ── 2. Search restaurants ─────────────────────────────────────
    search_args = {"keyword": food_query, "latitude": HOME_LAT, "longitude": HOME_LNG}
    if addr_id:
        search_args["address_id"] = addr_id

    result = _mcp.call("get_restaurants_for_keyword", search_args, timeout=20)
    raw    = _text(result)
    print(f"[Zomato] Restaurants raw: {raw[:400]}")

    parsed = _llm_parse(
        f'Extract restaurants from this Zomato response for "{food_query}".\n'
        f"Return ONLY JSON array (max 5):\n"
        f'[{{"id":"...","name":"...","rating":"...","delivery_time":"...mins","price_for_two":"..."}}]\n\n'
        f"{raw[:3000]}"
    )
    try:
        restaurants = json.loads(parsed)
    except:
        restaurants = []

    if not restaurants:
        _speak(f"I couldn't find restaurants for {food_query} near you sir.")
        return

    # ── 3. Present restaurants ────────────────────────────────────
    top = restaurants[:4]
    options = []
    for i, r in enumerate(top):
        line = f"Option {i+1}: {r.get('name','?')}"
        if r.get('rating'):        line += f", rated {r['rating']}"
        if r.get('delivery_time'): line += f", {r['delivery_time']} delivery"
        if r.get('price_for_two'): line += f", around {r['price_for_two']} rupees for two"
        options.append(line)

    _speak("I found these restaurants: " + ". ".join(options) + ". Which would you like sir?")
    choice = _listen()

    if not choice or any(w in choice.lower() for w in ["cancel","stop","never mind"]):
        _speak("Order cancelled sir.")
        return

    chosen_r = _pick(choice, top)
    rest_name = chosen_r.get('name', 'the restaurant')
    rest_id   = chosen_r.get('id', '')
    _speak(f"Great. Getting the menu from {rest_name}.")

    # ── 4. Get menu items ─────────────────────────────────────────
    listing_result = _mcp.call("get_menu_items_listing",
                                {"restaurant_id": rest_id}, timeout=20)
    listing_raw = _text(listing_result)
    print(f"[Zomato] Menu listing: {listing_raw[:300]}")

    # Ask LLM to find category for the food query
    category_prompt = (
        f'From this Zomato menu listing, find the category name that contains "{food_query}".\n'
        f"Return ONLY the category name as a plain string, nothing else.\n\n{listing_raw[:2000]}"
    )
    category = _llm_parse(category_prompt).strip().strip('"')
    print(f"[Zomato] Category for '{food_query}': {category}")

    # Get menu by category
    menu_args = {"restaurant_id": rest_id}
    if category and category.lower() not in ["not found", "none", ""]:
        menu_args["categories"] = [category]

    menu_result = _mcp.call("get_restaurant_menu_by_categories", menu_args, timeout=20)
    menu_raw = _text(menu_result)
    print(f"[Zomato] Menu raw: {menu_raw[:400]}")

    parsed_menu = _llm_parse(
        f'From this Zomato menu, find items matching "{food_query}".\n'
        f"Return ONLY JSON array (max 5):\n"
        f'[{{"id":"...","name":"...","price":"...","description":"..."}}]\n'
        f"Price should be in rupees (number only). No markdown.\n\n{menu_raw[:3000]}"
    )
    try:
        menu_items = json.loads(parsed_menu)
    except:
        menu_items = []

    if not menu_items:
        _speak(f"I couldn't read menu items for {food_query} from {rest_name} sir.")
        return

    # ── 5. Present menu items ─────────────────────────────────────
    item_options = []
    for i, item in enumerate(menu_items[:4]):
        line = f"Option {i+1}: {item.get('name','?')}"
        if item.get('price'): line += f" at {item['price']} rupees"
        if item.get('description'): line += f" — {item['description'][:60]}"
        item_options.append(line)

    _speak(
        f"From {rest_name}: " + ". ".join(item_options) +
        ". Which would you like sir?"
    )
    item_choice = _listen()

    if not item_choice or any(w in item_choice.lower() for w in ["cancel","stop"]):
        _speak("Order cancelled sir.")
        return

    chosen_item = _pick(item_choice, menu_items)
    price_str   = f" for {chosen_item['price']} rupees" if chosen_item.get('price') else ""

    _speak(
        f"Order summary: {chosen_item.get('name','?')} from {rest_name}{price_str}. "
        f"Say yes to place the order, or cancel."
    )
    confirm = _listen()
    if not confirm or any(w in confirm.lower() for w in ["no","cancel","stop"]):
        _speak("Order cancelled sir.")
        return

    # ── 6. Ask payment method ─────────────────────────────────────
    _speak("How would you like to pay sir? Say UPI, cash on delivery, or card.")
    payment_response = _listen()
    if "cash" in payment_response.lower():
        payment_method = "cod"
    elif "card" in payment_response.lower():
        payment_method = "card"
    else:
        payment_method = "upi"   # default to UPI

    # ── 7. Create cart ────────────────────────────────────────────
    _speak(f"Creating your cart sir.")
    cart_args = {
        "restaurant_id": rest_id,
        "items": [{"item_id": chosen_item.get('id',''), "quantity": 1}],
        "payment_method": payment_method,
        "latitude":  HOME_LAT,
        "longitude": HOME_LNG,
    }
    if addr_id:
        cart_args["address_id"] = addr_id

    cart_result = _mcp.call("create_cart", cart_args, timeout=25)
    cart_raw    = _text(cart_result)
    print(f"[Zomato] Cart: {cart_raw[:300]}")

    # Extract cart_id
    cart_id = ""
    cart_parsed = _llm_parse(
        f'Extract cart_id from this response. Return ONLY the cart_id value.\n\n{cart_raw[:1000]}'
    )
    cart_id = cart_parsed.strip().strip('"').strip("'")
    print(f"[Zomato] Cart ID: {cart_id}")

    # ── 8. Check offers ───────────────────────────────────────────
    if cart_id:
        offers_result = _mcp.call("get_cart_offers", {"cart_id": cart_id}, timeout=15)
        offers_raw = _text(offers_result)
        if offers_raw and len(offers_raw) > 20:
            offer_summary = _llm_parse(
                f"Summarize any discount offers in ONE short sentence.\n\n{offers_raw[:1000]}"
            )
            if offer_summary and "not found" not in offer_summary.lower():
                _speak(f"By the way, there's an offer: {offer_summary}")

    # ── 9. Checkout ───────────────────────────────────────────────
    _speak("Placing your order now sir.")
    checkout_args = {"cart_id": cart_id} if cart_id else {
        "restaurant_id": rest_id, "payment_method": payment_method,
        "latitude": HOME_LAT, "longitude": HOME_LNG,
    }
    checkout_result = _mcp.call("checkout_cart", checkout_args, timeout=30)
    checkout_raw    = _text(checkout_result)
    print(f"[Zomato] Checkout: {checkout_raw[:400]}")

    if "[QR:" in checkout_raw:
        _speak(
            f"Order placed sir! A UPI QR code has been opened on your screen. "
            f"Scan it to pay for {chosen_item.get('name')} from {rest_name}."
        )
    else:
        _speak(
            f"Order placed sir! {chosen_item.get('name')} from {rest_name}{price_str}. "
            f"You'll get a confirmation on your Zomato app."
        )

    if _notify_fn:
        _notify_fn(
            f"Zomato: {chosen_item.get('name')} from {rest_name}"
            + (f" — ₹{chosen_item.get('price','')}" if chosen_item.get('price') else "")
        )


# ── Helper: pick item from list by voice choice ───────────────────
def _pick(choice: str, items: list) -> dict:
    num = re.search(r'\b([1-5])\b', choice)
    if num:
        idx = int(num.group(1)) - 1
        if 0 <= idx < len(items):
            return items[idx]
    for item in items:
        name = item.get('name', '') if isinstance(item, dict) else str(item)
        if any(w in name.lower() for w in choice.lower().split() if len(w) > 2):
            return item
    return items[0]


# ── Availability check ────────────────────────────────────────────
def is_available() -> bool:
    try:
        r = subprocess.run(
            "npx --version" if IS_WINDOWS else ["npx", "--version"],
            capture_output=True, timeout=5, shell=IS_WINDOWS
        )
        return r.returncode == 0
    except:
        return False


# ── Public handle ─────────────────────────────────────────────────
def handle(user_text: str) -> str:
    if not is_available():
        return "Node.js is not installed sir. Install from nodejs.org to use Zomato."

    q = user_text.lower().strip()
    for pat in [
        r'\bfrom\s+zomato\b', r'\bvia\s+zomato\b', r'\bon\s+zomato\b', r'\bzomato\b',
        r'\border\b', r'\bget\s+me\b', r'\bi\s+want\s+(?:to\s+order\s+)?',
        r'\bcan\s+you\s+(?:order|get)\b', r'\bplease\b',
    ]:
        q = re.sub(pat, '', q, flags=re.IGNORECASE)
    q = re.sub(r'\s+', ' ', q).strip(" .,?!")

    if not q:
        _speak("What would you like to order from Zomato sir?")
        q = _listen()
        if not q: return "Order cancelled."

    print(f"[Zomato] Ordering: '{q}'")
    threading.Thread(target=lambda item=q: _order_flow(item), daemon=True).start()
    return ""


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    if "--tools" in sys.argv:
        print("Listing Zomato MCP tools...")
        for t in _mcp.list_tools():
            print(f"  {t.get('name')}: {t.get('description','')[:80]}")
    elif "--test" in sys.argv:
        item = " ".join(sys.argv[sys.argv.index("--test")+1:]) or "coffee"
        print(f"\nTesting order: '{item}'")
        _order_flow(item)
    elif "--address" in sys.argv:
        aid, label = _get_address_id()
        print(f"Address: {label} (id={aid})")
    elif "--history" in sys.argv:
        r = _mcp.call("get_order_history", {"latitude": HOME_LAT, "longitude": HOME_LNG})
        print(_text(r)[:1000])
    else:
        print("Usage:")
        print("  python zomato_agent.py --tools            # list MCP tools")
        print("  python zomato_agent.py --test coffee      # test ordering")
        print("  python zomato_agent.py --address          # check saved address")
        print("  python zomato_agent.py --history          # recent orders")
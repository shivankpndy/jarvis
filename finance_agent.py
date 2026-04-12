"""
JARVIS Finance Agent — Yahoo Finance (yfinance)
No API key needed. Works for:
  - Indian stocks (NSE/BSE): Reliance, TCS, Nifty 50 etc.
  - US stocks: Apple, Tesla, Google etc.
  - Crypto: Bitcoin, Ethereum etc.
  - Gold, Silver, Oil
  - Mutual funds, ETFs

Install:
    pip install yfinance

No .env keys required for basic usage.
"""

import re, threading, datetime
import requests
from dotenv import load_dotenv
from llm import chat_raw

load_dotenv(r"D:\JARVIS\.env")

_speak_fn  = None
_notify_fn = None

def set_speak(fn):  global _speak_fn;  _speak_fn  = fn
def set_notify(fn): global _notify_fn; _notify_fn = fn

def _speak(text):
    if _speak_fn: _speak_fn(text)
    else: print(f"[Finance] {text}")


# ── Ticker resolution map ─────────────────────────────────────────
# Maps natural language → Yahoo Finance ticker symbol
# Indian stocks use .NS (NSE) or .BO (BSE) suffix
TICKER_MAP = {
    # ── Indian Indices ────────────────────────────────────────────
    "nifty":           "^NSEI",
    "nifty 50":        "^NSEI",
    "nifty50":         "^NSEI",
    "sensex":          "^BSESN",
    "bank nifty":      "^NSEBANK",
    "banknifty":       "^NSEBANK",
    "nifty bank":      "^NSEBANK",
    "nifty it":        "^CNXIT",
    "nifty midcap":    "^NSEMDCP50",

    # ── Indian Large Caps (NSE) ───────────────────────────────────
    "reliance":        "RELIANCE.NS",
    "ril":             "RELIANCE.NS",
    "tcs":             "TCS.NS",
    "infosys":         "INFY.NS",
    "infy":            "INFY.NS",
    "hdfc bank":       "HDFCBANK.NS",
    "hdfcbank":        "HDFCBANK.NS",
    "hdfc":            "HDFCBANK.NS",
    "icici bank":      "ICICIBANK.NS",
    "icicibank":       "ICICIBANK.NS",
    "icici":           "ICICIBANK.NS",
    "sbi":             "SBIN.NS",
    "state bank":      "SBIN.NS",
    "wipro":           "WIPRO.NS",
    "hcl":             "HCLTECH.NS",
    "hcltech":         "HCLTECH.NS",
    "bajaj finance":   "BAJFINANCE.NS",
    "bajajfin":        "BAJFINANCE.NS",
    "bajaj finserv":   "BAJAJFINSV.NS",
    "kotak":           "KOTAKBANK.NS",
    "kotak bank":      "KOTAKBANK.NS",
    "l&t":             "LT.NS",
    "lt":              "LT.NS",
    "larsen":          "LT.NS",
    "asian paints":    "ASIANPAINT.NS",
    "ultratech":       "ULTRACEMCO.NS",
    "titan":           "TITAN.NS",
    "nestle":          "NESTLEIND.NS",
    "ongc":            "ONGC.NS",
    "power grid":      "POWERGRID.NS",
    "ntpc":            "NTPC.NS",
    "maruti":          "MARUTI.NS",
    "maruti suzuki":   "MARUTI.NS",
    "tata motors":     "TATAMOTORS.NS",
    "tatamotors":      "TATAMOTORS.NS",
    "tata steel":      "TATASTEEL.NS",
    "tatasteel":       "TATASTEEL.NS",
    "adani ports":     "ADANIPORTS.NS",
    "adani green":     "ADANIGREEN.NS",
    "adani ent":       "ADANIENT.NS",
    "adani enterprises": "ADANIENT.NS",
    "sun pharma":      "SUNPHARMA.NS",
    "sunpharma":       "SUNPHARMA.NS",
    "dr reddy":        "DRREDDY.NS",
    "drreddys":        "DRREDDY.NS",
    "cipla":           "CIPLA.NS",
    "divis lab":       "DIVISLAB.NS",
    "zomato":          "ZOMATO.NS",
    "paytm":           "PAYTM.NS",
    "nykaa":           "NYKAA.NS",
    "irctc":           "IRCTC.NS",
    "dmart":           "DMART.NS",
    "avenue supermarts": "DMART.NS",
    "ltimindtree":     "LTIM.NS",
    "lti":             "LTIM.NS",
    "tech mahindra":   "TECHM.NS",
    "techmahindra":    "TECHM.NS",
    "axis bank":       "AXISBANK.NS",
    "axisbank":        "AXISBANK.NS",
    "indusind":        "INDUSINDBK.NS",
    "indusind bank":   "INDUSINDBK.NS",
    "bharti airtel":   "BHARTIARTL.NS",
    "airtel":          "BHARTIARTL.NS",
    "jio":             "RELIANCE.NS",
    "hindalco":        "HINDALCO.NS",
    "jsw steel":       "JSWSTEEL.NS",
    "grasim":          "GRASIM.NS",
    "hero motocorp":   "HEROMOTOCO.NS",
    "hero":            "HEROMOTOCO.NS",
    "bajaj auto":      "BAJAJ-AUTO.NS",
    "eicher":          "EICHERMOT.NS",
    "royal enfield":   "EICHERMOT.NS",
    "upl":             "UPL.NS",
    "britannia":       "BRITANNIA.NS",
    "hul":             "HINDUNILVR.NS",
    "hindustan unilever": "HINDUNILVR.NS",
    "itc":             "ITC.NS",
    "m&m":             "M&M.NS",
    "mahindra":        "M&M.NS",
    "tata power":      "TATAPOWER.NS",
    "tata consumer":   "TATACONSUM.NS",

    # ── US Stocks ─────────────────────────────────────────────────
    "apple":           "AAPL",
    "aapl":            "AAPL",
    "tesla":           "TSLA",
    "tsla":            "TSLA",
    "google":          "GOOGL",
    "alphabet":        "GOOGL",
    "googl":           "GOOGL",
    "microsoft":       "MSFT",
    "msft":            "MSFT",
    "amazon":          "AMZN",
    "amzn":            "AMZN",
    "meta":            "META",
    "facebook":        "META",
    "nvidia":          "NVDA",
    "nvda":            "NVDA",
    "netflix":         "NFLX",
    "nflx":            "NFLX",
    "sp500":           "^GSPC",
    "s&p 500":         "^GSPC",
    "s&p":             "^GSPC",
    "dow jones":       "^DJI",
    "dow":             "^DJI",
    "nasdaq":          "^IXIC",

    # ── Crypto ────────────────────────────────────────────────────
    "bitcoin":         "BTC-USD",
    "btc":             "BTC-USD",
    "ethereum":        "ETH-USD",
    "eth":             "ETH-USD",
    "solana":          "SOL-USD",
    "sol":             "SOL-USD",
    "bnb":             "BNB-USD",
    "xrp":             "XRP-USD",
    "ripple":          "XRP-USD",
    "dogecoin":        "DOGE-USD",
    "doge":            "DOGE-USD",
    "cardano":         "ADA-USD",
    "ada":             "ADA-USD",
    "shib":            "SHIB-USD",

    # ── Commodities ───────────────────────────────────────────────
    "gold":            "GC=F",
    "silver":          "SI=F",
    "crude oil":       "CL=F",
    "oil":             "CL=F",
    "natural gas":     "NG=F",

    # ── Currency ──────────────────────────────────────────────────
    "usd inr":         "INR=X",
    "dollar":          "INR=X",
    "usd to inr":      "INR=X",
    "rupee":           "INR=X",
}

# Tickers that are in INR (to format with ₹ symbol)
INR_SUFFIXES = {".NS", ".BO"}
INR_INDICES  = {"^NSEI", "^BSESN", "^NSEBANK", "^CNXIT", "^NSEMDCP50"}


# ── yfinance fetch ────────────────────────────────────────────────
def _fetch_yf(ticker: str) -> dict | None:
    """
    Fetch quote from Yahoo Finance via yfinance.
    Returns dict with price, change, change_pct, name, currency etc.
    """
    try:
        import yfinance as yf
        tk   = yf.Ticker(ticker)
        info = tk.fast_info   # fast_info is much quicker than .info

        price = getattr(info, "last_price", None)
        if price is None or price == 0:
            # Fallback to history
            hist = tk.history(period="1d", interval="1m")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        if not price:
            return None

        prev_close = getattr(info, "previous_close", None) or price
        change     = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0

        # Get full name from slow info only if needed (cached)
        try:
            name = tk.info.get("longName") or tk.info.get("shortName") or ticker
        except Exception:
            name = ticker

        currency = getattr(info, "currency", "USD")
        day_high = getattr(info, "day_high", None)
        day_low  = getattr(info, "day_low", None)
        volume   = getattr(info, "three_month_average_volume", None)

        return {
            "ticker":     ticker,
            "name":       name,
            "price":      price,
            "change":     change,
            "change_pct": change_pct,
            "day_high":   day_high,
            "day_low":    day_low,
            "currency":   currency,
            "volume":     volume,
        }
    except ImportError:
        print("[Finance] yfinance not installed — run: pip install yfinance")
        return None
    except Exception as e:
        print(f"[Finance] yfinance error for {ticker}: {e}")
        return None


# ── Resolve natural language → ticker ────────────────────────────
def _resolve_ticker(text: str) -> tuple[str, str]:
    """
    Returns (display_name, yahoo_ticker) or ("", "").
    Tries local map first, then LLM extraction, then direct .NS/.BO guess.
    """
    t = text.lower().strip()

    # Try longest match first in our map
    for name in sorted(TICKER_MAP.keys(), key=len, reverse=True):
        if name in t:
            return name, TICKER_MAP[name]

    # Look for an uppercase ticker the user might have said (e.g. "WIPRO", "AAPL")
    tickers = re.findall(r'\b([A-Z]{2,8})\b', text.upper())
    for ticker in tickers:
        # Skip common English words
        if ticker in {"THE", "FOR", "AND", "ARE", "HOW", "WHAT", "PRICE", "STOCK",
                      "TELL", "NOW", "TODAY", "AT", "IS", "OF", "IN", "MY"}:
            continue
        # Try NSE first
        result = _fetch_yf(ticker + ".NS")
        if result and result["price"]:
            return ticker, ticker + ".NS"
        # Try direct (US stock)
        result = _fetch_yf(ticker)
        if result and result["price"]:
            return ticker, ticker

    # LLM extraction as last resort
    try:
        extracted = chat_raw(
            f"Extract just the company name or stock ticker from this query. "
            f"Reply with ONLY the name or ticker, nothing else.\n"
            f"Query: '{text}'"
        ).strip().lower()
        if extracted and extracted in TICKER_MAP:
            return extracted, TICKER_MAP[extracted]
    except Exception:
        pass

    return "", ""


# ── Format spoken response ────────────────────────────────────────
def _format_response(data: dict) -> str:
    ticker = data["ticker"]
    name   = data["name"]
    price  = data["price"]
    chg    = data["change"]
    pct    = data["change_pct"]
    curr   = data["currency"]
    high   = data["day_high"]
    low    = data["day_low"]

    # Currency symbol
    is_inr = (any(ticker.endswith(s) for s in INR_SUFFIXES) or
              ticker in INR_INDICES)
    sym = "₹" if is_inr or curr == "INR" else "$" if curr == "USD" else curr + " "

    # Format price
    if price >= 1000:
        price_str = f"{sym}{price:,.2f}"
    elif price >= 1:
        price_str = f"{sym}{price:.2f}"
    else:
        price_str = f"{sym}{price:.6f}"   # crypto sub-dollar

    direction = "up" if chg >= 0 else "down"
    arrow     = "▲" if chg >= 0 else "▼"

    # Use short name if long name is too verbose for speech
    display = name if len(name) < 40 else ticker

    msg = (f"{display} is at {price_str}, "
           f"{direction} {abs(pct):.2f}% ({arrow}{sym}{abs(chg):.2f}) today sir.")

    if high and low:
        msg += f" Day range {sym}{low:.2f} – {sym}{high:.2f}."

    return msg


# ── Portfolio / watchlist ─────────────────────────────────────────
DEFAULT_WATCHLIST = [
    ("Nifty 50",    "^NSEI"),
    ("Reliance",    "RELIANCE.NS"),
    ("TCS",         "TCS.NS"),
    ("HDFC Bank",   "HDFCBANK.NS"),
    ("Bitcoin",     "BTC-USD"),
]

def get_watchlist_summary(symbols: list = None) -> str:
    """Called from morning_briefing. Returns quick market snapshot."""
    watch = symbols or DEFAULT_WATCHLIST
    lines = []
    for display, ticker in watch[:5]:
        data = _fetch_yf(ticker)
        if data and data["price"]:
            is_inr = any(ticker.endswith(s) for s in INR_SUFFIXES) or ticker in INR_INDICES
            sym    = "₹" if is_inr else "$"
            pct    = data["change_pct"]
            arrow  = "▲" if pct >= 0 else "▼"
            lines.append(f"{display} {sym}{data['price']:,.0f} {arrow}{abs(pct):.1f}%")
    if lines:
        return "Market snapshot: " + ", ".join(lines) + "."
    return ""


# ── Main handler ──────────────────────────────────────────────────
def handle(user_text: str) -> str:
    print(f"[Finance] Query: '{user_text}'")

    display_name, ticker = _resolve_ticker(user_text)

    if not ticker:
        return (
            "I couldn't identify which stock or asset you're asking about sir. "
            "Try saying 'price of Reliance', 'how is Nifty doing', "
            "'Bitcoin price', or 'Apple stock'."
        )

    print(f"[Finance] Resolved: '{display_name}' → {ticker}")
    data = _fetch_yf(ticker)

    if not data or not data["price"]:
        return (
            f"I couldn't fetch the price for {display_name or ticker} right now sir. "
            f"Yahoo Finance may be unavailable or market is closed."
        )

    return _format_response(data)


# ── Standalone test ───────────────────────────────────────────────
if __name__ == "__main__":
    import yfinance as yf
    print("Testing JARVIS Finance Agent (yfinance)...")
    tests = [
        "What is Reliance trading at?",
        "Price of TCS",
        "How is Nifty doing today?",
        "Bitcoin price",
        "Gold price today",
        "Apple stock price",
        "How is Tesla doing?",
        "HDFC Bank price",
    ]
    for q in tests:
        print(f"\nQ: {q}")
        print(f"A: {handle(q)}")
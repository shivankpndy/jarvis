"""
JARVIS Finance Agent
Handles: stocks, crypto, Nifty/Sensex, gold, oil, forex
Uses search_agent as data source — no API key needed.
"""
import re
import ollama
from search_agent import search

BRAIN_MODEL = "llama3.2:3b"

# ── Query builder — makes better search queries ────────────────────
def _build_query(user_text: str) -> str:
    t = user_text.lower()

    # Crypto
    crypto_map = {
        "bitcoin": "Bitcoin BTC price USD today",
        "btc":     "Bitcoin BTC price USD today",
        "ethereum": "Ethereum ETH price USD today",
        "eth":     "Ethereum ETH price USD today",
        "solana":  "Solana SOL price USD today",
        "dogecoin": "Dogecoin DOGE price USD today",
        "doge":    "Dogecoin DOGE price USD today",
    }
    for key, query in crypto_map.items():
        if key in t:
            return query

    # Indian indices
    if any(k in t for k in ["nifty 50", "nifty50", "nifty"]):
        return "Nifty 50 index today price NSE India"
    if any(k in t for k in ["sensex", "bse"]):
        return "BSE Sensex index today price India"
    if "bank nifty" in t:
        return "Bank Nifty index today NSE India"

    # Commodities
    if "gold" in t:
        return "gold price today India per gram 24 karat"
    if "silver" in t:
        return "silver price today India per gram"
    if any(k in t for k in ["crude", "oil"]):
        return "crude oil price today USD per barrel"

    # Forex
    if any(k in t for k in ["usd", "dollar", "rupee", "inr"]):
        return "USD to INR exchange rate today"
    if "euro" in t:
        return "EUR to INR exchange rate today"

    # Extract stock ticker or company name
    # Remove common finance words to isolate the stock name
    for noise in ["stock price", "share price", "stock", "share",
                  "price of", "price", "value of", "value",
                  "how much is", "what is the", "what is",
                  "current", "today", "check", "tell me"]:
        t = t.replace(noise, " ")
    t = " ".join(t.split())

    if t.strip():
        return f"{t.strip()} stock price today NSE BSE India"

    return user_text


# ── Summarize raw search result as finance answer ──────────────────
def _summarize(raw: str, question: str) -> str:
    try:
        prompt = (
            f"You are JARVIS, a financial assistant. "
            f"Based on these search results, give a brief financial answer "
            f"in 1-2 sentences. Address the user as sir. "
            f"Include the actual number/price if you can find it. "
            f"If you cannot find the specific price, say so.\n\n"
            f"Question: {question}\n"
            f"Search results: {raw}\n\n"
            f"Answer:"
        )
        response = ollama.chat(
            model=BRAIN_MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        return response["message"]["content"].strip()
    except Exception as e:
        print(f"[Finance] Ollama error: {e}")
        sentences = re.split(r'(?<=[.!?])\s+', raw)
        return " ".join(sentences[:2])


# ── Voice command handler ──────────────────────────────────────────
def handle(user_text: str) -> str:
    print(f"[Finance] Query: '{user_text}'")

    query = _build_query(user_text)
    print(f"[Finance] Search query: '{query}'")

    raw = search(query)
    if not raw:
        return (
            "I wasn't able to fetch that financial data sir. "
            "Please check your internet connection."
        )

    return _summarize(raw, user_text)
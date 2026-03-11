"""
JARVIS Search Agent — multi-source, robust
Sources (in order of attempt):
  1. DuckDuckGo Instant Answer API  (no key, fast)
  2. Wikipedia REST API             (no key, great for factual)
  3. DuckDuckGo HTML scrape         (fallback)
All results summarized by Ollama before speaking.
"""
import urllib.request
import urllib.parse
import urllib.error
import json
import re
import ollama

BRAIN_MODEL = "llama3.2:3b"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ── Source 1: DuckDuckGo Instant Answer ───────────────────────────
def _ddg_instant(query: str) -> str:
    try:
        params = urllib.parse.urlencode({
            "q": query, "format": "json",
            "no_html": "1", "skip_disambig": "1",
            "t": "jarvis"
        })
        url = f"https://api.duckduckgo.com/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(req, timeout=6) as r:
            data = json.loads(r.read().decode("utf-8"))

        if data.get("AbstractText") and len(data["AbstractText"]) > 40:
            return data["AbstractText"][:700]
        if data.get("Answer"):
            return data["Answer"]

        # Collect related topics
        snippets = []
        for t in data.get("RelatedTopics", [])[:4]:
            if isinstance(t, dict) and t.get("Text") and len(t["Text"]) > 20:
                snippets.append(t["Text"])
        if snippets:
            return " ".join(snippets)[:700]

        return ""
    except Exception as e:
        print(f"[Search] DDG instant error: {e}")
        return ""


# ── Source 2: Wikipedia REST API ──────────────────────────────────
def _wikipedia(query: str) -> str:
    try:
        # Search for best article title
        search_params = urllib.parse.urlencode({"action": "query", "list": "search",
            "srsearch": query, "format": "json", "srlimit": "1"})
        search_url = f"https://en.wikipedia.org/w/api.php?{search_params}"
        req = urllib.request.Request(search_url, headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(req, timeout=6) as r:
            search_data = json.loads(r.read().decode("utf-8"))

        results = search_data.get("query", {}).get("search", [])
        if not results:
            return ""

        title = results[0]["title"]

        # Get summary extract
        extract_params = urllib.parse.urlencode({"action": "query", "prop": "extracts",
            "exintro": "1", "explaintext": "1", "titles": title, "format": "json",
            "exsentences": "4"})
        extract_url = f"https://en.wikipedia.org/w/api.php?{extract_params}"
        req = urllib.request.Request(extract_url, headers={"User-Agent": HEADERS["User-Agent"]})
        with urllib.request.urlopen(req, timeout=6) as r:
            extract_data = json.loads(r.read().decode("utf-8"))

        pages = extract_data.get("query", {}).get("pages", {})
        for page in pages.values():
            extract = page.get("extract", "").strip()
            if extract and len(extract) > 40:
                # Clean up and trim
                extract = re.sub(r'\n+', ' ', extract)
                return f"[Wikipedia: {title}] {extract[:700]}"

        return ""
    except Exception as e:
        print(f"[Search] Wikipedia error: {e}")
        return ""


# ── Source 3: DuckDuckGo HTML scrape ──────────────────────────────
def _ddg_html(query: str) -> str:
    try:
        params = urllib.parse.urlencode({"q": query, "kl": "in-en"})
        url    = f"https://html.duckduckgo.com/html/?{params}"
        req    = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # Extract result snippets
        snippets = []
        # Try result__snippet class
        for chunk in html.split('class="result__snippet"')[1:5]:
            end = chunk.find("</a>")
            if end == -1: end = chunk.find("</span>")
            if end == -1: end = 300
            snippet = chunk[:end]
            # Strip all HTML tags
            snippet = re.sub(r'<[^>]+>', '', snippet).strip()
            snippet = re.sub(r'\s+', ' ', snippet)
            if len(snippet) > 30:
                snippets.append(snippet)

        if snippets:
            return " ".join(snippets)[:800]

        return ""
    except Exception as e:
        print(f"[Search] DDG HTML error: {e}")
        return ""


# ── Source 4: DuckDuckGo Lite (most reliable scrape) ──────────────
def _ddg_lite(query: str) -> str:
    try:
        params  = urllib.parse.urlencode({"q": query})
        url     = f"https://lite.duckduckgo.com/lite/?{params}"
        req     = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as r:
            html = r.read().decode("utf-8", errors="ignore")

        # Extract text from <td class="result-snippet"> tags
        snippets = []
        for chunk in html.split('class="result-snippet"')[1:5]:
            end = chunk.find("</td>")
            if end == -1: end = 400
            snippet = re.sub(r'<[^>]+>', '', chunk[:end]).strip()
            snippet = re.sub(r'\s+', ' ', snippet)
            if len(snippet) > 30:
                snippets.append(snippet)

        if snippets:
            return " ".join(snippets)[:800]
        return ""
    except Exception as e:
        print(f"[Search] DDG lite error: {e}")
        return ""


# ── Main search — tries all sources ───────────────────────────────
def search(query: str) -> str:
    print(f"[Search] Query: '{query}'")

    # Try each source in order
    for name, fn in [
        ("DDG Instant", _ddg_instant),
        ("Wikipedia",   _wikipedia),
        ("DDG Lite",    _ddg_lite),
        ("DDG HTML",    _ddg_html),
    ]:
        result = fn(query)
        if result and len(result.strip()) > 40:
            print(f"[Search] Got result from {name} ({len(result)} chars)")
            return result.strip()
        print(f"[Search] {name}: no result")

    return ""


# ── Summarize with Ollama ──────────────────────────────────────────
def _summarize(raw: str, question: str) -> str:
    try:
        prompt = (
            f"Based on these web search results, answer the question concisely "
            f"for a voice assistant. Be brief — 2 sentences max. "
            f"Address the user as sir. Do not say 'based on search results' or "
            f"'according to'. Just answer naturally.\n\n"
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
        print(f"[Search] Ollama summarize error: {e}")
        # Return trimmed raw result if Ollama fails
        sentences = re.split(r'(?<=[.!?])\s+', raw)
        return " ".join(sentences[:3])


def search_and_summarize(query: str, original_question: str) -> str:
    raw = search(query)
    if not raw:
        return ""
    return _summarize(raw, original_question)


# ── Clean trigger words from query ────────────────────────────────
def _clean_query(text: str) -> str:
    t = text.lower().strip()
    prefixes = [
        "search for", "search the web for", "search the web",
        "search online for", "search online", "search",
        "look up", "look for", "google", "find out about",
        "find out", "find", "browse for",
        "tell me about", "what is", "what are", "who is",
        "who are", "when was", "where is", "why is", "how does",
        "how do", "how is",
    ]
    for p in sorted(prefixes, key=len, reverse=True):  # longest first
        if t.startswith(p):
            query = text[len(p):].strip().lstrip(",").strip()
            if query:
                return query
    return text.strip()


# ── Handle direct voice command ────────────────────────────────────
def handle(user_text: str) -> str:
    query = _clean_query(user_text)
    if not query:
        return "What would you like me to search for sir?"

    print(f"[Search] Cleaned query: '{query}'")
    result = search_and_summarize(query, user_text)

    if result:
        return result
    return (
        "I wasn't able to retrieve search results for that sir. "
        "Please check your internet connection and try again."
    )


# ── Auto-fallback trigger detector ────────────────────────────────
def should_search(user_text: str, ollama_reply: str) -> bool:
    uncertainty = [
        "i don't know", "i'm not sure", "i cannot", "i can't",
        "no information", "not aware", "don't have information",
        "beyond my knowledge", "my training", "as of my",
        "i'm unable", "i do not have", "not certain",
        "i lack", "no data", "don't have access",
        "can't provide", "cannot provide", "i apologize",
        "unfortunately i", "my knowledge cutoff",
        "don't have real-time", "no access to real",
    ]
    # Also trigger on current/live/recent queries
    live_triggers = [
        "current", "latest", "today", "right now", "live",
        "recently", "this week", "this month", "price of",
        "stock price", "weather", "score", "news",
    ]
    reply_lower  = ollama_reply.lower()
    query_lower  = user_text.lower()

    if any(p in reply_lower for p in uncertainty):
        return True
    if any(t in query_lower for t in live_triggers):
        return True
    return False
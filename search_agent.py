"""
JARVIS Search Agent — Serper.dev primary (100 free/day), DDG fallback
Add to .env: SERPER_API_KEY=your_key_from_serper.dev
"""
import os, re, requests
from dotenv import load_dotenv
from llm import chat_raw

load_dotenv(r"D:\JARVIS\.env")

SERPER_KEY      = os.getenv("SERPER_API_KEY", "")
SERPER_ENDPOINT = "https://google.serper.dev/search"

LIVE_TRIGGERS = [
    "current", "latest", "today", "right now", "live",
    "weather", "price of", "score", "news", "stock",
    "what time", "how much is", "rate", "exchange",
    "trending", "breaking", "just happened",
]


def _serper_search(query: str, count: int = 5) -> list[dict]:
    if not SERPER_KEY:
        print("[Search] No SERPER_API_KEY — falling back to DDG")
        return []
    try:
        headers = {"X-API-KEY": SERPER_KEY, "Content-Type": "application/json"}
        payload = {"q": query, "num": count, "gl": "in", "hl": "en"}
        r = requests.post(SERPER_ENDPOINT, headers=headers, json=payload, timeout=8)
        r.raise_for_status()
        data = r.json()
        results = []

        # Answer box — best for factual queries
        if data.get("answerBox"):
            ab = data["answerBox"]
            answer = ab.get("answer") or ab.get("snippet") or ab.get("snippetHighlighted")
            if answer:
                results.append({"title": ab.get("title",""), "url": ab.get("link",""),
                                 "description": answer if isinstance(answer, str) else " ".join(answer)})

        # Knowledge graph
        if data.get("knowledgeGraph"):
            kg = data["knowledgeGraph"]
            desc = kg.get("description","")
            if desc:
                results.append({"title": kg.get("title",""), "url": kg.get("website",""),
                                 "description": desc})

        # Organic results
        for item in data.get("organic", []):
            results.append({
                "title":       item.get("title", ""),
                "url":         item.get("link", ""),
                "description": item.get("snippet", ""),
            })

        return results
    except Exception as e:
        print(f"[Search] Serper error: {e}")
        return []


def _ddg_fallback(query: str) -> str:
    try:
        r = requests.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": 1, "skip_disambig": 1},
            timeout=6
        )
        data = r.json()
        return data.get("AbstractText","") or data.get("Answer","")
    except Exception:
        return ""


def _summarize(query: str, results: list[dict]) -> str:
    if not results: return ""
    # If first result is a direct answer box, return it directly (no LLM needed)
    first_desc = results[0].get("description","")
    if first_desc and len(first_desc) < 200:
        return first_desc

    context = "\n".join(
        f"{i+1}. {r['title']}: {r['description']}"
        for i, r in enumerate(results[:4]) if r.get("description")
    )
    if not context.strip(): return ""
    try:
        prompt = (
            f"Answer this concisely in 1-2 sentences for voice readout.\n"
            f"Question: {query}\nSources:\n{context}\n"
            f"Answer (natural speech, no bullet points):"
        )
        return chat_raw(prompt).strip()
    except Exception:
        return first_desc[:200]


def search(query: str) -> str:
    print(f"[Search] Query: {query}")
    results = _serper_search(query)
    if results:
        answer = _summarize(query, results)
        if answer:
            print(f"[Search] Serper result: {answer[:80]}")
            return answer
    # DDG fallback
    ddg = _ddg_fallback(query)
    if ddg and len(ddg) > 20:
        return ddg[:300]
    return "I couldn't find a clear answer for that sir. Try asking differently."


def handle(user_text: str) -> str:
    query = user_text.lower()
    for filler in ["jarvis","hey","search for","look up","find out","find","what is",
                   "who is","tell me about","search","google","look it up"]:
        query = re.sub(rf'\b{re.escape(filler)}\b', '', query).strip()
    query = query.strip(" ?.,!")
    if not query:
        return "What would you like me to search for sir?"
    return search(query)
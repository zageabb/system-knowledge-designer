from __future__ import annotations

import html
import json
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class ExternalResearchError(ValueError):
    pass


WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
_RESEARCH_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="external-research")


@dataclass
class ResearchCitation:
    title: str
    url: str
    excerpt: str


def sanitise_external_query(value: str) -> str:
    text = value.strip()
    text = re.sub(r"https?://\S+|\bwww\.\S+", " ", text, flags=re.I)
    text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", " ", text)
    text = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b|\b[0-9a-f]{8}-[0-9a-f-]{27,}\b|\b\d{7,}\b", " ", text, flags=re.I)
    text = re.sub(r'"[^"\n]{1,300}"|\'[^\'\n]{1,300}\'', " ", text)
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9-]{1,39}", text)
    generic = " ".join(tokens[:12])
    if len(tokens) < 2:
        raise ExternalResearchError("The query is too specific or sensitive after privacy sanitisation. Use at least two generic public terms.")
    return generic


def search_wikipedia(query: str, *, limit: int = 5, timeout: float = 8, opener=urlopen) -> list[ResearchCitation]:
    params = urlencode({"action": "query", "list": "search", "srsearch": query, "srlimit": min(max(limit, 1), 5), "format": "json", "utf8": 1})
    request = Request(f"{WIKIPEDIA_API}?{params}", headers={"User-Agent": "SystemKnowledgeDesigner/0.1 (local research client)"})
    try:
        with opener(request, timeout=timeout) as response:
            payload = json.loads(response.read(1_000_001))
    except Exception as exc:
        raise ExternalResearchError(f"External research provider failed: {exc}") from exc
    items = payload.get("query", {}).get("search", [])
    citations = []
    for item in items[:5]:
        page_id = int(item["pageid"])
        excerpt = html.unescape(re.sub(r"<[^>]+>", "", str(item.get("snippet", ""))))[:1000]
        citations.append(ResearchCitation(title=str(item.get("title", "Untitled"))[:240], url=f"https://en.wikipedia.org/?curid={page_id}", excerpt=excerpt))
    return citations


def submit_research_task(task):
    """Submit one bounded provider task without coupling the worker to Flask."""
    return _RESEARCH_EXECUTOR.submit(task)

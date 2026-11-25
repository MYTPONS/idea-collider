from __future__ import annotations

import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

DDG_ENDPOINT = "https://html.duckduckgo.com/html/?q="
BING_ENDPOINT = "https://www.bing.com/search?q="


class _BingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._in_li = False
        self._in_h2 = False
        self._in_p = False
        self._href = ""
        self._title: list[str] = []
        self._snippet: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attr = dict(attrs)
        if tag == "li" and "b_algo" in (attr.get("class") or ""):
            self._in_li = True
            self._href = ""
            self._title = []
            self._snippet = []
        elif self._in_li and tag == "h2":
            self._in_h2 = True
        elif self._in_li and tag == "a" and not self._href:
            self._href = attr.get("href") or ""
        elif self._in_li and tag == "p":
            self._in_p = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self._in_h2 = False
        elif tag == "p":
            self._in_p = False
        elif tag == "li" and self._in_li:
            self._in_li = False
            title = " ".join("".join(self._title).split())
            snippet = " ".join("".join(self._snippet).split())
            if title or snippet:
                self.results.append(
                    {"title": title, "url": self._href, "snippet": snippet}
                )

    def handle_data(self, data: str) -> None:
        if self._in_h2:
            self._title.append(data)
        elif self._in_p:
            self._snippet.append(data)


def _fetch(url: str, timeout: int = 20) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Language": "zh-CN,zh;q=0.9"}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "ignore")


def search(query: str, limit: int = 8) -> list[dict[str, str]]:
    url = BING_ENDPOINT + urllib.parse.quote(query)
    body = _fetch(url)
    parser = _BingParser()
    parser.feed(body)
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in parser.results:
        if not item["snippet"] or item["snippet"] in seen:
            continue
        seen.add(item["snippet"])
        out.append(item)
        if len(out) >= limit:
            break
    if out:
        return out
    stripped = re.sub(r"<[^>]+>", " ", body)
    return [{"title": "", "url": "", "snippet": " ".join(stripped.split())[:2000]}]

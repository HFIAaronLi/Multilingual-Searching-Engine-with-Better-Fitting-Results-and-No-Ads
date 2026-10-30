#!/usr/bin/env python3
"""Terminal Search: multilingual, bilingual, ad-filtered terminal search."""

import json
import os
import queue
import re
import threading
import time
import unicodedata
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table


console = Console()
CONFIG_PATH = Path.home() / ".tsearch.json"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
REQUEST_TIMEOUT = (4, 8)
MAX_ARTICLE_BYTES = 2_000_000
DEFAULT_POOL = ["google", "bing", "duckduckgo", "yahoo", "baidu", "brave"]
CUSTOM_PREFIX = "custom:"
CONFIG_VERSION = 2


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str
    score: float = 0.0


HELP_TEXT = """
Commands / 命令
  :new                 Start a new topic / 开始新话题
  :next / n            Next page / 下一页
  :prev / p            Previous page / 上一页
  :open <number>       Open a result / 打开指定编号的结果
  :summary <number>    Summarize a result page / 提取指定网页的段落摘要
  :pool <names>        Set engines or add domains / 设置引擎或直接添加域名
  :pool reset          Restore the default pool / 恢复默认搜索池
  :lang auto|<code>    Set result language / 设置搜索结果语言
  :filter on|off       Toggle ad and junk filtering / 开关广告及垃圾内容过滤
  :exit / q            Quit / 退出

Language / 语言
  auto means no added language restriction / auto 表示不附加语言限制
  Examples / 示例：:lang zh、:lang en、:lang ja、:lang fr、:lang zh-CN
  This changes the search language, not the bilingual interface.
  此命令只改变搜索语言，不改变中英双语界面。

Search engines / 搜索引擎
  :pool                         List engines / 查看引擎
  :pool google,bing,yahoo      Use named engines / 使用指定内置引擎
  :pool yahoo.hk               Add a custom domain / 添加自定义域名引擎
  :pool google,yahoo.jp,baidu.com
                               Mix built-ins and domains / 混合使用内置引擎与域名
  Custom domains use a best-effort parser and follow site redirects.
  自定义域名会尽力解析网页，并跟随网站自身跳转；能否使用取决于网站和网络。

Summaries / 摘要
  Result rows preview the first, second, and last available text units.
  搜索结果会预览现有文本的首段、次段和末段。
  :summary <number> fetches that page and previews P1, P2, and Last.
  :summary <编号> 会读取对应网页，并分别显示首段、次段和末段的开头。
""".strip()


AD_HOSTS = {
    "doubleclick.net",
    "googleadservices.com",
    "googlesyndication.com",
    "google-analytics.com",
    "ad.doubleclick.net",
    "adservice.google.com",
    "ads.yahoo.com",
    "adserver.yahoo.com",
    "ads.baidu.com",
}

AD_LABEL_RE = re.compile(
    r"(?:^|[\s|·•\[(【])"
    r"(?:ad|ads|sponsored|promoted|advertisement|广告|推广|赞助内容)"
    r"(?:$|[\s|·•\])】])",
    re.IGNORECASE,
)

BOILERPLATE_RE = re.compile(
    r"^(?:subscribe|sign up|newsletter|advertisement|share this|"
    r"all rights reserved|cookie settings|订阅|注册|广告|分享本文|版权所有)",
    re.IGNORECASE,
)

LANGUAGE_MARKETS = {
    "ar": "ar-SA",
    "de": "de-DE",
    "en": "en-US",
    "es": "es-ES",
    "fr": "fr-FR",
    "it": "it-IT",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "nl": "nl-NL",
    "pt": "pt-BR",
    "ru": "ru-RU",
    "zh": "zh-CN",
}

DUCKDUCKGO_REGIONS = {
    "de": "de-de",
    "en": "us-en",
    "es": "es-es",
    "fr": "fr-fr",
    "it": "it-it",
    "ja": "jp-jp",
    "ko": "kr-kr",
    "nl": "nl-nl",
    "pt": "br-pt",
    "ru": "ru-ru",
    "zh": "cn-zh",
}


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def shorten(text: str, limit: int) -> str:
    text = clean_text(text)
    return text if len(text) <= limit else text[:limit].rstrip() + "…"


def split_text_units(text: str) -> List[str]:
    """Split real paragraphs first; use sentences as a snippet fallback."""
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    paragraphs = [clean_text(p) for p in re.split(r"\n\s*\n|\n", normalized)]
    paragraphs = [p for p in paragraphs if p]
    if len(paragraphs) > 1:
        return paragraphs
    sentences = re.split(
        r"(?<=[。！？!?；;])|(?<=[.!?])\s+(?=[A-Z0-9])",
        paragraphs[0],
    )
    return [clean_text(s) for s in sentences if clean_text(s)]


def paragraph_preview(text_or_paragraphs, width: int = 72) -> str:
    if isinstance(text_or_paragraphs, str):
        units = split_text_units(text_or_paragraphs)
    else:
        units = [clean_text(p) for p in text_or_paragraphs if clean_text(p)]
    if not units:
        return ""
    if len(units) == 1:
        selected = [("P1 首段", units[0])]
    elif len(units) == 2:
        selected = [("P1 首段", units[0]), ("Last 末段", units[-1])]
    else:
        selected = [
            ("P1 首段", units[0]),
            ("P2 次段", units[1]),
            ("Last 末段", units[-1]),
        ]
    return "  |  ".join(f"{label}: {shorten(text, width)}" for label, text in selected)


def tokenize(text: str) -> List[str]:
    """Unicode-friendly tokens; no language-specific query detection."""
    text = unicodedata.normalize("NFKC", text or "").lower()
    words = re.findall(r"[^\W_]+", text, flags=re.UNICODE)
    tokens = list(words)
    for word in words:
        if re.search(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]", word):
            tokens.extend(word)
            tokens.extend(word[i : i + 2] for i in range(len(word) - 1))
    return tokens


def relevance_score(query: str, title: str, snippet: str) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 0.0
    title_tokens = set(tokenize(title))
    snippet_tokens = set(tokenize(snippet))
    return (
        len(query_tokens & title_tokens) * 3.0
        + len(query_tokens & snippet_tokens)
    ) / len(query_tokens)


def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        url = "https:" + url
    elif url.startswith("www."):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        if "duckduckgo.com" in host and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [""])[0]
            if target:
                url = unquote(target)
        elif "google." in host and parsed.path == "/url":
            target = parse_qs(parsed.query).get("q", [""])[0]
            if target:
                url = unquote(target)
        elif "search.yahoo." in host and "/RU=" in parsed.path:
            match = re.search(r"/RU=([^/]+)", parsed.path)
            if match:
                url = unquote(match.group(1))
    except (ValueError, UnicodeError):
        pass
    return url


def valid_web_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except ValueError:
        return False


def is_ad_or_junk(title: str, snippet: str, url: str) -> bool:
    """Filter explicit ad labels and known ad hosts, not ordinary topic words."""
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return True
    if any(host == domain or host.endswith("." + domain) for domain in AD_HOSTS):
        return True
    lowered_path = urlparse(url).path.lower()
    if any(marker in lowered_path for marker in ("/adserver", "/doubleclick")):
        return True
    return bool(AD_LABEL_RE.search(f"{title or ''} {snippet or ''}"))


def dedupe(results: Iterable[SearchResult]) -> List[SearchResult]:
    seen = set()
    output = []
    for result in results:
        key = result.url.split("#", 1)[0].rstrip("/").lower()
        if key and key not in seen:
            seen.add(key)
            output.append(result)
    return output


def valid_language_code(code: str) -> bool:
    return code == "auto" or bool(
        re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", code)
    )


def language_name(code: str) -> str:
    if code == "auto":
        return "auto (no restriction / 不限制)"
    return code


def load_config() -> dict:
    try:
        with CONFIG_PATH.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def save_config(
    lang: str,
    pool: Sequence[str],
    filter_ads: bool,
    custom_engines: dict = None,
) -> None:
    data = {
        "config_version": CONFIG_VERSION,
        "lang": lang,
        "pool": list(pool),
        "filter_ads": filter_ads,
        "custom_engines": sorted((custom_engines or {}).values()),
    }
    try:
        with CONFIG_PATH.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError:
        # Search remains usable if the home directory is not writable.
        pass


def request_headers(lang: str = "auto") -> dict:
    headers = {"User-Agent": USER_AGENT}
    if lang != "auto":
        headers["Accept-Language"] = lang
    return headers


class BingProvider:
    name = "bing"

    def search(self, query: str, lang: str = "auto") -> List[SearchResult]:
        params = {"q": query, "count": 10}
        if lang != "auto":
            params["setlang"] = lang
            base_lang = lang.lower().split("-", 1)[0]
            if base_lang in LANGUAGE_MARKETS:
                params["mkt"] = LANGUAGE_MARKETS[base_lang]
        response = requests.get(
            "https://www.bing.com/search",
            params=params,
            headers=request_headers(lang),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        output = []
        for item in soup.select("li.b_algo")[:10]:
            link = item.select_one("h2 a") or item.find("a")
            if not link:
                continue
            paragraph = item.find("p")
            output.append(
                SearchResult(
                    title=link.get_text(" ", strip=True),
                    url=normalize_url(link.get("href", "")),
                    snippet=paragraph.get_text(" ", strip=True) if paragraph else "",
                    source=self.name,
                )
            )
        return output


class DuckDuckGoProvider:
    name = "duckduckgo"

    def search(self, query: str, lang: str = "auto") -> List[SearchResult]:
        data = {"q": query}
        if lang != "auto":
            base_lang = lang.lower().split("-", 1)[0]
            if base_lang in DUCKDUCKGO_REGIONS:
                data["kl"] = DUCKDUCKGO_REGIONS[base_lang]
        response = requests.post(
            "https://html.duckduckgo.com/html/",
            data=data,
            headers=request_headers(lang),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        output = []
        for link in soup.select(".result__a")[:10]:
            parent = link.find_parent("div", class_="result")
            snippet = parent.select_one(".result__snippet") if parent else None
            output.append(
                SearchResult(
                    title=link.get_text(" ", strip=True),
                    url=normalize_url(link.get("href", "")),
                    snippet=snippet.get_text(" ", strip=True) if snippet else "",
                    source=self.name,
                )
            )
        return output


class BaiduProvider:
    name = "baidu"

    def search(self, query: str, lang: str = "auto") -> List[SearchResult]:
        response = requests.get(
            "https://www.baidu.com/s",
            params={"wd": query, "rn": 10},
            headers=request_headers(lang),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        output = []
        for item in soup.select("div.result, div.c-container")[:10]:
            link = item.select_one("h3 a") or item.find("a")
            if not link:
                continue
            output.append(
                SearchResult(
                    title=link.get_text(" ", strip=True),
                    url=normalize_url(link.get("href", "")),
                    snippet=clean_text(item.get_text(" ", strip=True))[:500],
                    source=self.name,
                )
            )
        return output


COMMON_ITEM_SELECTORS = (
    "li.b_algo",
    "div.MjjYud",
    "div.g",
    "div.algo",
    "div.snippet",
    "article.result",
    "div.result",
    "li.serp-item",
    "ul.results-standard li",
    "li.res-list",
    "div.vrwrap",
    "div.rb",
)


def parse_html_results(
    html: str,
    base_url: str,
    source: str,
    item_selectors: Sequence[str] = COMMON_ITEM_SELECTORS,
    snippet_selectors: Sequence[str] = (),
) -> List[SearchResult]:
    """Parse common result layouts, then fall back to result headings."""
    soup = BeautifulSoup(html, "html.parser")
    output = []
    seen = set()

    def add_result(link, container) -> None:
        if not link:
            return
        title = clean_text(link.get_text(" ", strip=True))
        href = link.get("href", "")
        if not title or not href or href.startswith(("javascript:", "mailto:")):
            return
        url = normalize_url(urljoin(base_url, href))
        if not valid_web_url(url):
            return
        try:
            result_host = (urlparse(url).hostname or "").lower()
            base_host = (urlparse(base_url).hostname or "").lower()
            result_path = urlparse(url).path.lower()
            if result_host == base_host and result_path.startswith(
                ("/search", "/preferences", "/settings", "/login")
            ):
                return
        except ValueError:
            return
        key = url.split("#", 1)[0].rstrip("/").lower()
        if key in seen:
            return
        snippet = ""
        if container:
            for selector in snippet_selectors:
                element = container.select_one(selector)
                if element:
                    snippet = clean_text(element.get_text(" ", strip=True))
                    break
            if not snippet:
                paragraph = container.find("p")
                if paragraph:
                    snippet = clean_text(paragraph.get_text(" ", strip=True))
            if not snippet:
                snippet = clean_text(container.get_text(" ", strip=True))[:500]
        seen.add(key)
        output.append(SearchResult(title, url, snippet[:500], source))

    items = soup.select(", ".join(item_selectors)) if item_selectors else []
    for item in items:
        heading = item.find(["h2", "h3"])
        link = None
        if heading:
            link = heading.find("a") or heading.find_parent("a")
        if not link:
            link = item.select_one(
                "h2 a, h3 a, a.result-title, a.result__a, a.result-header"
            )
        add_result(link, item)
        if len(output) >= 10:
            return output[:10]

    if not output:
        for heading in soup.find_all(["h2", "h3"]):
            link = heading.find("a") or heading.find_parent("a")
            container = (
                link.find_parent(["li", "article"])
                if link
                else None
            ) or heading.parent
            add_result(link, container)
            if len(output) >= 10:
                break
    return output[:10]


class HTMLProvider:
    def __init__(
        self,
        name: str,
        endpoint: str,
        query_param: str = "q",
        item_selectors: Sequence[str] = COMMON_ITEM_SELECTORS,
        snippet_selectors: Sequence[str] = (),
        extra_params: dict = None,
        language_param: str = None,
    ):
        self.name = name
        self.endpoint = endpoint
        self.query_param = query_param
        self.item_selectors = tuple(item_selectors)
        self.snippet_selectors = tuple(snippet_selectors)
        self.extra_params = extra_params or {}
        self.language_param = language_param

    def search(self, query: str, lang: str = "auto") -> List[SearchResult]:
        params = dict(self.extra_params)
        params[self.query_param] = query
        if lang != "auto" and self.language_param:
            params[self.language_param] = lang
        response = requests.get(
            self.endpoint,
            params=params,
            headers=request_headers(lang),
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )
        response.raise_for_status()
        return parse_html_results(
            response.text,
            response.url,
            self.name,
            self.item_selectors,
            self.snippet_selectors,
        )


def custom_provider(target: str) -> Tuple[str, HTMLProvider]:
    """Create a provider from a user-supplied domain without changing its region."""
    value = (target or "").strip()
    if not value or re.search(r"\s", value):
        raise ValueError("empty or invalid domain")
    if "://" not in value:
        value = "https://" + value
    parsed = urlparse(value)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("enter a domain only")
    host = parsed.hostname.lower().rstrip(".")
    if not host or ("." not in host and host != "localhost"):
        raise ValueError("invalid domain")
    netloc = parsed.netloc.lower()
    bare_netloc = netloc[4:] if netloc.startswith("www.") else netloc
    bare_host = host[4:] if host.startswith("www.") else host
    scheme = parsed.scheme

    query_param = "q"
    extra_params = {}
    item_selectors = COMMON_ITEM_SELECTORS
    snippet_selectors = ()

    if "yahoo." in bare_host:
        search_host = netloc if bare_host.startswith("search.") else f"search.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/search"
        query_param = "p"
        item_selectors = ("div.algo", "div.dd.algo")
        snippet_selectors = (".compText", ".lh-16", ".fc-falcon")
    elif "google." in bare_host:
        search_host = netloc if bare_host.startswith("www.") else f"www.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/search"
        extra_params = {"num": 10}
        item_selectors = ("div.MjjYud", "div.g")
        snippet_selectors = (".VwiC3b", ".yXK7lf", ".aCOpRe")
    elif "baidu." in bare_host:
        search_host = netloc if bare_host.startswith("www.") else f"www.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/s"
        query_param = "wd"
        extra_params = {"rn": 10}
        item_selectors = ("div.result", "div.c-container")
    elif "duckduckgo." in bare_host:
        search_host = netloc if bare_host.startswith("html.") else f"html.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/html/"
        item_selectors = ("div.result",)
        snippet_selectors = (".result__snippet",)
    elif "brave." in bare_host:
        search_host = netloc if bare_host.startswith("search.") else f"search.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/search"
        item_selectors = ("div.snippet", "div.result")
        snippet_selectors = (".snippet-description", ".result-description")
    elif "ecosia." in bare_host:
        search_host = netloc if bare_host.startswith("www.") else f"www.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/search"
        item_selectors = ("article.result", "div.result")
        snippet_selectors = (".result__description", ".result-description")
    elif "yandex." in bare_host:
        endpoint = f"{scheme}://{netloc}/search/"
        query_param = "text"
        item_selectors = ("li.serp-item",)
        snippet_selectors = (".OrganicTextContentSpan", ".TextContainer")
    elif "mojeek." in bare_host:
        search_host = netloc if bare_host.startswith("www.") else f"www.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/search"
        item_selectors = ("ul.results-standard li",)
        snippet_selectors = ("p.s",)
    elif "sogou." in bare_host:
        search_host = netloc if bare_host.startswith("www.") else f"www.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/web"
        query_param = "query"
        item_selectors = ("div.vrwrap", "div.rb")
    elif bare_host == "so.com" or bare_host.endswith(".so.com"):
        search_host = netloc if bare_host.startswith("www.") else f"www.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/s"
        item_selectors = ("li.res-list",)
        snippet_selectors = (".res-desc",)
    elif "naver." in bare_host:
        search_host = netloc if bare_host.startswith("search.") else f"search.{bare_netloc}"
        endpoint = f"{scheme}://{search_host}/search.naver"
        query_param = "query"
    else:
        endpoint = f"{scheme}://{netloc}/search"

    display_name = bare_host + (f":{parsed.port}" if parsed.port else "")
    provider = HTMLProvider(
        display_name,
        endpoint,
        query_param,
        item_selectors,
        snippet_selectors,
        extra_params,
    )
    return display_name, provider


class SearXNGProvider:
    name = "searxng"

    def __init__(self, base_url: str = "http://127.0.0.1:8888"):
        self.base_url = base_url.rstrip("/")

    def search(self, query: str, lang: str = "auto") -> List[SearchResult]:
        params = {"q": query, "format": "json"}
        if lang != "auto":
            params["language"] = lang
        response = requests.get(
            f"{self.base_url}/search",
            params=params,
            headers=request_headers(lang),
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        output = []
        for item in data.get("results", [])[:10]:
            output.append(
                SearchResult(
                    title=clean_text(item.get("title", "")),
                    url=normalize_url(item.get("url", "")),
                    snippet=clean_text(item.get("content", "")),
                    source=self.name,
                )
            )
        return output


class Engine:
    def __init__(self):
        config = load_config()
        self.lang = config.get("lang", "auto")
        if not isinstance(self.lang, str) or not valid_language_code(self.lang):
            self.lang = "auto"
        self.lang = self.lang.lower()
        self.page_size = 10
        self.timeout = 10
        self.filter_ads = bool(config.get("filter_ads", True))
        self.current_query = None
        self.current_page = 1
        self.raw_results = []
        self.all_results = []
        self.last_failed = []
        self.has_fetched = False
        self.providers = {
            "google": HTMLProvider(
                "google",
                "https://www.google.com/search",
                item_selectors=("div.MjjYud", "div.g"),
                snippet_selectors=(".VwiC3b", ".yXK7lf", ".aCOpRe"),
                extra_params={"num": 10},
                language_param="hl",
            ),
            "bing": BingProvider(),
            "duckduckgo": DuckDuckGoProvider(),
            "yahoo": HTMLProvider(
                "yahoo",
                "https://search.yahoo.com/search",
                query_param="p",
                item_selectors=("div.algo", "div.dd.algo"),
                snippet_selectors=(".compText", ".lh-16", ".fc-falcon"),
            ),
            "baidu": BaiduProvider(),
            "brave": HTMLProvider(
                "brave",
                "https://search.brave.com/search",
                item_selectors=("div.snippet", "div.result"),
                snippet_selectors=(".snippet-description", ".result-description"),
            ),
            "ecosia": HTMLProvider(
                "ecosia",
                "https://www.ecosia.org/search",
                item_selectors=("article.result", "div.result"),
                snippet_selectors=(".result__description", ".result-description"),
            ),
            "yandex": HTMLProvider(
                "yandex",
                "https://yandex.com/search/",
                query_param="text",
                item_selectors=("li.serp-item",),
                snippet_selectors=(".OrganicTextContentSpan", ".TextContainer"),
            ),
            "mojeek": HTMLProvider(
                "mojeek",
                "https://www.mojeek.com/search",
                item_selectors=("ul.results-standard li",),
                snippet_selectors=("p.s",),
            ),
            "sogou": HTMLProvider(
                "sogou",
                "https://www.sogou.com/web",
                query_param="query",
                item_selectors=("div.vrwrap", "div.rb"),
            ),
            "searxng": SearXNGProvider(
                os.environ.get("TSEARCH_SEARXNG_URL", "http://127.0.0.1:8888")
            ),
        }
        self.custom_engines = {}
        self.invalid_engines = []
        raw_custom = config.get("custom_engines", [])
        if isinstance(raw_custom, list):
            for target in raw_custom:
                if not isinstance(target, str):
                    continue
                try:
                    self.register_custom(target)
                except (ValueError, TypeError):
                    continue
        raw_pool = config.get("pool") or DEFAULT_POOL
        if (
            config.get("config_version", 1) != CONFIG_VERSION
            and raw_pool == ["bing", "duckduckgo"]
        ):
            # Migrate the previous implicit two-engine default to the expanded pool.
            raw_pool = DEFAULT_POOL
        if not isinstance(raw_pool, list):
            raw_pool = DEFAULT_POOL
        self.pool = [
            name
            for name in raw_pool
            if isinstance(name, str) and name in self.providers
        ]
        if not self.pool:
            self.pool = list(DEFAULT_POOL)

    def register_custom(self, target: str) -> str:
        name, provider = custom_provider(target)
        key = CUSTOM_PREFIX + name
        self.providers[key] = provider
        self.custom_engines[key] = target
        return key

    def display_engine(self, key: str) -> str:
        provider = self.providers.get(key)
        return provider.name if provider and key.startswith(CUSTOM_PREFIX) else key

    def pool_display(self) -> str:
        return ", ".join(self.display_engine(name) for name in self.pool)

    def save(self) -> None:
        save_config(self.lang, self.pool, self.filter_ads, self.custom_engines)

    def invalidate_search(self) -> None:
        self.current_page = 1
        self.raw_results = []
        self.all_results = []
        self.last_failed = []
        self.has_fetched = False

    def set_pool(self, names: Sequence[str]) -> List[str]:
        valid = []
        self.invalid_engines = []
        for raw_name in names:
            name = raw_name.strip()
            if not name:
                continue
            key = name if name in self.providers else name.lower()
            if key not in self.providers:
                try:
                    key = self.register_custom(name)
                except (ValueError, TypeError):
                    self.invalid_engines.append(name)
                    continue
            if key not in valid:
                valid.append(key)
        if valid:
            self.pool = valid
            self.invalidate_search()
            self.save()
        return valid

    def set_lang(self, lang: str) -> bool:
        lang = lang.lower()
        if lang == "all":
            lang = "auto"
        if not valid_language_code(lang):
            return False
        self.lang = lang
        self.invalidate_search()
        self.save()
        return True

    def set_filter(self, enabled: bool) -> None:
        self.filter_ads = enabled
        self.save()
        if self.has_fetched and self.current_query:
            self.all_results = self.process_results(self.current_query, self.raw_results)
            self.current_page = 1

    def new_topic(self, query: str) -> None:
        self.current_query = query
        self.invalidate_search()

    def fetch(self, query: str) -> Tuple[List[SearchResult], List[str]]:
        result_queue = queue.Queue()
        failed = set()

        def worker(name):
            try:
                results = self.providers[name].search(query, self.lang)
                result_queue.put((name, results, not results))
            except Exception:
                result_queue.put((name, [], True))

        threads = []
        for name in self.pool:
            thread = threading.Thread(target=worker, args=(name,), daemon=True)
            thread.start()
            threads.append((name, thread))

        collected = []
        deadline = time.monotonic() + self.timeout
        finished = set()
        while len(finished) < len(threads):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                name, results, did_fail = result_queue.get(timeout=min(0.25, remaining))
                finished.add(name)
                if did_fail:
                    failed.add(name)
                else:
                    collected.extend(results)
            except queue.Empty:
                if all(not thread.is_alive() for _, thread in threads):
                    break

        for name, thread in threads:
            if name not in finished and thread.is_alive():
                failed.add(name)
        return collected, sorted(failed)

    def process_results(
        self, query: str, results: Iterable[SearchResult]
    ) -> List[SearchResult]:
        cleaned = []
        for result in results:
            result.title = clean_text(result.title)
            result.snippet = result.snippet.strip()
            result.url = normalize_url(result.url)
            if not result.title or not valid_web_url(result.url):
                continue
            if self.filter_ads and is_ad_or_junk(result.title, result.snippet, result.url):
                continue
            result.score = relevance_score(query, result.title, result.snippet)
            cleaned.append(result)
        return sorted(dedupe(cleaned), key=lambda item: item.score, reverse=True)

    def search(self, query: str):
        if query != self.current_query:
            self.new_topic(query)
        if not self.has_fetched:
            self.raw_results, self.last_failed = self.fetch(query)
            self.all_results = self.process_results(query, self.raw_results)
            self.has_fetched = True
        return self.page(self.current_page)

    @property
    def page_count(self) -> int:
        return max(1, (len(self.all_results) + self.page_size - 1) // self.page_size)

    def page(self, page: int) -> List[SearchResult]:
        start = (page - 1) * self.page_size
        return self.all_results[start : start + self.page_size]

    def next_page(self) -> bool:
        if self.current_page >= self.page_count:
            return False
        self.current_page += 1
        return True

    def prev_page(self) -> bool:
        if self.current_page <= 1:
            return False
        self.current_page -= 1
        return True

    def result_at(self, number: int) -> SearchResult:
        if number < 1 or number > len(self.all_results):
            raise IndexError(number)
        return self.all_results[number - 1]


def extract_article_paragraphs(url: str) -> List[str]:
    response = requests.get(
        url,
        headers=request_headers(),
        timeout=REQUEST_TIMEOUT,
        stream=True,
        allow_redirects=True,
    )
    response.raise_for_status()
    content_type = response.headers.get("Content-Type", "").lower()
    if content_type and "html" not in content_type and "text/plain" not in content_type:
        raise ValueError("not an HTML or text page / 不是 HTML 或文本网页")

    chunks = []
    size = 0
    for chunk in response.iter_content(chunk_size=65536):
        if not chunk:
            continue
        size += len(chunk)
        if size > MAX_ARTICLE_BYTES:
            raise ValueError("page is too large / 网页内容过大")
        chunks.append(chunk)
    content = b"".join(chunks)

    if "text/plain" in content_type:
        text = content.decode(response.encoding or "utf-8", errors="replace")
        return [clean_text(p) for p in re.split(r"\n\s*\n|\n", text) if clean_text(p)]

    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(
        ["script", "style", "noscript", "svg", "form", "nav", "footer", "aside"]
    ):
        tag.decompose()
    for tag in soup.select(
        ".advertisement, .ads, .ad-container, .social-share, .related-posts, "
        "[class*='cookie'], [id*='cookie'], [aria-label='advertisement']"
    ):
        tag.decompose()

    root = (
        soup.select_one("article")
        or soup.select_one("main")
        or soup.select_one(".article-content, .post-content, .entry-content")
        or soup.body
        or soup
    )
    paragraphs = []
    seen = set()
    for element in root.find_all("p"):
        text = clean_text(element.get_text(" ", strip=True))
        if len(text) < 2 or BOILERPLATE_RE.search(text) or text in seen:
            continue
        seen.add(text)
        paragraphs.append(text)
    if not paragraphs:
        text = root.get_text("\n", strip=True)
        for line in re.split(r"\n\s*\n|\n", text):
            line = clean_text(line)
            if len(line) >= 20 and not BOILERPLATE_RE.search(line) and line not in seen:
                seen.add(line)
                paragraphs.append(line)
    if not paragraphs:
        raise ValueError("no readable paragraphs found / 未找到可读段落")
    return paragraphs


def show_results(engine: Engine, results: Sequence[SearchResult]) -> None:
    start = (engine.current_page - 1) * engine.page_size
    table = Table(
        title=(
            f"Results 结果 | {engine.current_query} | "
            f"Page 页 {engine.current_page}/{engine.page_count}"
        )
    )
    table.add_column("#", justify="right", style="cyan", width=4)
    table.add_column("Title 标题", style="magenta", max_width=36, overflow="fold")
    table.add_column("Summary 摘要", style="white", max_width=68, overflow="fold")
    table.add_column("URL 网址", style="green", max_width=42, overflow="fold")
    table.add_column("Source 来源", style="yellow", width=18)
    for index, result in enumerate(results, start=start + 1):
        table.add_row(
            str(index),
            result.title,
            paragraph_preview(result.snippet, width=54),
            result.url,
            result.source,
        )
    console.print(table)


def show_article_summary(engine: Engine, number: int) -> None:
    try:
        result = engine.result_at(number)
    except IndexError:
        console.print("Invalid result number. / 无效的结果编号。")
        return
    console.print("Fetching page… / 正在读取网页……")
    try:
        paragraphs = extract_article_paragraphs(result.url)
    except Exception as error:
        detail = shorten(str(error), 160)
        console.print(
            escape(f"Could not summarize this page. / 无法生成网页摘要。 {detail}")
        )
        return
    console.print(escape(f"{result.title}\n{result.url}"))
    console.print(
        Panel(
            escape(paragraph_preview(paragraphs, width=140)),
            title="Paragraph summary / 段落摘要",
            border_style="cyan",
        )
    )


def print_language(engine: Engine) -> None:
    console.print(
        f"Search language / 搜索语言: {language_name(engine.lang)}\n"
        "Use :lang auto for no restriction, or a code such as zh, en, ja, fr.\n"
        "使用 :lang auto 解除限制，或输入 zh、en、ja、fr 等语言代码。"
    )


def main() -> None:
    engine = Engine()
    filter_state = "on / 开" if engine.filter_ads else "off / 关"
    console.print(
        Panel.fit(
            "[bold]Terminal Search / 终端搜索[/bold]\n"
            f"Search language / 搜索语言: {language_name(engine.lang)}\n"
            f"Search pool / 搜索池: {engine.pool_display()}\n"
            f"Ad filtering / 广告过滤: {filter_state}\n"
            "[dim]Type :help for commands. / 输入 :help 查看命令。[/dim]",
            border_style="cyan",
        )
    )

    while True:
        try:
            user_input = console.input("[bold cyan]Search 搜索 > [/bold cyan]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\nBye! / 再见！")
            break
        if not user_input:
            continue

        if not user_input.startswith(":"):
            results = engine.search(user_input)
            if engine.last_failed:
                console.print(
                    "[yellow]Engines failed, timed out, or returned no usable response / "
                    "引擎失败、超时或未返回可用响应: "
                    f"{', '.join(engine.display_engine(name) for name in engine.last_failed)}[/yellow]"
                )
                if "searxng" in engine.last_failed:
                    console.print(
                        "[dim]SearXNG is optional; use :pool reset to skip it. / "
                        "SearXNG 是可选项；输入 :pool reset 即可不使用它。[/dim]"
                    )
            if not results:
                console.print("No results found. / 没有找到结果。")
            else:
                show_results(engine, results)
            continue

        parts = user_input[1:].split()
        command = parts[0].lower()
        args = parts[1:]

        if command in ("exit", "q"):
            console.print("Bye! / 再见！")
            break
        if command == "help":
            console.print(Panel(HELP_TEXT, title="Help / 帮助"))
        elif command == "lang":
            if not args:
                print_language(engine)
            elif engine.set_lang(args[0]):
                console.print(
                    f"Search language saved / 搜索语言已保存: {language_name(engine.lang)}\n"
                    "Run a search to use the new setting. / 重新搜索后生效。"
                )
            else:
                console.print(
                    "Invalid language code. Examples: auto, zh, en, ja, fr, zh-CN.\n"
                    "无效语言代码。示例：auto、zh、en、ja、fr、zh-CN。"
                )
        elif command == "pool":
            builtin = ", ".join(
                name for name in engine.providers if not name.startswith(CUSTOM_PREFIX)
            )
            if not args:
                custom = ", ".join(
                    engine.display_engine(name) for name in engine.custom_engines
                ) or "none / 无"
                console.print(
                    f"Built-in engines / 内置引擎: {builtin}\n"
                    f"Custom engines / 自定义引擎: {custom}\n"
                    f"Current pool / 当前搜索池: {engine.pool_display()}\n"
                    "Add a domain directly, e.g. :pool yahoo.hk / "
                    "可直接添加域名，例如 :pool yahoo.hk"
                )
            else:
                if len(args) == 1 and args[0].lower() == "reset":
                    names = list(DEFAULT_POOL)
                else:
                    names = " ".join(args).split(",")
                valid = engine.set_pool(names)
                if engine.invalid_engines:
                    console.print(
                        escape(
                            "Invalid entries / 无效条目: "
                            + ", ".join(engine.invalid_engines)
                        )
                    )
                if valid:
                    console.print(
                        f"Search pool saved / 搜索池已保存: {engine.pool_display()}\n"
                        "Run a search to use the new pool. / 重新搜索后生效。"
                    )
                else:
                    console.print(
                        f"No valid engine. / 没有有效引擎。\n"
                        f"Built-in engines / 内置引擎: {builtin}"
                    )
        elif command == "filter":
            if not args:
                state = "on / 开" if engine.filter_ads else "off / 关"
                console.print(f"Ad and junk filtering / 广告及垃圾内容过滤: {state}")
            elif args[0].lower() in ("on", "off"):
                engine.set_filter(args[0].lower() == "on")
                state = "on / 开" if engine.filter_ads else "off / 关"
                console.print(f"Filtering saved / 过滤设置已保存: {state}")
                if engine.current_query and engine.all_results:
                    show_results(engine, engine.page(engine.current_page))
            else:
                console.print("Use :filter on or :filter off. / 请使用 :filter on 或 :filter off。")
        elif command == "new":
            engine.current_query = None
            engine.invalidate_search()
            console.print("New topic ready. / 新话题已就绪。")
        elif command in ("next", "n"):
            if not engine.current_query:
                console.print("Run a search first. / 请先搜索。")
            elif engine.next_page():
                show_results(engine, engine.page(engine.current_page))
            else:
                console.print("No next page. / 没有下一页。")
        elif command in ("prev", "p"):
            if not engine.current_query:
                console.print("Run a search first. / 请先搜索。")
            elif engine.prev_page():
                show_results(engine, engine.page(engine.current_page))
            else:
                console.print("No previous page. / 没有上一页。")
        elif command == "open":
            if not args or not engine.current_query:
                console.print("Use :open <number> after a search. / 搜索后使用 :open <编号>。")
                continue
            try:
                result = engine.result_at(int(args[0]))
            except (ValueError, IndexError):
                console.print("Invalid result number. / 无效的结果编号。")
                continue
            console.print(escape(f"Opening / 正在打开: {result.url}"))
            try:
                opened = webbrowser.open(result.url)
                if not opened:
                    console.print("Copy the URL above into your browser. / 请将上方网址复制到浏览器。")
            except webbrowser.Error:
                console.print("Could not open a browser. / 无法打开浏览器。")
        elif command in ("summary", "sum"):
            if not args or not engine.current_query:
                console.print(
                    "Use :summary <number> after a search. / 搜索后使用 :summary <编号>。"
                )
                continue
            try:
                number = int(args[0])
            except ValueError:
                console.print("Invalid result number. / 无效的结果编号。")
                continue
            show_article_summary(engine, number)
        else:
            console.print("Unknown command. Type :help. / 未知命令，请输入 :help。")


if __name__ == "__main__":
    main()

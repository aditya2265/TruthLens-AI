"""GDELT 2.0 DOC API Integration for TruthLens AI Live News Feed.

Provides live news article discovery via keyless public GDELT DOC API.
Includes strict response validation, deduplication, formatting, 15-minute caching,
thread-safe 6-second rate limiting, and secondary fallback provider support.
"""
import datetime
import html
import re
import threading
import time
import urllib.parse
from typing import Any, TypedDict
import requests


class NewsArticle(TypedDict):
    id: str
    title: str
    url: str
    source_domain: str
    seendate_formatted: str
    language: str
    source_country: str


class NewsFeedResponse(TypedDict):
    status: str  # "success" or "error"
    message: str
    articles: list[NewsArticle]
    is_cached: bool
    last_updated: str
    notice: str


GDELT_API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
GDELT_TIMEOUT = (15.0, 25.0)  # (connect_timeout, read_timeout) - TLS handshake takes ~9.8s
MAX_RESPONSE_BYTES = 1024 * 1024  # 1 MB response cap
CACHE_TTL_SECONDS = 900  # 15 minutes
MIN_REQUEST_INTERVAL_SECONDS = 6.0  # Minimum 6 seconds between outbound GDELT requests

# Thread lock to serialize outbound GDELT requests and enforce minimum interval
_NEWS_FEED_LOCK = threading.Lock()

# In-memory cache and last request tracking
_NEWS_FEED_CACHE: dict[str, Any] = {
    "timestamp": 0.0,
    "response": None,
    "last_request_time": 0.0,
}


def canonicalize_url(raw_url: str) -> str:
    """Canonicalizes article URL by stripping tracking params and normalizing."""
    if not raw_url or not isinstance(raw_url, str):
        return ""
    try:
        parsed = urllib.parse.urlparse(raw_url.strip())
        if not parsed.scheme or not parsed.netloc:
            return raw_url.strip()

        # Parse query params and remove tracking tokens
        query_params = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        tracking_keys = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            "fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid"
        }
        filtered_params = [
            (k, v) for k, v in query_params if k.lower() not in tracking_keys
        ]
        new_query = urllib.parse.urlencode(filtered_params)

        clean_path = parsed.path.rstrip("/") if parsed.path != "/" else "/"
        return urllib.parse.urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            clean_path,
            "",
            new_query,
            "",  # strip fragment
        ))
    except Exception:
        return raw_url.strip()


def parse_gdelt_seendate(seendate_str: str) -> str:
    """Converts GDELT date format 'YYYYMMDDHHMMSS' or ISO string to readable format."""
    if not seendate_str or not isinstance(seendate_str, str):
        return "Recent"

    clean_str = re.sub(r"\D", "", seendate_str)
    if len(clean_str) >= 8:
        try:
            year = int(clean_str[0:4])
            month = int(clean_str[4:6])
            day = int(clean_str[6:8])
            dt = datetime.date(year, month, day)
            return dt.strftime("%b %d, %Y")
        except ValueError:
            pass

    return "Recent"


def clean_article_title(raw_title: str) -> str:
    """Unescapes HTML entities and cleans up article headline formatting."""
    if not raw_title:
        return "Untitled Article"

    unescaped = html.unescape(raw_title.strip())
    # Remove excessive whitespace
    cleaned = re.sub(r"\s+", " ", unescaped)
    return cleaned


def fetch_fallback_news(max_records: int = 9) -> NewsFeedResponse | None:
    """Attempts to fetch news from secondary providers (GNews or NewsData) if keys are configured."""
    from src.config import GNEWS_API_KEY, NEWSDATA_API_KEY

    # 1. Try GNews API if key provided
    if GNEWS_API_KEY:
        try:
            resp = requests.get(
                "https://gnews.io/api/v4/top-headlines",
                params={"token": GNEWS_API_KEY, "lang": "en", "max": str(min(max_records, 10))},
                timeout=(5.0, 8.0),
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_articles = data.get("articles", [])
                if isinstance(raw_articles, list) and raw_articles:
                    parsed: list[NewsArticle] = []
                    for idx, a in enumerate(raw_articles[:max_records]):
                        title = clean_article_title(a.get("title", ""))
                        url = canonicalize_url(a.get("url", ""))
                        if not url:
                            continue
                        source_name = a.get("source", {}).get("name", "GNews")
                        pub_date = str(a.get("publishedAt", ""))[:10]
                        parsed.append({
                            "id": f"gnews-{idx}-{abs(hash(url)) & 0xffff}",
                            "title": title,
                            "url": a.get("url", ""),
                            "source_domain": source_name,
                            "seendate_formatted": pub_date or "Recent",
                            "language": "English",
                            "source_country": "Global",
                        })
                    if parsed:
                        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC")
                        return {
                            "status": "success",
                            "message": f"Retrieved {len(parsed)} headlines from GNews fallback.",
                            "articles": parsed,
                            "is_cached": False,
                            "last_updated": f"{now_utc} (GNews fallback)",
                            "notice": "Headlines provided via GNews fallback provider.",
                        }
        except Exception:
            pass

    # 2. Try NewsData API if key provided
    if NEWSDATA_API_KEY:
        try:
            resp = requests.get(
                "https://newsdata.io/api/1/news",
                params={"apikey": NEWSDATA_API_KEY, "language": "en"},
                timeout=(5.0, 8.0),
            )
            if resp.status_code == 200:
                data = resp.json()
                raw_results = data.get("results", [])
                if isinstance(raw_results, list) and raw_results:
                    parsed: list[NewsArticle] = []
                    for idx, a in enumerate(raw_results[:max_records]):
                        title = clean_article_title(a.get("title", ""))
                        url = canonicalize_url(a.get("link", ""))
                        if not url:
                            continue
                        source_name = a.get("source_id", "NewsData")
                        pub_date = str(a.get("pubDate", ""))[:10]
                        parsed.append({
                            "id": f"newsdata-{idx}-{abs(hash(url)) & 0xffff}",
                            "title": title,
                            "url": a.get("link", ""),
                            "source_domain": source_name,
                            "seendate_formatted": pub_date or "Recent",
                            "language": "English",
                            "source_country": "Global",
                        })
                    if parsed:
                        now_utc = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC")
                        return {
                            "status": "success",
                            "message": f"Retrieved {len(parsed)} headlines from NewsData fallback.",
                            "articles": parsed,
                            "is_cached": False,
                            "last_updated": f"{now_utc} (NewsData fallback)",
                            "notice": "Headlines provided via NewsData fallback provider.",
                        }
        except Exception:
            pass

    return None


def fetch_gdelt_news(
    query: str = "(news OR report OR official OR market OR science OR tech) sourcelang:english",
    max_records: int = 9,
    force_refresh: bool = False,
) -> NewsFeedResponse:
    """Fetches recent news articles from GDELT 2.0 DOC API with caching, rate limiting, and error handling."""
    global _NEWS_FEED_CACHE, _NEWS_FEED_LOCK

    now = time.time()
    cached_data = _NEWS_FEED_CACHE.get("response")
    cache_time = _NEWS_FEED_CACHE.get("timestamp", 0.0)

    # 1. Normal page load: return valid cached feed if within 15-minute TTL
    if not force_refresh and cached_data and (now - cache_time < CACHE_TTL_SECONDS):
        cached_copy = dict(cached_data)
        cached_copy["is_cached"] = True
        return cached_copy  # type: ignore

    # 2. Acquire lock to serialize external calls and enforce minimum 6.0s interval
    with _NEWS_FEED_LOCK:
        now = time.time()
        cached_data = _NEWS_FEED_CACHE.get("response")
        cache_time = _NEWS_FEED_CACHE.get("timestamp", 0.0)
        last_request_time = _NEWS_FEED_CACHE.get("last_request_time", 0.0)

        # Re-check cache under lock in case another thread just populated it
        if not force_refresh and cached_data and (now - cache_time < CACHE_TTL_SECONDS):
            cached_copy = dict(cached_data)
            cached_copy["is_cached"] = True
            return cached_copy  # type: ignore

        elapsed_since_last_req = now - last_request_time

        # 3. Rate-limit protection: if refresh requested within 6 seconds
        if force_refresh and elapsed_since_last_req < MIN_REQUEST_INTERVAL_SECONDS:
            if cached_data:
                cached_copy = dict(cached_data)
                cached_copy["is_cached"] = True
                cached_copy["status"] = "success"
                orig_time = cached_data.get("last_updated", "")
                cached_copy["last_updated"] = orig_time if "(cached)" in orig_time else f"{orig_time} (cached)"
                cached_copy["notice"] = f"Showing cached feed from {orig_time}. GDELT requires a 6-second interval."
                return cached_copy  # type: ignore

            # No cache exists: try fallback providers
            fallback_res = fetch_fallback_news(max_records=max_records)
            if fallback_res:
                _NEWS_FEED_CACHE["timestamp"] = now
                _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                return fallback_res

            return {
                "status": "error",
                "message": "GDELT API requests must be spaced at least 6 seconds apart. Please wait a moment.",
                "articles": [],
                "is_cached": False,
                "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                "notice": "Rate limit: please wait 6 seconds before retrying.",
            }

        params = {
            "query": query,
            "mode": "ArtList",
            "maxrecords": str(min(max_records, 15)),
            "format": "json",
            "sort": "DateDesc",
        }

        _NEWS_FEED_CACHE["last_request_time"] = time.time()

        try:
            resp = requests.get(
                GDELT_API_URL,
                params=params,
                headers={"User-Agent": "TruthLensAI/1.0 (Educational News Feed)"},
                timeout=GDELT_TIMEOUT,
                stream=True,
            )

            if resp.status_code == 429:
                # GDELT Rate limit reached
                if cached_data:
                    cached_copy = dict(cached_data)
                    cached_copy["is_cached"] = True
                    cached_copy["status"] = "success"
                    orig_time = cached_data.get("last_updated", "")
                    cached_copy["last_updated"] = orig_time if "(cached)" in orig_time else f"{orig_time} (cached)"
                    cached_copy["notice"] = f"GDELT rate limit reached (max 1 request per 5 seconds). Showing cached feed (retrieved at {orig_time})."
                    return cached_copy  # type: ignore

                fallback_res = fetch_fallback_news(max_records=max_records)
                if fallback_res:
                    _NEWS_FEED_CACHE["timestamp"] = now
                    _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                    return fallback_res

                return {
                    "status": "error",
                    "message": "GDELT API rate limit reached (max 1 request every 5 seconds). Please wait a moment before refreshing.",
                    "articles": [],
                    "is_cached": False,
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                    "notice": "Feed rate limit reached. Please wait before retrying.",
                }

            if resp.status_code != 200:
                if cached_data:
                    cached_copy = dict(cached_data)
                    cached_copy["is_cached"] = True
                    cached_copy["status"] = "success"
                    cached_copy["notice"] = f"GDELT returned HTTP {resp.status_code}. Showing cached feed."
                    return cached_copy  # type: ignore

                fallback_res = fetch_fallback_news(max_records=max_records)
                if fallback_res:
                    _NEWS_FEED_CACHE["timestamp"] = now
                    _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                    return fallback_res

                return {
                    "status": "error",
                    "message": f"GDELT API returned HTTP status code {resp.status_code}.",
                    "articles": [],
                    "is_cached": False,
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                    "notice": "Live news feed temporarily unavailable.",
                }

            # Size check
            content_bytes = bytearray()
            for chunk in resp.iter_content(chunk_size=8192):
                content_bytes.extend(chunk)
                if len(content_bytes) > MAX_RESPONSE_BYTES:
                    if cached_data:
                        cached_copy = dict(cached_data)
                        cached_copy["is_cached"] = True
                        cached_copy["status"] = "success"
                        return cached_copy  # type: ignore
                    return {
                        "status": "error",
                        "message": "GDELT API response size exceeded limit.",
                        "articles": [],
                        "is_cached": False,
                        "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                        "notice": "Response payload too large.",
                    }

            try:
                data = resp.json()
            except Exception:
                # In case GDELT returned plain text rate limit with 200 (edge case) or HTML
                raw_text = content_bytes.decode("utf-8", errors="replace")
                if "limit requests to one every" in raw_text.lower():
                    if cached_data:
                        cached_copy = dict(cached_data)
                        cached_copy["is_cached"] = True
                        cached_copy["status"] = "success"
                        orig_time = cached_data.get("last_updated", "")
                        cached_copy["last_updated"] = orig_time if "(cached)" in orig_time else f"{orig_time} (cached)"
                        cached_copy["notice"] = f"GDELT rate limit reached. Showing cached feed (retrieved at {orig_time})."
                        return cached_copy  # type: ignore

                    fallback_res = fetch_fallback_news(max_records=max_records)
                    if fallback_res:
                        _NEWS_FEED_CACHE["timestamp"] = now
                        _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                        return fallback_res

                    return {
                        "status": "error",
                        "message": "GDELT API rate limit reached. Please wait 6 seconds before retrying.",
                        "articles": [],
                        "is_cached": False,
                        "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                        "notice": "Feed rate limit reached.",
                    }

                if cached_data:
                    cached_copy = dict(cached_data)
                    cached_copy["is_cached"] = True
                    cached_copy["status"] = "success"
                    return cached_copy  # type: ignore

                fallback_res = fetch_fallback_news(max_records=max_records)
                if fallback_res:
                    _NEWS_FEED_CACHE["timestamp"] = now
                    _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                    return fallback_res

                return {
                    "status": "error",
                    "message": "Failed to parse JSON response from GDELT API.",
                    "articles": [],
                    "is_cached": False,
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                    "notice": "Invalid response format.",
                }

            raw_articles = data.get("articles", [])
            if not isinstance(raw_articles, list) or len(raw_articles) == 0:
                if cached_data:
                    cached_copy = dict(cached_data)
                    cached_copy["is_cached"] = True
                    cached_copy["status"] = "success"
                    return cached_copy  # type: ignore

                fallback_res = fetch_fallback_news(max_records=max_records)
                if fallback_res:
                    _NEWS_FEED_CACHE["timestamp"] = now
                    _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                    return fallback_res

                return {
                    "status": "success",
                    "message": "No news articles found for query.",
                    "articles": [],
                    "is_cached": False,
                    "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                    "notice": "No articles currently returned by feed.",
                }

            parsed_articles: list[NewsArticle] = []
            seen_urls = set()
            seen_titles = set()

            for idx, item in enumerate(raw_articles):
                if not isinstance(item, dict):
                    continue

                article_url = item.get("url", "").strip()
                if not article_url or not (article_url.startswith("http://") or article_url.startswith("https://")):
                    continue

                canon_url = canonicalize_url(article_url)
                if not canon_url:
                    canon_url = article_url

                # Deduplicate by canonical URL
                if canon_url in seen_urls:
                    continue

                raw_title = item.get("title", "")
                title = clean_article_title(raw_title)

                # Deduplicate by normalized title
                norm_title = title.lower()
                if norm_title in seen_titles:
                    continue

                seen_urls.add(canon_url)
                seen_titles.add(norm_title)

                domain = item.get("domain", "")
                if not domain:
                    try:
                        domain = urllib.parse.urlparse(article_url).hostname or "external news"
                    except Exception:
                        domain = "external news"

                seendate = parse_gdelt_seendate(str(item.get("seendate", "")))

                parsed_articles.append(
                    {
                        "id": f"gdelt-{idx}-{abs(hash(canon_url)) & 0xffff}",
                        "title": title,
                        "url": article_url,
                        "source_domain": domain,
                        "seendate_formatted": seendate,
                        "language": item.get("language", "English"),
                        "source_country": item.get("sourcecountry", "Global"),
                    }
                )

                if len(parsed_articles) >= max_records:
                    break

            updated_time = datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC")

            result: NewsFeedResponse = {
                "status": "success",
                "message": f"Successfully retrieved {len(parsed_articles)} recent news articles.",
                "articles": parsed_articles,
                "is_cached": False,
                "last_updated": updated_time,
                "notice": "Discovery feed from GDELT Project — does not establish fact verification or credibility.",
            }

            # Cache valid response
            _NEWS_FEED_CACHE["timestamp"] = now
            _NEWS_FEED_CACHE["response"] = result

            return result

        except requests.exceptions.Timeout:
            if cached_data:
                cached_copy = dict(cached_data)
                cached_copy["is_cached"] = True
                cached_copy["status"] = "success"
                cached_copy["notice"] = "Live GDELT connection timed out. Showing cached feed."
                return cached_copy  # type: ignore

            fallback_res = fetch_fallback_news(max_records=max_records)
            if fallback_res:
                _NEWS_FEED_CACHE["timestamp"] = now
                _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                return fallback_res

            return {
                "status": "error",
                "message": "Connection to GDELT API timed out.",
                "articles": [],
                "is_cached": False,
                "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                "notice": "Live feed timed out.",
            }
        except requests.exceptions.RequestException as e:
            if cached_data:
                cached_copy = dict(cached_data)
                cached_copy["is_cached"] = True
                cached_copy["status"] = "success"
                return cached_copy  # type: ignore

            fallback_res = fetch_fallback_news(max_records=max_records)
            if fallback_res:
                _NEWS_FEED_CACHE["timestamp"] = now
                _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                return fallback_res

            return {
                "status": "error",
                "message": f"Network request to GDELT API failed: {str(e)}",
                "articles": [],
                "is_cached": False,
                "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                "notice": "Network connection error.",
            }
        except Exception as e:
            if cached_data:
                cached_copy = dict(cached_data)
                cached_copy["is_cached"] = True
                cached_copy["status"] = "success"
                return cached_copy  # type: ignore

            fallback_res = fetch_fallback_news(max_records=max_records)
            if fallback_res:
                _NEWS_FEED_CACHE["timestamp"] = now
                _NEWS_FEED_CACHE["response"] = dict(fallback_res)
                return fallback_res

            return {
                "status": "error",
                "message": f"Unexpected error in live news feed: {str(e)}",
                "articles": [],
                "is_cached": False,
                "last_updated": datetime.datetime.now(datetime.timezone.utc).strftime("%H:%M UTC"),
                "notice": "Error loading live feed.",
            }


def clear_news_feed_cache() -> None:
    """Resets the in-memory cache (useful for testing)."""
    global _NEWS_FEED_CACHE
    _NEWS_FEED_CACHE = {
        "timestamp": 0.0,
        "response": None,
        "last_request_time": 0.0,
    }

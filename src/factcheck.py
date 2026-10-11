"""Google Fact Check Tools API Integration for TruthLens AI (Stage 4).

Connects to the official Google Fact Check Tools REST API (`claims:search`)
to search independent fact-checking databases for matching external evidence.
Never fabricates results, preserves publisher verdicts verbatim, and gracefully
handles missing API keys, rate limits, and network errors.
"""
import datetime
import html
import re
import urllib.parse
from typing import Any, TypedDict
import requests

from src.config import GOOGLE_FACTCHECK_API_KEY

FACTCHECK_API_URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
FACTCHECK_TIMEOUT = (4.0, 8.0)  # (connect_timeout, read_timeout)
MAX_RESPONSE_BYTES = 1024 * 1024  # 1 MB response cap
MAX_QUERY_CHARS = 120  # Bounded search query length


class FactCheckReview(TypedDict):
    claim_text: str
    claimant: str
    claim_date: str
    publisher_name: str
    publisher_site: str
    review_title: str
    review_url: str
    review_date: str
    textual_rating: str
    rating_badge_class: str


class FactCheckResult(TypedDict):
    status: str  # "success" | "no_matches" | "missing_key" | "error"
    message: str
    query_used: str
    reviews: list[FactCheckReview]
    notice: str


def extract_factcheck_query(text: str, title: str = "") -> str:
    """Extracts a concise, effective search query for claims:search.

    Prioritizes article title when available. For raw text, extracts the first
    sentence or leading clause, bounded to MAX_QUERY_CHARS characters.
    """
    candidate = ""
    if title and len(title.strip()) >= 5:
        candidate = title.strip()
    elif text and isinstance(text, str):
        cleaned = text.strip()
        # Take the first paragraph or line
        first_line = cleaned.split("\n")[0].strip()
        # Look for first sentence boundary (.!?) with at least 10 chars
        match = re.search(r"[.!?]", first_line)
        if match and match.start() >= 10:
            candidate = first_line[: match.start()]
        else:
            candidate = first_line

    # Clean punctuation, excess whitespace, and quotes
    candidate = html.unescape(candidate)
    candidate = re.sub(r'[\t\r\n]+', ' ', candidate)
    candidate = re.sub(r'["“”‘’\']', ' ', candidate)
    candidate = re.sub(r'\s+', ' ', candidate).strip()

    # Bound length at word boundary
    if len(candidate) > MAX_QUERY_CHARS:
        truncated = candidate[:MAX_QUERY_CHARS]
        last_space = truncated.rsplit(" ", 1)
        if len(last_space) > 1 and len(last_space[0]) > 20:
            candidate = last_space[0]
        else:
            candidate = truncated

    return candidate


def parse_factcheck_date(date_str: str) -> str:
    """Converts ISO date string ('YYYY-MM-DDTHH:MM:SSZ' or 'YYYY-MM-DD') to readable format."""
    if not date_str or not isinstance(date_str, str):
        return "Date unavailable"

    # Match YYYY-MM-DD
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_str.strip())
    if match:
        try:
            year, month, day = int(match.group(1)), int(match.group(2)), int(match.group(3))
            dt = datetime.date(year, month, day)
            return dt.strftime("%b %d, %Y")
        except ValueError:
            pass

    return "Date unavailable"


def classify_rating_badge(textual_rating: str) -> str:
    """Returns CSS badge class ('false', 'true', 'mixed') based on rating sentiment.

    Used purely for UI styling; the original publisher rating string is always preserved.
    """
    if not textual_rating:
        return "badge-neutral"

    r = textual_rating.lower().strip()
    false_keywords = ["false", "fake", "incorrect", "pants on fire", "hoax", "debunked", "misleading", "distorts"]
    true_keywords = ["true", "correct", "accurate", "verified"]

    if any(k in r for k in false_keywords):
        return "badge-false"
    if any(k in r for k in true_keywords) and not any(k in r for k in ["mostly false", "partly false", "not true"]):
        return "badge-true"
    return "badge-mixed"


def search_fact_checks(
    query: str,
    api_key: str | None = None,
    language_code: str = "en",
    page_size: int = 5,
) -> FactCheckResult:
    """Searches Google Fact Check Tools API for matching claim reviews.

    Args:
        query: The search query string.
        api_key: Optional API key override. If None, uses GOOGLE_FACTCHECK_API_KEY from config.
        language_code: BCP-47 language tag (default 'en').
        page_size: Maximum number of claims to retrieve (default 5).

    Returns:
        Structured FactCheckResult with status, parsed reviews, and transparent notices.
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "status": "no_matches",
            "message": "Empty search query provided.",
            "query_used": "",
            "reviews": [],
            "notice": "No search terms were available to query fact-checking databases.",
        }

    key = api_key if api_key is not None else GOOGLE_FACTCHECK_API_KEY
    if not key:
        return {
            "status": "missing_key",
            "message": (
                "Google Fact Check Tools API key is not configured. "
                "Set GOOGLE_FACTCHECK_API_KEY in your .env file to enable live fact-check searches."
            ),
            "query_used": clean_query,
            "reviews": [],
            "notice": "Fact-check lookup unconfigured (API key required).",
        }

    params = {
        "query": clean_query,
        "languageCode": language_code,
        "pageSize": str(min(page_size, 10)),
        "key": key,
    }

    try:
        resp = requests.get(
            FACTCHECK_API_URL,
            params=params,
            headers={"User-Agent": "TruthLensAI/1.0 (FactCheck Integration)"},
            timeout=FACTCHECK_TIMEOUT,
            stream=True,
        )

        # Handle HTTP status codes
        if resp.status_code == 403 or resp.status_code == 400:
            return {
                "status": "error",
                "message": (
                    f"Google Fact Check Tools API authentication failed (HTTP {resp.status_code}). "
                    "Verify that GOOGLE_FACTCHECK_API_KEY is valid and the Fact Check Tools API is enabled."
                ),
                "query_used": clean_query,
                "reviews": [],
                "notice": "API authentication error.",
            }

        if resp.status_code == 429:
            return {
                "status": "error",
                "message": "Google Fact Check Tools API rate or quota limit reached. Please try again later.",
                "query_used": clean_query,
                "reviews": [],
                "notice": "API quota limit reached.",
            }

        if resp.status_code != 200:
            return {
                "status": "error",
                "message": f"Google Fact Check Tools API returned HTTP {resp.status_code}.",
                "query_used": clean_query,
                "reviews": [],
                "notice": "Fact-check service temporarily unavailable.",
            }

        # Size bounded check
        content_bytes = bytearray()
        for chunk in resp.iter_content(chunk_size=8192):
            content_bytes.extend(chunk)
            if len(content_bytes) > MAX_RESPONSE_BYTES:
                return {
                    "status": "error",
                    "message": "Fact-check API response exceeded maximum allowable size.",
                    "query_used": clean_query,
                    "reviews": [],
                    "notice": "Response payload too large.",
                }

        try:
            data = resp.json()
        except Exception:
            return {
                "status": "error",
                "message": "Failed to parse JSON response from Google Fact Check Tools API.",
                "query_used": clean_query,
                "reviews": [],
                "notice": "Invalid response format.",
            }

        raw_claims = data.get("claims", [])
        if not isinstance(raw_claims, list) or len(raw_claims) == 0:
            return {
                "status": "no_matches",
                "message": f"No indexed fact-checks found matching claim: '{clean_query}'.",
                "query_used": clean_query,
                "reviews": [],
                "notice": "No matching claims found in independent fact-checking databases.",
            }

        parsed_reviews: list[FactCheckReview] = []
        seen_urls = set()

        for claim in raw_claims:
            if not isinstance(claim, dict):
                continue

            claim_text = html.unescape(str(claim.get("text", "")).strip())
            claimant = html.unescape(str(claim.get("claimant", "")).strip()) or "Unspecified source"
            claim_date = parse_factcheck_date(str(claim.get("claimDate", "")))

            claim_reviews = claim.get("claimReview", [])
            if not isinstance(claim_reviews, list):
                continue

            for cr in claim_reviews:
                if not isinstance(cr, dict):
                    continue

                review_url = str(cr.get("url", "")).strip()
                if not review_url or not (review_url.startswith("http://") or review_url.startswith("https://")):
                    continue

                # Deduplicate by normalized review URL
                norm_url = review_url.split("#")[0].rstrip("/").lower()
                if norm_url in seen_urls:
                    continue
                seen_urls.add(norm_url)

                # Publisher metadata
                pub = cr.get("publisher", {})
                if isinstance(pub, dict):
                    pub_name = html.unescape(str(pub.get("name", "")).strip()) or "Independent Reviewer"
                    pub_site = html.unescape(str(pub.get("site", "")).strip())
                    if not pub_site:
                        try:
                            pub_site = urllib.parse.urlparse(review_url).netloc or "external"
                        except Exception:
                            pub_site = "external"
                else:
                    pub_name = "Independent Reviewer"
                    pub_site = "external"

                review_title = html.unescape(str(cr.get("title", "")).strip()) or "Fact-Check Review"
                review_date = parse_factcheck_date(str(cr.get("reviewDate", "")))
                textual_rating = html.unescape(str(cr.get("textualRating", "")).strip()) or "Not rated"
                badge_class = classify_rating_badge(textual_rating)

                parsed_reviews.append(
                    {
                        "claim_text": claim_text or "Unspecified claim statement",
                        "claimant": claimant,
                        "claim_date": claim_date,
                        "publisher_name": pub_name,
                        "publisher_site": pub_site,
                        "review_title": review_title,
                        "review_url": review_url,
                        "review_date": review_date,
                        "textual_rating": textual_rating,
                        "rating_badge_class": badge_class,
                    }
                )

                if len(parsed_reviews) >= page_size:
                    break
            if len(parsed_reviews) >= page_size:
                break

        if not parsed_reviews:
            return {
                "status": "no_matches",
                "message": f"No valid fact-check reviews found for query '{clean_query}'.",
                "query_used": clean_query,
                "reviews": [],
                "notice": "No matching reviews found in independent databases.",
            }

        return {
            "status": "success",
            "message": f"Found {len(parsed_reviews)} related fact-check article(s).",
            "query_used": clean_query,
            "reviews": parsed_reviews,
            "notice": (
                "External fact-checks from independent publishers via Google Fact Check Tools API. "
                "Matching external reviews provide evidence regarding related claims, but do not prove "
                "that the entire submitted text is true or false."
            ),
        }

    except requests.exceptions.Timeout:
        return {
            "status": "error",
            "message": "Connection to Google Fact Check Tools API timed out.",
            "query_used": clean_query,
            "reviews": [],
            "notice": "Fact-check lookup timed out.",
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "error",
            "message": f"Network request to Google Fact Check Tools API failed: {str(e)}",
            "query_used": clean_query,
            "reviews": [],
            "notice": "Network connection error.",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Unexpected error during fact-check lookup: {str(e)}",
            "query_used": clean_query,
            "reviews": [],
            "notice": "Fact-check lookup error.",
        }

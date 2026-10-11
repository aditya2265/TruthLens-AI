"""Unit and integration tests for GDELT 2.0 DOC API news feed service."""
import json
import time
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.news_feed import (
    clear_news_feed_cache,
    clean_article_title,
    fetch_gdelt_news,
    parse_gdelt_seendate,
)


@pytest.fixture(autouse=True)
def reset_cache():
    """Resets news feed cache before each test."""
    clear_news_feed_cache()
    yield
    clear_news_feed_cache()


# --- 1. Date, Title & Canonicalization Helper Tests ---
def test_parse_gdelt_seendate_valid():
    assert parse_gdelt_seendate("20261010T153000Z") == "Oct 10, 2026"
    assert parse_gdelt_seendate("20261010153000") == "Oct 10, 2026"
    assert parse_gdelt_seendate("20250101") == "Jan 01, 2025"


def test_parse_gdelt_seendate_invalid():
    assert parse_gdelt_seendate("") == "Recent"
    assert parse_gdelt_seendate("not-a-date") == "Recent"
    assert parse_gdelt_seendate(None) == "Recent"  # type: ignore


def test_clean_article_title():
    assert clean_article_title("Breaking &quot;News&quot; &amp; Updates") == 'Breaking "News" & Updates'
    assert clean_article_title("   Multiple   Spaces   In   Title  ") == "Multiple Spaces In Title"
    assert clean_article_title("") == "Untitled Article"


def test_canonicalize_url():
    from src.news_feed import canonicalize_url

    assert canonicalize_url("https://example.com/story/?utm_source=twitter&utm_medium=social") == "https://example.com/story"
    assert canonicalize_url("https://EXAMPLE.com/story?fbclid=12345#section") == "https://example.com/story"
    assert canonicalize_url("https://example.com/item?category=news&utm_campaign=daily") == "https://example.com/item?category=news"
    assert canonicalize_url("") == ""
    assert canonicalize_url("invalid-url") == "invalid-url"


# --- 2. GDELT API Request & Parsing Tests ---
def test_fetch_gdelt_news_success():
    mock_payload = {
        "articles": [
            {
                "url": "https://reuters.com/world/article-1",
                "title": "Global Climate Conference Concludes with New Agreement",
                "seendate": "20261010T120000Z",
                "domain": "reuters.com",
                "language": "English",
                "sourcecountry": "United States",
            },
            {
                "url": "https://apnews.com/article/tech-2",
                "title": "New Quantum Computing Breakthrough Announced",
                "seendate": "20261010T100000Z",
                "domain": "apnews.com",
                "language": "English",
                "sourcecountry": "United States",
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "success"
        assert len(res["articles"]) == 2
        assert res["articles"][0]["source_domain"] == "reuters.com"
        assert res["articles"][0]["seendate_formatted"] == "Oct 10, 2026"
        assert "Discovery feed from GDELT" in res["notice"]


def test_fetch_gdelt_news_deduplication():
    mock_payload = {
        "articles": [
            {
                "url": "https://example.com/story1?utm_source=google",
                "title": "Major Policy Reform Approved",
                "seendate": "20261010T120000Z",
                "domain": "example.com",
            },
            {
                "url": "https://example.com/story1?utm_source=twitter",  # Same canonical URL
                "title": "Major Policy Reform Approved",
                "seendate": "20261010T120000Z",
                "domain": "example.com",
            },
            {
                "url": "https://example.com/story2",
                "title": "MAJOR POLICY REFORM APPROVED",  # Duplicate title
                "seendate": "20261010T120000Z",
                "domain": "example.com",
            },
            {
                "url": "https://example.com/story3",
                "title": "Different Unique Headline",
                "seendate": "20261010T120000Z",
                "domain": "example.com",
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "success"
        assert len(res["articles"]) == 2
        assert res["articles"][0]["title"] == "Major Policy Reform Approved"
        assert res["articles"][1]["title"] == "Different Unique Headline"


def test_fetch_gdelt_news_missing_and_malformed_fields():
    mock_payload = {
        "articles": [
            "not-a-dict",  # Ignored
            {"url": "not-http://bad-scheme.com", "title": "Bad Scheme"},  # Ignored
            {"title": "Missing URL"},  # Ignored
            {
                "url": "https://example.com/fallback-domain-story",
                # Missing domain and title
                "seendate": "invalid-date",
            },
            {
                "url": "https://bbc.com/news/valid-story",
                "title": "&lt;Breaking&gt; Global Report",
                "seendate": "20261010120000",
                "domain": "bbc.com",
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "success"
        assert len(res["articles"]) == 2
        # Fallback fields validated
        assert res["articles"][0]["source_domain"] == "example.com"
        assert res["articles"][0]["title"] == "Untitled Article"
        assert res["articles"][0]["seendate_formatted"] == "Recent"
        assert res["articles"][1]["title"] == "<Breaking> Global Report"
        assert res["articles"][1]["seendate_formatted"] == "Oct 10, 2026"


def test_fetch_gdelt_news_empty_response():
    mock_payload = {"articles": []}

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "success"
        assert len(res["articles"]) == 0
        assert "No articles" in res["notice"]


def test_fetch_gdelt_news_http_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 503

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "503" in res["message"]
        assert len(res["articles"]) == 0


def test_fetch_gdelt_news_rate_limit_429():
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "rate limit" in res["message"].lower() or "5 seconds" in res["message"].lower()
        assert len(res["articles"]) == 0


def test_fetch_gdelt_news_rate_limit_plain_text():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"Please limit requests to one every 5 seconds"]
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "rate limit" in res["message"].lower()


def test_fetch_gdelt_news_timeout():
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "timed out" in res["message"].lower()


def test_fetch_gdelt_news_network_failure():
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("DNS lookup failed")):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "network request" in res["message"].lower()


def test_fetch_gdelt_news_invalid_json():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"<html><body>502 Bad Gateway</body></html>"]
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "parse json" in res["message"].lower()


def test_fetch_gdelt_news_oversized_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    large_chunk = b"X" * (1024 * 1024 + 100)
    mock_resp.iter_content.return_value = [large_chunk]

    with patch("requests.get", return_value=mock_resp):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "exceeded limit" in res["message"].lower()


def test_fetch_gdelt_news_caching_behavior():
    mock_payload = {
        "articles": [
            {
                "url": "https://example.com/cached-story",
                "title": "Cached News Title",
                "seendate": "20261010T120000Z",
                "domain": "example.com",
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp) as mock_get:
        # First call fetches from API
        res1 = fetch_gdelt_news(force_refresh=False)
        assert res1["status"] == "success"
        assert res1["is_cached"] is False
        assert mock_get.call_count == 1

        # Second call returns cached data without calling requests.get again
        res2 = fetch_gdelt_news(force_refresh=False)
        assert res2["status"] == "success"
        assert res2["is_cached"] is True
        assert mock_get.call_count == 1  # Not incremented


# --- 3. Flask API Integration Tests ---
def test_flask_api_news_feed_endpoint():
    from src.app import app

    app.config["TESTING"] = True
    mock_feed = {
        "status": "success",
        "message": "Fetched 1 articles.",
        "articles": [
            {
                "id": "gdelt-0-123",
                "title": "Flask Feed Test Title",
                "url": "https://example.com/flask-news",
                "source_domain": "example.com",
                "seendate_formatted": "Oct 10, 2026",
                "language": "English",
                "source_country": "Global",
            }
        ],
        "is_cached": False,
        "last_updated": "12:00 UTC",
        "notice": "Discovery feed from GDELT Project.",
    }

    with patch("src.app.fetch_gdelt_news", return_value=mock_feed):
        with app.test_client() as client:
            response = client.get("/api/news-feed")
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["status"] == "success"
            assert len(data["articles"]) == 1
            assert data["articles"][0]["title"] == "Flask Feed Test Title"


def test_flask_api_news_feed_rate_limit_and_error_codes():
    from src.app import app

    app.config["TESTING"] = True

    rate_limited_feed = {
        "status": "error",
        "message": "GDELT API requests must be spaced at least 5 seconds apart.",
        "articles": [],
        "is_cached": False,
        "last_updated": "12:00 UTC",
        "notice": "Rate limit: please wait 5 seconds before retrying.",
    }

    server_error_feed = {
        "status": "error",
        "message": "GDELT API returned HTTP status code 503.",
        "articles": [],
        "is_cached": False,
        "last_updated": "12:00 UTC",
        "notice": "Live news feed temporarily unavailable.",
    }

    with patch("src.app.fetch_gdelt_news", return_value=rate_limited_feed):
        with app.test_client() as client:
            response = client.get("/api/news-feed?refresh=true")
            assert response.status_code == 429
            data = json.loads(response.data)
            assert data["status"] == "error"

    with patch("src.app.fetch_gdelt_news", return_value=server_error_feed):
        with app.test_client() as client:
            response = client.get("/api/news-feed")
            assert response.status_code == 503
            data = json.loads(response.data)
            assert data["status"] == "error"


def test_news_feed_cache_hit_and_expiry():
    mock_payload = {
        "articles": [
            {
                "url": "https://example.com/cached-1",
                "title": "Cached News Title",
                "seendate": "20261010T120000Z",
                "domain": "example.com",
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp) as mock_get:
        # First call populates cache
        res1 = fetch_gdelt_news(force_refresh=False)
        assert res1["status"] == "success"
        assert res1["is_cached"] is False
        assert mock_get.call_count == 1

        # Second call within TTL hits cache without network call
        res2 = fetch_gdelt_news(force_refresh=False)
        assert res2["status"] == "success"
        assert res2["is_cached"] is True
        assert mock_get.call_count == 1

        # Third call after TTL expiry triggers a new fetch
        with patch("time.time", return_value=time.time() + 1000):
            res3 = fetch_gdelt_news(force_refresh=False)
            assert res3["status"] == "success"
            assert mock_get.call_count == 2


def test_news_feed_refresh_within_window_returns_cached_data_with_200():
    from src.app import app

    mock_payload = {
        "articles": [
            {
                "url": "https://example.com/live-news",
                "title": "Fresh Breaking News",
                "seendate": "20261010T120000Z",
                "domain": "example.com",
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp) as mock_get:
        # Initial fetch populates cache
        res1 = fetch_gdelt_news(force_refresh=True)
        assert res1["status"] == "success"
        assert mock_get.call_count == 1

        # Force refresh immediately (< 6s later) must return cached data with success, not error
        res2 = fetch_gdelt_news(force_refresh=True)
        assert res2["status"] == "success"
        assert res2["is_cached"] is True
        assert "cached" in res2["last_updated"]
        assert mock_get.call_count == 1  # Blocked from calling GDELT API

        # Verify via Flask API route that it returns HTTP 200, NOT HTTP 429
        with app.test_client() as client:
            resp = client.get("/api/news-feed?refresh=true")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["status"] == "success"
            assert data["is_cached"] is True
            assert len(data["articles"]) == 1


def test_news_feed_rate_limit_without_cache_shows_error():
    from src.app import app

    # Reset cache and mock GDELT 429 with no fallback keys
    clear_news_feed_cache()
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("requests.get", return_value=mock_resp), \
         patch("src.config.GNEWS_API_KEY", ""), \
         patch("src.config.NEWSDATA_API_KEY", ""):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "error"
        assert "rate limit" in res["message"].lower()

        # Via Flask API route, returns HTTP 429 when no cache is available
        with app.test_client() as client:
            resp = client.get("/api/news-feed?refresh=true")
            assert resp.status_code == 429
            data = json.loads(resp.data)
            assert data["status"] == "error"


def test_news_feed_fallback_provider_gnews_used_when_gdelt_fails():
    clear_news_feed_cache()
    mock_gnews_payload = {
        "articles": [
            {
                "title": "GNews Fallback Headline",
                "url": "https://gnews.example.com/fallback-article",
                "publishedAt": "2026-10-11T12:00:00Z",
                "source": {"name": "GNews Source", "url": "https://gnews.example.com"},
            }
        ]
    }
    mock_gnews_resp = MagicMock()
    mock_gnews_resp.status_code = 200
    mock_gnews_resp.json.return_value = mock_gnews_payload

    # Mock GDELT returning 503 error, but GNEWS_API_KEY is configured
    mock_gdelt_resp = MagicMock()
    mock_gdelt_resp.status_code = 503

    def mock_requests_get(url, *args, **kwargs):
        if "gnews.io" in url:
            return mock_gnews_resp
        return mock_gdelt_resp

    with patch("requests.get", side_effect=mock_requests_get), \
         patch("src.config.GNEWS_API_KEY", "test-gnews-key"):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "success"
        assert len(res["articles"]) == 1
        assert res["articles"][0]["title"] == "GNews Fallback Headline"
        assert "GNews" in res["last_updated"]


def test_news_feed_fallback_provider_newsdata_used_when_gdelt_fails():
    clear_news_feed_cache()
    mock_newsdata_payload = {
        "results": [
            {
                "title": "NewsData Fallback Headline",
                "link": "https://newsdata.example.com/fallback-article",
                "pubDate": "2026-10-11 12:00:00",
                "source_id": "NewsData Wire",
            }
        ]
    }
    mock_newsdata_resp = MagicMock()
    mock_newsdata_resp.status_code = 200
    mock_newsdata_resp.json.return_value = mock_newsdata_payload

    # Mock GDELT returning 429 rate limit, GNews missing, but NEWSDATA_API_KEY is configured
    mock_gdelt_resp = MagicMock()
    mock_gdelt_resp.status_code = 429

    def mock_requests_get(url, *args, **kwargs):
        if "newsdata.io" in url:
            return mock_newsdata_resp
        return mock_gdelt_resp

    with patch("requests.get", side_effect=mock_requests_get), \
         patch("src.config.GNEWS_API_KEY", ""), \
         patch("src.config.NEWSDATA_API_KEY", "test-newsdata-key"):
        res = fetch_gdelt_news(force_refresh=True)
        assert res["status"] == "success"
        assert len(res["articles"]) == 1
        assert res["articles"][0]["title"] == "NewsData Fallback Headline"
        assert "NewsData" in res["last_updated"]


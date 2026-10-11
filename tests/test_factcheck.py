"""Unit and integration tests for Google Fact Check Tools API service (Stage 4)."""
import json
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.factcheck import (
    classify_rating_badge,
    extract_factcheck_query,
    parse_factcheck_date,
    search_fact_checks,
)
from src.app import app

MOCK_FEED = {
    "status": "success",
    "message": "Retrieved 1 articles.",
    "articles": [],
    "is_cached": False,
    "last_updated": "12:00 UTC",
    "notice": "Mock feed",
}


@pytest.fixture(autouse=True)
def mock_news_feed():
    with patch("src.app.fetch_gdelt_news", return_value=MOCK_FEED):
        yield


@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


# --- 1. Query Extraction & Helper Tests ---
def test_extract_factcheck_query_title_priority():
    title = "Congress Approves Historic Bipartisan Clean Energy Package"
    text = "Detailed paragraph explaining the votes and committee negotiations across the week."
    query = extract_factcheck_query(text, title=title)
    assert query == title


def test_extract_factcheck_query_from_text():
    text = "NASA confirmed the discovery of a new exoplanet yesterday. Scientists used the James Webb Telescope."
    query = extract_factcheck_query(text)
    assert query == "NASA confirmed the discovery of a new exoplanet yesterday"


def test_extract_factcheck_query_length_bound():
    long_claim = "A " + "very " * 40 + "long claim statement that exceeds the maximum query limit."
    query = extract_factcheck_query(long_claim)
    assert len(query) <= 120
    assert not query.endswith(" ")


def test_parse_factcheck_date():
    assert parse_factcheck_date("2026-10-10T15:30:00Z") == "Oct 10, 2026"
    assert parse_factcheck_date("2025-01-01") == "Jan 01, 2025"
    assert parse_factcheck_date("invalid-date") == "Date unavailable"
    assert parse_factcheck_date("") == "Date unavailable"
    assert parse_factcheck_date(None) == "Date unavailable"  # type: ignore


def test_classify_rating_badge():
    assert classify_rating_badge("False") == "badge-false"
    assert classify_rating_badge("Pants on Fire!") == "badge-false"
    assert classify_rating_badge("Mostly False") == "badge-false"
    assert classify_rating_badge("True") == "badge-true"
    assert classify_rating_badge("Correct") == "badge-true"
    assert classify_rating_badge("Mixture") == "badge-mixed"
    assert classify_rating_badge("Unproven") == "badge-mixed"
    assert classify_rating_badge("") == "badge-neutral"


# --- 2. API Key Enforcement & Search Tests ---
def test_search_fact_checks_missing_key():
    with patch("src.factcheck.GOOGLE_FACTCHECK_API_KEY", ""):
        res = search_fact_checks("sample claim query", api_key="")
        assert res["status"] == "missing_key"
        assert "GOOGLE_FACTCHECK_API_KEY" in res["message"]
        assert len(res["reviews"]) == 0
        assert "unconfigured" in res["notice"]


def test_search_fact_checks_empty_query():
    res = search_fact_checks("   ", api_key="dummy-key")
    assert res["status"] == "no_matches"
    assert len(res["reviews"]) == 0


def test_search_fact_checks_success():
    mock_payload = {
        "claims": [
            {
                "text": "The moon landings were staged in a Hollywood film studio.",
                "claimant": "Viral social media video",
                "claimDate": "2026-05-01T00:00:00Z",
                "claimReview": [
                    {
                        "publisher": {
                            "name": "PolitiFact",
                            "site": "politifact.com",
                        },
                        "url": "https://www.politifact.com/factchecks/2026/moon-landing/",
                        "title": "No, the Apollo moon landings were not filmed on a studio lot",
                        "reviewDate": "2026-05-02T12:00:00Z",
                        "textualRating": "False",
                        "languageCode": "en",
                    }
                ],
            }
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp) as mock_get:
        res = search_fact_checks("moon landing staged", api_key="test-api-key")
        assert res["status"] == "success"
        assert len(res["reviews"]) == 1
        review = res["reviews"][0]
        assert review["publisher_name"] == "PolitiFact"
        assert review["publisher_site"] == "politifact.com"
        assert review["textual_rating"] == "False"
        assert review["rating_badge_class"] == "badge-false"
        assert review["review_url"] == "https://www.politifact.com/factchecks/2026/moon-landing/"
        assert review["review_date"] == "May 02, 2026"
        assert "moon landings were staged" in review["claim_text"]
        assert mock_get.call_count == 1
        # Confirm query parameters
        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["params"]["key"] == "test-api-key"
        assert call_kwargs["params"]["query"] == "moon landing staged"


def test_search_fact_checks_deduplication():
    mock_payload = {
        "claims": [
            {
                "text": "Claim statement A",
                "claimReview": [
                    {
                        "publisher": {"name": "FactCheck.org"},
                        "url": "https://factcheck.org/story-1/",
                        "textualRating": "Misleading",
                    },
                    {
                        # Duplicate URL
                        "publisher": {"name": "FactCheck.org"},
                        "url": "https://factcheck.org/story-1/#section",
                        "textualRating": "Misleading",
                    },
                ],
            },
            {
                "text": "Claim statement B",
                "claimReview": [
                    {
                        "publisher": {"name": "Reuters Fact Check"},
                        "url": "https://reuters.com/fact-check/story-2",
                        "textualRating": "False",
                    }
                ],
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("query", api_key="dummy-key")
        assert res["status"] == "success"
        assert len(res["reviews"]) == 2
        assert res["reviews"][0]["publisher_name"] == "FactCheck.org"
        assert res["reviews"][1]["publisher_name"] == "Reuters Fact Check"


def test_search_fact_checks_empty_results():
    mock_payload = {"claims": []}

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("unknown rare claim statement", api_key="dummy-key")
        assert res["status"] == "no_matches"
        assert len(res["reviews"]) == 0
        assert "No indexed fact-checks" in res["message"]


def test_search_fact_checks_missing_and_malformed_fields():
    mock_payload = {
        "claims": [
            "not-a-dict",
            {"text": "No reviews claim", "claimReview": "not-a-list"},
            {
                "text": "Malformed claim",
                "claimReview": [
                    {"url": "ftp://not-http.com"},  # Non-http rejected
                    {"url": ""},  # Empty URL rejected
                    {
                        # Missing publisher, date, rating
                        "url": "https://snopes.com/fact-check/sample",
                    },
                ],
            },
        ]
    }

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [json.dumps(mock_payload).encode("utf-8")]
    mock_resp.json.return_value = mock_payload

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("sample", api_key="dummy-key")
        assert res["status"] == "success"
        assert len(res["reviews"]) == 1
        r = res["reviews"][0]
        assert r["publisher_name"] == "Independent Reviewer"
        assert r["publisher_site"] == "snopes.com"
        assert r["textual_rating"] == "Not rated"
        assert r["review_date"] == "Date unavailable"


def test_search_fact_checks_auth_error_403():
    mock_resp = MagicMock()
    mock_resp.status_code = 403

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("claim", api_key="invalid-key")
        assert res["status"] == "error"
        assert "authentication failed" in res["message"].lower()
        # Ensure API key is NEVER leaked in the error message
        assert "invalid-key" not in res["message"]


def test_search_fact_checks_quota_limit_429():
    mock_resp = MagicMock()
    mock_resp.status_code = 429

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("claim", api_key="dummy-key")
        assert res["status"] == "error"
        assert "quota" in res["message"].lower()


def test_search_fact_checks_http_error_500():
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("claim", api_key="dummy-key")
        assert res["status"] == "error"
        assert "500" in res["message"]


def test_search_fact_checks_timeout():
    with patch("requests.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
        res = search_fact_checks("claim", api_key="dummy-key")
        assert res["status"] == "error"
        assert "timed out" in res["message"].lower()


def test_search_fact_checks_network_failure():
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("DNS failure")):
        res = search_fact_checks("claim", api_key="dummy-key")
        assert res["status"] == "error"
        assert "network request" in res["message"].lower()


def test_search_fact_checks_invalid_json():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"Invalid response not json"]
    mock_resp.json.side_effect = json.JSONDecodeError("Expecting value", "", 0)

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("claim", api_key="dummy-key")
        assert res["status"] == "error"
        assert "parse json" in res["message"].lower()


def test_search_fact_checks_oversized_response():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"X" * (1024 * 1024 + 100)]

    with patch("requests.get", return_value=mock_resp):
        res = search_fact_checks("claim", api_key="dummy-key")
        assert res["status"] == "error"
        assert "size" in res["message"].lower()


# --- 3. Flask Route & End-to-End Integration Tests ---
def test_flask_api_fact_check_endpoint():
    from src.app import app

    app.config["TESTING"] = True
    mock_fc = {
        "status": "success",
        "message": "Found 1 review.",
        "query_used": "test query",
        "reviews": [
            {
                "claim_text": "Sample claim",
                "claimant": "Speaker",
                "claim_date": "Oct 10, 2026",
                "publisher_name": "AP Fact Check",
                "publisher_site": "apnews.com",
                "review_title": "AP Assessment",
                "review_url": "https://apnews.com/fact-check/123",
                "review_date": "Oct 10, 2026",
                "textual_rating": "False",
                "rating_badge_class": "badge-false",
            }
        ],
        "notice": "External fact check evidence.",
    }

    with patch("src.app.search_fact_checks", return_value=mock_fc):
        with app.test_client() as client:
            resp = client.get("/api/fact-check?query=test%20query")
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data["status"] == "success"
            assert len(data["reviews"]) == 1
            assert data["reviews"][0]["publisher_name"] == "AP Fact Check"

            # Missing query returns 400
            resp_empty = client.get("/api/fact-check")
            assert resp_empty.status_code == 400


def test_predict_text_attaches_fact_checks():
    from src.predict import predict_text

    mock_fc = {
        "status": "success",
        "message": "Found 1 review.",
        "query_used": "economy report",
        "reviews": [
            {
                "claim_text": "The economy grew by 100% last quarter.",
                "claimant": "Social post",
                "claim_date": "Oct 10, 2026",
                "publisher_name": "Reuters",
                "publisher_site": "reuters.com",
                "review_title": "Review Title",
                "review_url": "https://reuters.com/factcheck",
                "review_date": "Oct 10, 2026",
                "textual_rating": "False",
                "rating_badge_class": "badge-false",
            }
        ],
        "notice": "Fact checks notice",
    }

    with patch("src.predict.search_fact_checks", return_value=mock_fc):
        res = predict_text("The committee discussed the federal budget allocations for infrastructure grants.")
        assert "fact_checks" in res
        assert res["fact_checks"]["status"] == "success"
        assert len(res["fact_checks"]["reviews"]) == 1


def test_predict_url_attaches_fact_checks():
    from src.predict import predict_url

    mock_extraction = {
        "status": "success",
        "url": "https://example.com/article",
        "source_domain": "example.com",
        "extracted_title": "Major Infrastructure Bill Passed in Congress",
        "extracted_text": "Lawmakers approved thirty state grants for bridge and highway improvements.",
        "extracted_excerpt": "Lawmakers approved thirty state grants...",
        "publication_date": "2026-10-10",
        "fetch_notice": "Extracted with Trafilatura",
    }

    mock_fc = {
        "status": "no_matches",
        "message": "No indexed fact-checks found.",
        "query_used": "Major Infrastructure Bill Passed in Congress",
        "reviews": [],
        "notice": "No reviews found",
    }

    with patch("src.url_fetcher.fetch_and_extract_url", return_value=mock_extraction):
        with patch("src.predict.search_fact_checks", return_value=mock_fc) as mock_search:
            res = predict_url("https://example.com/article")
            assert res["status"] == "success"
            assert "fact_checks" in res
            assert res["fact_checks"]["status"] == "no_matches"
            # Ensure search_fact_checks was called with the article title
            mock_search.assert_called_once_with("Major Infrastructure Bill Passed in Congress")


def test_index_page_renders_fact_check_cards(client):
    """Verifies that the fact-check evidence card renders correctly in the results panel."""
    article_text = (
        "Officials announced a new policy regarding infrastructure spending and public transportation."
    )
    mock_fc = {
        "status": "success",
        "message": "Found 1 matching fact-check.",
        "query_used": "Officials announced a new policy",
        "reviews": [
            {
                "claim_text": "Claims that transit policy will double local tax rates are unfounded.",
                "claimant": "Online meme",
                "claim_date": "Oct 10, 2026",
                "publisher_name": "FactCheck.org",
                "publisher_site": "factcheck.org",
                "review_title": "Transit Taxes Fact Check",
                "review_url": "https://factcheck.org/transit-taxes-claim",
                "review_date": "Oct 10, 2026",
                "textual_rating": "False",
                "rating_badge_class": "badge-false",
            }
        ],
        "notice": "External fact-check evidence notice.",
    }

    with patch("src.predict.search_fact_checks", return_value=mock_fc):
        resp = client.post("/predict", data={"news_text": article_text, "input_mode": "text"})
        assert resp.status_code == 200
        html_content = resp.data.decode("utf-8")
        assert "Related Fact-Checks (External Evidence)" in html_content
        assert "FactCheck.org" in html_content
        assert "https://factcheck.org/transit-taxes-claim" in html_content
        assert "False" in html_content
        assert "Claims that transit policy will double local tax rates are unfounded." in html_content

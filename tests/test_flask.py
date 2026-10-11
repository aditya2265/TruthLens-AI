"""Integration and security tests for the Flask web application."""
import json
import pytest
from src.app import app
from src.config import SECRET_KEY, PRIMARY_MODEL_PATH
from src.history import init_db, clear_all_history, get_recent_history, save_history_record


from unittest.mock import patch

MOCK_FEED = {
    "status": "success",
    "message": "Retrieved 1 articles.",
    "articles": [
        {
            "id": "gdelt-0-1234",
            "title": "Mocked News Headline",
            "url": "https://example.com/mocked-news",
            "source_domain": "example.com",
            "seendate_formatted": "Oct 10, 2026",
            "language": "English",
            "source_country": "United States",
        }
    ],
    "is_cached": False,
    "last_updated": "12:00 UTC",
    "notice": "Discovery feed from GDELT Project.",
}


@pytest.fixture(autouse=True)
def mock_news_feed_for_flask_tests():
    """Mocks external GDELT feed for Flask route integration tests to prevent unmocked external calls."""
    with patch("src.app.fetch_gdelt_news", return_value=MOCK_FEED) as mock_feed:
        yield mock_feed


@pytest.fixture
def client(tmp_path):
    """Test client configured with testing flags and temp database."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False  # Disabled for straightforward route testing
    test_db = tmp_path / "test_history.sqlite3"
    init_db(test_db)

    with app.test_client() as client:
        yield client


@pytest.fixture
def csrf_client():
    """Test client with CSRF explicitly ENABLED to test security enforcement."""
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = True

    with app.test_client() as client:
        yield client


def test_homepage_loads_successfully(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"TruthLens" in response.data
    assert b"Fake News &amp; Misleading Content Detector" in response.data or b"Fake News & Misleading Content Detector" in response.data


def test_health_endpoint_no_information_disclosure(client):
    response = client.get("/health")
    # If model is trained, returns 200; if missing, returns 503
    assert response.status_code in (200, 503)
    data = json.loads(response.data)
    assert "status" in data
    assert "model_loaded" in data

    # Verify NO secrets, file paths, or stack traces are disclosed
    content_str = response.data.decode("utf-8")
    assert SECRET_KEY not in content_str
    assert "C:\\" not in content_str
    assert "d:\\" not in content_str
    assert "Traceback" not in content_str


def test_about_page_loads(client):
    response = client.get("/about")
    assert response.status_code == 200
    assert b"Methodology" in response.data
    assert b"Pillar A: Machine Learning" in response.data


def test_performance_page_loads(client):
    response = client.get("/performance")
    assert response.status_code == 200
    assert b"Held-Out Test Set Performance" in response.data or b"Model Training Required" in response.data


def test_404_custom_error_page(client):
    response = client.get("/non-existent-route-xyz")
    assert response.status_code == 404
    assert b"Page Not Found" in response.data


def test_csrf_enforcement_blocks_unauthenticated_post(csrf_client):
    # Attempt POST without CSRF token
    response = csrf_client.post("/predict", data={"news_text": "Sample test article text."})
    # Must be rejected due to CSRF failure
    assert response.status_code == 400
    assert b"CSRF" in response.data


def test_valid_text_submission_returns_prediction(client):
    article = (
        "The committee announced new regulatory guidelines for consumer financial protection on Wednesday. "
        "Federal representatives noted that public comments will be accepted through next month."
    )
    response = client.post("/predict", data={"news_text": article})
    assert response.status_code == 200
    assert b"Automated Assessment Result" in response.data
    assert b"Token Explanation" in response.data
    assert b"Writing Style Signals" in response.data


def test_empty_input_redirects_with_warning(client):
    response = client.post("/predict", data={"news_text": "   "}, follow_redirects=True)
    assert response.status_code == 200
    assert b"Please enter a valid URL" in response.data or b"Please enter" in response.data


def test_api_predict_json_endpoint(client):
    payload = {"text": "Federal Reserve officials held benchmark rates steady during the recent review meeting."}
    response = client.post("/api/predict", json=payload)
    assert response.status_code == 200
    data = json.loads(response.data)
    assert data["status"] == "success"
    assert "predicted_label" in data
    assert "explanation" in data
    assert "clickbait_analysis" in data


def test_api_predict_rejects_missing_field(client):
    response = client.post("/api/predict", json={"wrong_key": "abc"})
    assert response.status_code == 400


def test_local_history_flow(tmp_path):
    test_db = tmp_path / "hist.sqlite3"
    init_db(test_db)

    # Save record
    rec_id = save_history_record(
        predicted_label="Reliable-style patterns",
        predicted_class=0,
        decision_score=0.95,
        is_uncertain=False,
        text="Sample test news story headline.",
        model_version="1.0.0",
        db_path=test_db,
    )
    assert rec_id is not None

    records = get_recent_history(limit=10, db_path=test_db)
    assert len(records) == 1
    assert records[0]["predicted_label"] == "Reliable-style patterns"

    # Clear records
    clear_all_history(test_db)
    cleared = get_recent_history(limit=10, db_path=test_db)
    assert len(cleared) == 0


def test_flask_url_submission_success(client):
    from unittest.mock import patch
    mock_url_res = {
        "status": "success",
        "message": "Successfully extracted main article text.",
        "url": "https://example.com/valid-article",
        "source_domain": "example.com",
        "extracted_title": "Sample Valid Article Title",
        "extracted_text": "Federal Reserve officials held benchmark rates steady during the recent review meeting in Washington.",
        "extracted_excerpt": "Federal Reserve officials held benchmark rates steady...",
        "publication_date": "2026-10-10",
        "fetch_notice": "Fetched article from example.com.",
    }

    with patch("src.url_fetcher.fetch_and_extract_url", return_value=mock_url_res):
        response = client.post(
            "/predict",
            data={"input_mode": "url", "article_url": "https://example.com/valid-article"},
        )
        assert response.status_code == 200
        assert b"Automated Assessment Result" in response.data
        assert b"Sample Valid Article Title" in response.data
        assert b"example.com" in response.data


def test_flask_url_submission_ssrf_blocked(client):
    from unittest.mock import patch
    mock_url_res = {
        "status": "security_blocked",
        "message": "Security block: Loopback addresses (127.0.0.1) are prohibited.",
        "url": "http://127.0.0.1/secret",
        "source_domain": "127.0.0.1",
        "extracted_title": "",
        "extracted_text": "",
        "extracted_excerpt": "",
        "publication_date": None,
        "fetch_notice": "URL validation failed.",
    }

    with patch("src.url_fetcher.fetch_and_extract_url", return_value=mock_url_res):
        response = client.post(
            "/predict",
            data={"input_mode": "url", "article_url": "http://127.0.0.1/secret"},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Security block" in response.data or b"prohibited" in response.data or b"URL Analysis Error" in response.data or b"URL analysis failed" in response.data


def test_flask_api_predict_url_mode(client):
    from unittest.mock import patch
    mock_url_res = {
        "status": "success",
        "message": "Successfully extracted main article text.",
        "url": "https://example.com/valid-article",
        "source_domain": "example.com",
        "extracted_title": "Sample Valid Article Title",
        "extracted_text": "Federal Reserve officials held benchmark rates steady during the recent review meeting.",
        "extracted_excerpt": "Federal Reserve officials held benchmark rates steady...",
        "publication_date": "2026-10-10",
        "fetch_notice": "Fetched article from example.com.",
    }

    with patch("src.url_fetcher.fetch_and_extract_url", return_value=mock_url_res):
        payload = {"url": "https://example.com/valid-article"}
        response = client.post("/api/predict", json=payload)
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data["status"] == "success"
        assert "predicted_label" in data
        assert data["url_metadata"]["source_domain"] == "example.com"



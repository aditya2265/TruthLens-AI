"""Unit and security tests for URL validation, SSRF defenses, and Trafilatura article extraction."""
import socket
from unittest.mock import MagicMock, patch
import pytest
import requests

from src.url_fetcher import (
    MAX_REDIRECTS,
    MAX_RESPONSE_BYTES,
    fetch_and_extract_url,
    fetch_url_safely,
    is_ip_prohibited,
    validate_and_resolve_url,
)


# --- 1. IP Validation Tests ---
@pytest.mark.parametrize(
    "ip_str,expected_prohibited",
    [
        ("127.0.0.1", True),
        ("127.0.0.5", True),
        ("::1", True),
        ("10.0.0.1", True),
        ("10.255.255.255", True),
        ("172.16.0.1", True),
        ("192.168.1.1", True),
        ("169.254.169.254", True),
        ("169.254.1.1", True),
        ("224.0.0.1", True),  # Multicast
        ("0.0.0.0", True),
        ("8.8.8.8", False),  # Google Public DNS (Valid)
        ("1.1.1.1", False),  # Cloudflare DNS (Valid)
        ("93.184.216.34", False),  # example.com (Valid)
    ],
)
def test_is_ip_prohibited(ip_str, expected_prohibited):
    import ipaddress

    ip_obj = ipaddress.ip_address(ip_str)
    prohibited, reason = is_ip_prohibited(ip_obj)
    assert prohibited == expected_prohibited
    if expected_prohibited:
        assert len(reason) > 0


# --- 2. URL Scheme & Formatting Validation ---
def test_validate_url_rejects_empty_or_non_string():
    is_valid, ip, host, err = validate_and_resolve_url("")
    assert not is_valid
    assert "empty or malformed" in err.lower()

    is_valid, ip, host, err = validate_and_resolve_url(None)  # type: ignore
    assert not is_valid


@pytest.mark.parametrize(
    "unsupported_url",
    [
        "ftp://example.com/file.txt",
        "file:///etc/passwd",
        "file://C:/Windows/System32/cmd.exe",
        "gopher://example.com",
        "sftp://example.com",
        "javascript:alert(1)",
        "data:text/html,<h1>Hello</h1>",
    ],
)
def test_validate_url_rejects_unsupported_schemes(unsupported_url):
    is_valid, ip, host, err = validate_and_resolve_url(unsupported_url)
    assert not is_valid
    assert "not allowed" in err.lower() or "only http and https" in err.lower()


def test_validate_url_rejects_embedded_credentials():
    url = "http://admin:secret123@example.com/page"
    is_valid, ip, host, err = validate_and_resolve_url(url)
    assert not is_valid
    assert "embedded credentials" in err.lower()


@pytest.mark.parametrize(
    "blocked_host",
    [
        "http://localhost/admin",
        "http://localhost:8080/api",
        "http://127.0.0.1/status",
        "http://[::1]/secret",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://10.0.0.1/router",
        "http://192.168.0.1/",
    ],
)
def test_validate_url_rejects_localhost_and_internal_ips(blocked_host):
    is_valid, ip, host, err = validate_and_resolve_url(blocked_host)
    assert not is_valid
    assert "prohibited" in err.lower() or "security block" in err.lower()


# --- 3. Hostname DNS Resolution Security (DNS Rebinding & Private Resolution) ---
def test_validate_url_rejects_hostname_resolving_to_private_ip():
    # Mock DNS resolution for a seemingly harmless domain resolving to loopback/private IP
    mock_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        is_valid, ip, host, err = validate_and_resolve_url("http://rebinding-attack.com/article")
        assert not is_valid
        assert "resolves to prohibited ip" in err.lower()
        assert ip == "127.0.0.1"


def test_validate_url_accepts_valid_public_domain():
    mock_addr_info = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
    ]
    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        is_valid, ip, host, err = validate_and_resolve_url("https://example.com/news/123")
        assert is_valid
        assert ip == "93.184.216.34"
        assert host == "example.com"
        assert err == ""


def test_validate_url_handles_dns_resolution_failure():
    with patch("socket.getaddrinfo", side_effect=socket.gaierror("Name or service not known")):
        is_valid, ip, host, err = validate_and_resolve_url("https://this-domain-does-not-exist-xyz1239999.com")
        assert not is_valid
        assert "dns resolution failed" in err.lower()


# --- 4. Safe Fetching & SSRF Defense Tests ---
def test_fetch_url_safely_successful_html():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_redirect = False
    mock_response.headers = {"Content-Type": "text/html; charset=utf-8"}
    mock_response.iter_content.return_value = [b"<html><body><h1>News Article</h1><p>Content here.</p></body></html>"]
    mock_response.encoding = "utf-8"

    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", return_value=mock_response):
            success, html, final_url, domain = fetch_url_safely("http://example.com/article")
            assert success
            assert "News Article" in html
            assert domain == "example.com"


def test_fetch_url_safely_blocks_redirect_to_private_ip():
    # First response: 302 Redirect pointing to internal IP
    redirect_resp = MagicMock()
    redirect_resp.status_code = 302
    redirect_resp.is_redirect = True
    redirect_resp.headers = {"Location": "http://169.254.169.254/latest/meta-data/"}

    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", return_value=redirect_resp):
            success, err, final_url, domain = fetch_url_safely("http://example.com/redirect")
            assert not success
            assert "redirect blocked" in err.lower() or "prohibited" in err.lower()


def test_fetch_url_safely_exceeds_max_redirects():
    redirect_resp = MagicMock()
    redirect_resp.status_code = 301
    redirect_resp.is_redirect = True
    redirect_resp.headers = {"Location": "http://example.com/redirect-loop"}

    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", return_value=redirect_resp):
            success, err, final_url, domain = fetch_url_safely("http://example.com/redirect-loop")
            assert not success
            assert f"exceeded maximum allowed redirects ({MAX_REDIRECTS})" in err.lower()


def test_fetch_url_safely_rejects_oversized_response():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_redirect = False
    mock_response.headers = {"Content-Type": "text/html"}
    # Stream chunks that exceed 2MB cap
    large_chunk = b"A" * (1024 * 1024)
    mock_response.iter_content.return_value = [large_chunk, large_chunk, large_chunk]

    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", return_value=mock_response):
            success, err, final_url, domain = fetch_url_safely("http://example.com/largefile")
            assert not success
            assert "maximum limit" in err.lower()


def test_fetch_url_safely_timeout_handling():
    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", side_effect=requests.exceptions.Timeout("Connection timed out")):
            success, err, final_url, domain = fetch_url_safely("http://example.com/slow")
            assert not success
            assert "timed out" in err.lower()


def test_fetch_url_safely_unsupported_content_type():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_redirect = False
    mock_response.headers = {"Content-Type": "application/pdf"}

    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", return_value=mock_response):
            success, err, final_url, domain = fetch_url_safely("http://example.com/document.pdf")
            assert not success
            assert "unsupported content-type" in err.lower()


# --- 5. Trafilatura Extraction & Fail-Safe Behavior ---
def test_fetch_and_extract_url_successful_extraction():
    html_content = (
        "<html><head><title>Breaking News: Major Accord Signed</title></head>"
        "<body><article><p>Representatives from twenty nations signed a landmark climate agreement today in Geneva. "
        "The treaty establishes unified targets for carbon reduction over the next decade.</p></article></body></html>"
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_redirect = False
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.iter_content.return_value = [html_content.encode("utf-8")]
    mock_response.encoding = "utf-8"

    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", return_value=mock_response):
            res = fetch_and_extract_url("https://example.com/news/climate-accord")
            assert res["status"] == "success"
            assert "landmark climate agreement" in res["extracted_text"]
            assert res["extracted_title"] != ""
            assert res["source_domain"] == "example.com"
            assert res["publication_date"] is not None or res["publication_date"] is None


def test_fetch_and_extract_url_handles_empty_extraction_without_fabrication():
    # Webpage with zero main text (e.g. paywall / JS SPA shell)
    html_content = "<html><body><script>window.location='/login';</script></body></html>"

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.is_redirect = False
    mock_response.headers = {"Content-Type": "text/html"}
    mock_response.iter_content.return_value = [html_content.encode("utf-8")]
    mock_response.encoding = "utf-8"

    mock_addr_info = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]

    with patch("socket.getaddrinfo", return_value=mock_addr_info):
        with patch("requests.Session.get", return_value=mock_response):
            res = fetch_and_extract_url("https://example.com/paywalled-article")
            assert res["status"] == "extraction_failed"
            assert res["extracted_text"] == ""
            assert res["extracted_excerpt"] == ""
            assert "could not extract" in res["message"].lower() or "zero text" in res["fetch_notice"].lower()


def test_fetch_and_extract_url_blocks_security_threats_immediately():
    res = fetch_and_extract_url("http://127.0.0.1/admin/delete")
    assert res["status"] == "security_blocked"
    assert res["extracted_text"] == ""
    assert "prohibited" in res["message"].lower()

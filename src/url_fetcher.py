"""Secure URL validation, SSRF protection, and article text extraction module for TruthLens AI.

Enforces strict network security:
1. HTTP and HTTPS schemes only (blocks file://, ftp://, gopher://, etc.).
2. Embedded credentials check (rejects http://user:pass@host).
3. DNS resolution & IP validation: blocks loopback (127.0.0.0/8, ::1),
   private (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16, fc00::/7),
   link-local (169.254.0.0/16, fe80::/10), cloud metadata (169.254.169.254, etc.).
4. Per-redirect target IP re-validation (max 3 redirects).
5. Strict timeouts (5s connect / 10s read), 2 MB size cap, and HTML content-type check.
6. Main article text extraction via trafilatura.
"""
import ipaddress
import re
import socket
import urllib.parse
from typing import Any, TypedDict
import requests
import trafilatura


class URLExtractionResult(TypedDict):
    status: str  # "success", "invalid_url", "security_blocked", "extraction_failed", "timeout", "oversized"
    message: str
    url: str
    source_domain: str
    extracted_title: str
    extracted_text: str
    extracted_excerpt: str
    publication_date: str | None
    fetch_notice: str


# Maximum allowed response size (2 MB)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# Timeouts in seconds: (connect_timeout, read_timeout)
TIMEOUT_CONFIG = (5.0, 10.0)

# Max allowed HTTP redirects
MAX_REDIRECTS = 3

# Specific cloud metadata hostnames & IP strings
PROHIBITED_METADATA_HOSTS = {
    "169.254.169.254",
    "169.254.169.253",
    "metadata.google.internal",
    "metadata.gcp.internal",
    "100.100.100.200",
}


def is_ip_prohibited(ip_obj: ipaddress.IPv4Address | ipaddress.IPv6Address) -> tuple[bool, str]:
    """Checks if an IP address falls into loopback, private, link-local, or reserved ranges."""
    if ip_obj.is_loopback:
        return True, "Loopback addresses (127.0.0.0/8, ::1) are prohibited."
    if ip_obj.is_private:
        return True, "Private local network IP addresses are prohibited."
    if ip_obj.is_link_local:
        return True, "Link-local IP addresses (169.254.0.0/16) are prohibited."
    if ip_obj.is_multicast:
        return True, "Multicast IP addresses are prohibited."
    if ip_obj.is_reserved:
        return True, "Reserved IP addresses are prohibited."
    if ip_obj.is_unspecified:
        return True, "Unspecified IP addresses (0.0.0.0, ::) are prohibited."

    # Explicit check for 169.254.169.254 cloud metadata
    ip_str = str(ip_obj)
    if ip_str in PROHIBITED_METADATA_HOSTS:
        return True, "Access to cloud metadata endpoints is prohibited."

    return False, "IP is valid."


def validate_and_resolve_url(url_string: str) -> tuple[bool, str, str, str]:
    """Validates URL format, scheme, embedded credentials, and resolves hostname to non-prohibited IP.

    Returns:
        tuple (is_valid, resolved_ip, hostname, error_reason)
    """
    if not url_string or not isinstance(url_string, str):
        return False, "", "", "URL is empty or malformed."

    url_str = url_string.strip()

    try:
        parsed = urllib.parse.urlparse(url_str)
    except Exception:
        return False, "", "", "Failed to parse URL format."

    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        return False, "", "", f"Scheme '{scheme}' is not allowed. Only http and https URLs are supported."

    if parsed.username or parsed.password:
        return False, "", "", "URLs with embedded credentials (user:pass@host) are prohibited."

    hostname = parsed.hostname
    if not hostname:
        return False, "", "", "URL lacks a valid domain name or hostname."

    hostname_lower = hostname.lower()
    if hostname_lower in PROHIBITED_METADATA_HOSTS or hostname_lower == "localhost":
        return False, "", "", "Access to localhost or internal metadata hosts is prohibited."

    # Direct IP literal check
    try:
        ip_obj = ipaddress.ip_address(hostname)
        is_prohibited, reason = is_ip_prohibited(ip_obj)
        if is_prohibited:
            return False, str(ip_obj), hostname, f"Security block: {reason}"
        return True, str(ip_obj), hostname, ""
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution

    # DNS Resolution
    try:
        # Resolve hostname to IPv4 / IPv6 addresses
        addr_info = socket.getaddrinfo(hostname, parsed.port or (443 if scheme == "https" else 80), proto=socket.IPPROTO_TCP)
        if not addr_info:
            return False, "", hostname, f"DNS resolution yielded no IP addresses for '{hostname}'."

        resolved_ips = set()
        for family, _, _, _, sockaddr in addr_info:
            ip_str = sockaddr[0]
            resolved_ips.add(ip_str)

        # Audit EVERY resolved IP address
        for ip_str in resolved_ips:
            try:
                ip_obj = ipaddress.ip_address(ip_str)
                is_prohibited, reason = is_ip_prohibited(ip_obj)
                if is_prohibited:
                    return False, ip_str, hostname, f"Security block: Domain '{hostname}' resolves to prohibited IP ({ip_str}). {reason}"
            except ValueError:
                return False, ip_str, hostname, f"Resolved IP string '{ip_str}' is invalid."

        # Return first resolved IP for connection
        first_ip = list(resolved_ips)[0]
        return True, first_ip, hostname, ""

    except socket.gaierror as e:
        return False, "", hostname, f"DNS resolution failed for domain '{hostname}'."
    except Exception as e:
        return False, "", hostname, f"Network validation failed: {str(e)}"


def fetch_url_safely(url_string: str) -> tuple[bool, str, str, str]:
    """Fetches HTML content with strict SSRF defenses, redirect re-validation, timeouts, and size caps.

    Returns:
        tuple (success, html_text_or_error, final_url, domain)
    """
    is_valid, resolved_ip, hostname, err = validate_and_resolve_url(url_string)
    if not is_valid:
        return False, err, url_string, hostname

    current_url = url_string
    session = requests.Session()

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (compatible; TruthLens/1.0)",
        "Accept": "text/html,application/xhtml+xml,text/plain;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    redirect_count = 0
    while redirect_count <= MAX_REDIRECTS:
        # Validate current target URL before each hop
        val_ok, target_ip, cur_host, val_err = validate_and_resolve_url(current_url)
        if not val_ok:
            return False, f"Redirect blocked: {val_err}", current_url, cur_host

        try:
            # Execute HTTP request without automatic redirects so we audit each hop
            resp = session.get(
                current_url,
                headers=headers,
                timeout=TIMEOUT_CONFIG,
                stream=True,
                allow_redirects=False,
                verify=True,  # Never disable TLS verification
            )

            # Handle redirects manually
            if resp.is_redirect or resp.status_code in (301, 302, 303, 307, 308):
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    return False, f"Exceeded maximum allowed redirects ({MAX_REDIRECTS}).", current_url, cur_host

                location = resp.headers.get("Location")
                if not location:
                    return False, "Redirect response missing Location header.", current_url, cur_host

                current_url = urllib.parse.urljoin(current_url, location)
                continue

            if resp.status_code != 200:
                return False, f"Server returned HTTP status code {resp.status_code}.", current_url, cur_host

            # Check Content-Type header
            content_type = resp.headers.get("Content-Type", "").lower()
            if content_type and not any(ct in content_type for ct in ["text/html", "text/plain", "application/xhtml+xml"]):
                return False, f"Unsupported Content-Type '{content_type}'. Only HTML/text pages are supported.", current_url, cur_host

            # Read response body in chunks to enforce size limit
            content_bytes = bytearray()
            for chunk in resp.iter_content(chunk_size=8192):
                content_bytes.extend(chunk)
                if len(content_bytes) > MAX_RESPONSE_BYTES:
                    return False, f"Page size exceeded maximum limit of {MAX_RESPONSE_BYTES // (1024*1024)} MB.", current_url, cur_host

            # Decode text safely
            encoding = resp.encoding or "utf-8"
            html_text = content_bytes.decode(encoding, errors="replace")
            return True, html_text, current_url, cur_host

        except requests.exceptions.Timeout:
            return False, "Connection timed out while fetching webpage.", current_url, cur_host
        except requests.exceptions.SSLError:
            return False, "SSL/TLS certificate verification failed.", current_url, cur_host
        except requests.exceptions.RequestException as e:
            return False, f"HTTP request failed: {str(e)}", current_url, cur_host
        except Exception as e:
            return False, f"Fetch error: {str(e)}", current_url, cur_host

    return False, "Excessive redirects.", current_url, hostname


def fetch_and_extract_url(url_string: str) -> URLExtractionResult:
    """Primary entry point: Fetches URL safely and extracts main article text via Trafilatura.

    Never fabricates text on failure.
    """
    is_valid, resolved_ip, hostname, val_err = validate_and_resolve_url(url_string)
    if not is_valid:
        return {
            "status": "security_blocked" if "Security block" in val_err else "invalid_url",
            "message": val_err,
            "url": url_string,
            "source_domain": hostname or "unknown",
            "extracted_title": "",
            "extracted_text": "",
            "extracted_excerpt": "",
            "publication_date": None,
            "fetch_notice": "URL validation failed.",
        }

    success, content_or_err, final_url, domain = fetch_url_safely(url_string)
    if not success:
        return {
            "status": "extraction_failed",
            "message": content_or_err,
            "url": final_url,
            "source_domain": domain,
            "extracted_title": "",
            "extracted_text": "",
            "extracted_excerpt": "",
            "publication_date": None,
            "fetch_notice": f"Unable to fetch content from {domain}.",
        }

    # Extract article body & metadata using Trafilatura
    try:
        extracted_text = trafilatura.extract(
            content_or_err,
            include_links=False,
            include_images=False,
            include_comments=False,
            favor_precision=True,
        )

        bare_meta = trafilatura.bare_extraction(content_or_err)
        title = bare_meta.get("title", "") if bare_meta else ""
        date = bare_meta.get("date", None) if bare_meta else None

        if not extracted_text or not extracted_text.strip():
            # Fallback extraction: extract main body paragraphs from HTML
            p_matches = re.findall(r'<p[^>]*>(.*?)</p>', content_or_err, re.IGNORECASE | re.DOTALL)
            clean_paras = []
            for p in p_matches:
                cleaned_p = re.sub(r'<[^>]+>', ' ', p)
                cleaned_p = ' '.join(cleaned_p.split())
                if len(cleaned_p) > 35:
                    clean_paras.append(cleaned_p)
            if clean_paras and len(clean_paras) >= 2:
                extracted_text = "\n\n".join(clean_paras)

        if not extracted_text or not extracted_text.strip():
            return {
                "status": "extraction_failed",
                "message": (
                    "Could not extract main article text from the specified URL. "
                    "The webpage may require JavaScript rendering, sit behind a paywall, "
                    "or lack sufficient body text."
                ),
                "url": final_url,
                "source_domain": domain,
                "extracted_title": title or domain,
                "extracted_text": "",
                "extracted_excerpt": "",
                "publication_date": date,
                "fetch_notice": f"Extracted zero text body from {domain}.",
            }

        cleaned_text = extracted_text.strip()
        excerpt = cleaned_text[:200] + ("..." if len(cleaned_text) > 200 else "")

        return {
            "status": "success",
            "message": "Successfully extracted main article text.",
            "url": final_url,
            "source_domain": domain,
            "extracted_title": title or f"Article from {domain}",
            "extracted_text": cleaned_text,
            "extracted_excerpt": excerpt,
            "publication_date": date,
            "fetch_notice": f"Fetched article from {domain}. Downloading text does not verify its claims.",
        }

    except Exception as e:
        return {
            "status": "extraction_failed",
            "message": f"Trafilatura extraction error: {str(e)}",
            "url": final_url,
            "source_domain": domain,
            "extracted_title": "",
            "extracted_text": "",
            "extracted_excerpt": "",
            "publication_date": None,
            "fetch_notice": f"Extraction error on {domain}.",
        }

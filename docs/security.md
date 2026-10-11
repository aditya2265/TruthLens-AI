# TruthLens AI — Security and Privacy Architecture

## 1. Security Engineering Principles
TruthLens AI follows defence-in-depth security principles across all application layers: web presentation, input validation, outbound remote fetching, external API integrations, machine-learning pipeline isolation, and data persistence.

---

## 2. Core Implemented Controls

### A. Cross-Site Request Forgery (CSRF) Protection
- **Implementation:** `flask_wtf.csrf.CSRFProtect` is initialized on the Flask application instance.
- **Coverage:** All state-changing HTML POST forms (`/predict`, `/history/<id>/delete`, `/history/clear`) mandate and validate a cryptographic CSRF token.
- **API Exemption:** The machine-to-machine JSON endpoint (`POST /api/predict`) is explicitly marked `@csrf.exempt` for REST interoperability, while enforcing strict JSON body validation.
- **Verification:** Automated unit test in `tests/test_flask.py::test_csrf_enforcement_blocks_unauthenticated_post`.

### B. Input Validation & Resource Exhaustion Defense
- **Maximum Length:** Input text is capped at 15,000 characters (`MAX_INPUT_LENGTH`). Submissions exceeding this limit are safely truncated with an alert message.
- **Empty / Whitespace Check:** Server-side validation catches empty or whitespace submissions before pipeline execution, returning descriptive feedback.
- **Safe Pipeline Execution:** Model persistence loads strictly from fixed relative internal paths (`models/truthlens_model.joblib`). User input is never passed to `eval()`, `exec()`, or dynamic shell invocations.

### C. Prevention of Sensitive Information Disclosure
- **Health Check (`GET /health`):** Returns only operational readiness boolean, environment name, and model version. No internal file paths, API keys, database credentials, or stack traces are included.
- **Custom Error Handlers:** Production-safe 400, 404, and 500 error templates suppress Python exception tracebacks and internal stack information.
- **Git Hygiene:** `.env` and `instance/` (SQLite database) are strictly ignored in `.gitignore`.

### D. Local Privacy and Database Security
- **Local-Only History:** History records reside in a local SQLite file (`instance/truthlens_history.sqlite3`).
- **SQL Injection Defense:** All queries utilize parameterized SQL statements with `?` placeholders.
- **Data Minimization:** Full article bodies are never persisted to history; only short 120-character excerpts are retained for review.
- **User Control:** Users can selectively delete individual records or clear the entire history database at any time.

---

## 3. Remote URL Analysis & Server-Side Request Forgery (SSRF) Defense

Outbound article fetching in `src/url_fetcher.py` enforces rigorous SSRF mitigation before making HTTP requests:

1. **Protocol Whitelisting:** Permits only `http` and `https`. Schemes like `file://`, `ftp://`, `gopher://`, `data:`, and `javascript:` are immediately rejected.
2. **Credential Stripping:** Embedded user credentials (`http://user:pass@host`) are rejected to avoid authentication spoofing.
3. **Comprehensive IP Blacklisting (`is_ip_prohibited`):**
   - Loopback addresses (`127.0.0.0/8`, `::1`).
   - Private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`).
   - Link-local subnets (`169.254.0.0/16`).
   - Cloud instance metadata endpoints (`169.254.169.254`, `metadata.google.internal`).
   - Multicast (`224.0.0.0/4`) and wildcard (`0.0.0.0`).
4. **Pre-Flight DNS Resolution:** `socket.getaddrinfo` resolves hostnames and validates that *every* resolved IP address is public before initiating any socket connection.
5. **Redirect Auditing:** Redirects are manually inspected (maximum 3 redirects). Each redirect target undergoes full scheme and IP range re-validation before being followed.
6. **Streaming Size Limit:** Response streams are capped at 2 MB. Connections are immediately aborted if content exceeds this boundary.
7. **Strict Bounded Timeouts:** Connect timeout is set to 5.0 seconds; read timeout is set to 10.0 seconds.
8. **Mandatory TLS Verification:** All HTTPS requests enforce valid certificate validation (`verify=True`).
9. **Remaining Limitation (DNS Rebinding):** While pre-flight DNS resolution validates IP addresses, standard Python `requests` establishes its socket connection via a secondary internal resolution. In production environments where high-assurance DNS rebinding defense is required, a custom socket transport adapter pinning the validated IP address should be utilized.

---

## 4. Live News Feed Security (GDELT Integration)

The live headline feed in `src/news_feed.py` interacts with the public GDELT 2.0 DOC API:

- **Fixed Endpoint:** Requests are sent strictly to `https://api.gdeltproject.org/api/v2/doc/doc`. The target URL is immutable and non-user-controllable.
- **Keyless Public Access:** No API keys or credentials are required or transmitted.
- **Bounded Timeouts & Streaming Cap:** Bounded timeouts (15s connect, 25s read) accommodate GDELT server latency, while response payloads are capped at 1 MB.
- **Rate-Limit Defense:** Recognizes HTTP 429 and text-based rate limit notices, enforcing a client-side 5.0-second throttle to prevent API flooding.
- **URL Canonicalization:** Tracking parameters (`utm_*`, `fbclid`, etc.) are stripped to prevent cache duplication.

---

## 5. Google Fact Check Tools API Security

The external evidence lookup in `src/factcheck.py` queries the official Google Fact Check Tools API:

- **Environment-Only Secrets:** Configured via `GOOGLE_FACTCHECK_API_KEY` in `src/config.py`. Never hardcoded in source code or template files.
- **Zero Frontend Leakage:** API keys are never exposed in HTML, client JavaScript, error responses, or `/health`.
- **Query Bounding:** Search queries extracted from titles or articles are capped at 120 characters.
- **Bounded Timeouts & Resilience:** Connect timeout of 4.0s, read timeout of 8.0s, and 1 MB streaming cap. API errors (400, 403, 429, missing key) fail gracefully without disrupting primary text prediction.

---

## 6. Language Safety & Model Isolation

The language safety engine in `src/language.py` protects against model hallucination and out-of-domain errors:

- **Pure Standard Library:** Implemented with `unicodedata` and `re` without heavy, unverified external dependencies.
- **Classifier Isolation:** Non-English text (including Devanagari Hindi, Cyrillic, Arabic, CJK, etc.) short-circuits immediately before `load_model()` or `predict_proba()`.
- **Zero Sensation Fabrication:** Rules-based clickbait heuristics (tuned for English uppercase and buzzwords) are disabled on non-English inputs.
- **Transparency Notice:** Explicitly informs users that the assessment constraint is a language safety safeguard, not a verdict about the claim.

---

## 7. Production Deployment & WSGI Architecture

- **Development Notice:** The Flask development server (`debug=True` when `FLASK_ENV=development`) is strictly intended for local development and test execution.
- **Production WSGI Recommendation:**
  - **Linux / Cloud Deployments (e.g. Render):** Use `gunicorn --preload -w 1 --threads 8 --timeout 180 -b 0.0.0.0:$PORT src.app:app` (preloads model at boot, provides 8 worker threads for high concurrency, with thread-safe in-memory caching and lock serialization).
  - **Windows Deployments:** Use `waitress-serve --port=5000 src.app:app`.
  - Configure `FLASK_ENV=production` and generate a cryptographically strong `SECRET_KEY`.

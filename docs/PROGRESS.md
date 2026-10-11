# TruthLens AI — Project Progress & Verification Tracker

## Stage Checklists & Status

### Stage 1: Modern Consumer Redesign & UI Overhaul
- [x] Title updated to **"Fake News & Misleading Content Detector"** (Navbar logo: **TruthLens**)
- [x] Light theme enabled by default with CSS variables (`#f8fafc` primary background, `#ffffff` cards, soft shadows)
- [x] Dark-mode toggle button with `localStorage` persistence (`truthlens_theme`) implemented
- [x] Purple primary accent color (`#7c3aed` light / `#a855f7` dark) applied across buttons, badges, highlights
- [x] Hero section updated with pill `"Fake News & Misleading Content Detector"`, headline `"Check it before you <span class="highlight">believe</span> it."`, and subtitle `"Analyzes writing patterns and shows related fact-checks. Does not verify truth by itself."`
- [x] Centered analyzer card with 3 tabs created: **Article Link (URL)** [default], **Paste Text**, and **Image Upload** [disabled with "Coming soon (OCR)" badge]
- [x] Three feature cards added below analyzer card with honest copy:
  1. *"Writing-pattern analysis"* (Machine learning classifier trained on a labeled news dataset to identify lexical patterns)
  2. *"Sensational-language signals"* (Transparent rules-based indicators for excessive capitalization, punctuation, and clickbait phrases)
  3. *"Related fact-checks"* (Searches independent fact-checking databases for matching external evidence)
- [x] All existing pages (Dashboard, About, Performance, History, 404, 500, 400) restyled and verified responsive
- [x] Pytest suite executed (30/30 passed) and live HTTP endpoints verified (HTTP 200 OK)

---

### Stage 2: URL Analysis & Secure Extraction (Completed & Verified)
- [x] Implemented `src/url_fetcher.py` with Trafilatura article text extraction, title, and metadata parser
- [x] Enforced strict SSRF defenses: HTTP/HTTPS only, blocked embedded credentials (`user:pass@host`), blocked loopback (`127.0.0.0/8`, `::1`), private (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`), multicast, and cloud metadata (`169.254.169.254`, `metadata.google.internal`)
- [x] Hostname resolution (`socket.getaddrinfo`) with audit of every resolved IP against prohibited subnets (defends against DNS rebinding)
- [x] Per-redirect target IP re-validation (max 3 redirects), response size cap (2 MB limit), strict timeouts (5s connect / 10s read), content-type checks, and mandatory TLS certificate verification (`verify=True`)
- [x] Wired URL fetcher end-to-end into Flask routes `POST /predict` and `POST /api/predict`
- [x] Updated UI to display extracted URL metadata (title, domain, date, excerpt, fetch notice, original link) or clear error card on extraction/security failure without text fabrication
- [x] Expanded automated test suite with `tests/test_url_fetcher.py` and updated `tests/test_flask.py` (76/76 tests passing, including mocked security, redirect, timeout, oversize, and SSRF tests)

---

### Stage 3: Live API Data on Front Page (Completed & Verified)
- [x] Implemented `src/news_feed.py` provider layer consuming official GDELT 2.0 DOC API (`https://api.gdeltproject.org/api/v2/doc/doc`) with keyless public access, fixed non-user-controllable endpoint, and strict response validation.
- [x] Identified and resolved the root cause of the timeout:
  - Low Connect/Read Timeout: TLS handshake to `api.gdeltproject.org` takes ~9.8s and cross-dataset search query execution takes 12–16s. The previous connect/read timeout of `(3.5s, 6.0s)` aborted requests prematurely with `Connection to GDELT API timed out.`. Adjusted bounded timeout to `(15.0s, 25.0s)` with 1 MB streaming response size cap.
  - Rate Limiting (HTTP 429): GDELT enforces a strict limit of max 1 request per 5 seconds per client IP. Added rate limit detection, client-side 5s request throttling (`MIN_REQUEST_INTERVAL_SECONDS = 5.0`), and user-friendly error notices.
  - Synchronous Route Bottleneck: Eliminated redundant `fetch_gdelt_news()` calls during prediction POST requests and added cached fallback serving.
  - Frontend JS Syntax Error: Resolved unclosed braces in `static/js/main.js` that previously prevented `#btn-refresh-feed` and `.feed-analyze-btn` from binding on page load.
- [x] Implemented URL canonicalization (`canonicalize_url`) to strip tracking query parameters (`utm_*`, `fbclid`, etc.) and ensure reliable article deduplication.
- [x] Rendered 6–9 responsive live headline cards with source domain, publication timestamp, source country, link to original article, and 1-click "Analyze" integration.
- [x] Clear distinction between article publication timestamp (`Published: Oct 10, 2026`) and feed retrieval time (`Feed Retrieved: HH:MM UTC`).
- [x] Client-side dynamic refresh wired to `/api/news-feed?refresh=true` with an honest loading spinner, empty states, and fallback error handling without disruptive full page reloads.
- [x] Expanded test suite in `tests/test_news_feed.py` and `tests/test_flask.py` with comprehensive mocked HTTP tests (success, deduplication, missing fields, timeouts, 429 rate limit, 503 errors, invalid JSON, oversized payloads, caching TTL, route status codes). All 94 tests passing (3.49s).
- [x] Security verified: Fixed endpoint, mandatory TLS verification, bounded size/timeouts, no credentials exposed. Recorded existing DNS-rebinding limitation in SSRF notes.

---

### Stage 4: Related Fact-Checks (External Evidence) (Completed & Verified)
- [x] Implemented `src/factcheck.py` service layer consuming the official Google Fact Check Tools API (`https://factchecktools.googleapis.com/v1alpha1/claims:search`).
- [x] Secure API configuration via `GOOGLE_FACTCHECK_API_KEY` in `src/config.py` and documented in `.env.example`. Never hardcoded or exposed in frontend, templates, logs, or error responses.
- [x] Query extraction heuristic (`extract_factcheck_query`): Prioritizes extracted article title for URL analysis; extracts concise leading claim/sentence (bounded to 120 chars) for text analysis.
- [x] Robust response validation & deduplication: Parsed claim statements, reviewer/publisher attribution, publication dates, verbatim publisher ratings, and direct source links. Deduplicated by review URL and claim text.
- [x] Graceful error & missing-key handling: Clear configuration card and setup instructions when key is missing; handles HTTP 400/403, HTTP 429 quota limits, connect/read timeouts (`4.0s, 8.0s`), and malformed responses without blocking primary prediction.
- [x] Integrated into Flask backend (`src/predict.py`, `src/app.py` with `/api/fact-check` endpoint) across both Text and URL submission workflows without re-fetching article text.
- [x] UI Evidence Display: Added "C. Related Fact-Checks (External Evidence)" in `templates/index.html` and styled in `static/css/style.css` with responsive cards, publisher badges, verbatim rating pills, publication dates, and original review links.
- [x] Clear distinction: ML classification, rules-based clickbait indicators, and external fact checks are explicitly separated, with transparency notice stating external reviews are supporting evidence about related claims rather than automatic proof of whole-article veracity.
- [x] Automated testing: Implemented `tests/test_factcheck.py` with 22 mocked test cases covering success, deduplication, empty results, missing/malformed fields, missing key, 403, 429, 500, timeouts, network errors, JSON parsing, oversized payloads, query bounding, route handling, and frontend rendering. All 116 tests passing (4.27s).

---

### Stage 5: Language Safety (Completed & Verified)
- [x] Implemented `src/language.py` providing standard-library-only (`unicodedata`, `re`, `typing`) language safety checks without heavy external dependencies.
- [x] Supported scripts & languages:
  - Unicode block analysis for non-Latin scripts: Devanagari (Hindi `\u0900-\u097F`), Cyrillic, Arabic, CJK (Chinese/Japanese), Hangul, Bengali, Tamil, Telugu, and other major non-Latin alphabets.
  - Stopword vocabulary frequency analysis for Latin-script foreign languages: Spanish, French, German, Italian, Portuguese, and romanized Hindi (Hinglish).
  - Common English function word density check on multi-word text.
- [x] Short-circuited ML classifier and rules-based indicators:
  - Wired `detect_language` directly into `src/predict.py` (`predict_text` and `predict_url`) before model pipeline loading (`load_model()`), feature extraction, or clickbait rule execution (`analyze_writing_style()`).
  - For non-English input, returns exact user-facing message: `"Unable to assess: this model was trained on English news."`
  - Completely omits verdict (`predicted_label = None`), confidence scores (`confidence_score = None`, `decision_score = None`), and fake/real labels.
- [x] UI & API Integration:
  - Updated `templates/index.html` with dedicated `unsupported_language` card adhering to Stage 1 styling, dark/light themes, and displaying URL metadata, related fact-checks, and the 5-step verification checklist.
  - Prominent transparency note added: *"This is an automated language constraint, not a verdict about the truth, accuracy, or reliability of the claim."*
  - Updated `POST /api/predict` in `src/app.py` to return HTTP 200 with `status: "unsupported_language"` and exact message.
- [x] Files created or modified:
  - `src/language.py` (Created: pure Python standard library language safety module)
  - `src/predict.py` (Modified: wired `detect_language` to short-circuit before model loading and rules evaluation)
  - `src/app.py` (Modified: added `"unsupported_language"` to allowed 200 HTTP response statuses in `api_predict`)
  - `templates/index.html` (Modified: added `unsupported_language` results card with transparency note)
  - `tests/test_language.py` (Created: 18 unit, integration, and UI tests)
- [x] Automated testing: Implemented `tests/test_language.py` (18 test cases) covering English pass-through, Hindi (Devanagari) rejection, non-English URL extraction rejection, mock proving `load_model` is never called, empty/short/mixed/ambiguous inputs, and Flask HTML/API routes. Full test suite: 134/134 passed (14.59s) with 0 failures and 0 regressions.
- [x] Remaining limitations for short or mixed-language text:
  - Extremely short snippets (< 4 words) without script markers (e.g. acronyms or proper nouns like "NASA Update") pass language safety and rely on the input-brevity quality warning.
  - Mixed code (Hinglish) with heavy English grammar and fewer than 3 distinguishing Romanized markers may pass to the classifier, where low TF-IDF vocabulary overlap flags it as out-of-distribution.
- [x] Manual verification steps:
  1. Submit Hindi text (`"भारत ने अंतरिक्ष में नया उपग्रह लॉन्च किया"`) via Text input tab: verify exact message `"Unable to assess: this model was trained on English news."`, no verdict badge, and clarification note that this is not a verdict.
  2. Submit URL yielding non-English text: verify extraction displays metadata while model classification is skipped.
  3. Send `POST /api/predict` with `{"text": "भारत सरकार..."}`: verify HTTP 200 with `status: "unsupported_language"`.
  4. Submit English headline: verify normal prediction flow, confidence scores, and explanations remain intact.

---

### Stage 6: Verification and Report (Completed & Verified)
### Stage 6: Verification and Report (Completed & Verified)
- [x] Full automated test suite executed via `.\.venv\Scripts\python.exe -m pytest -q`: 139 passed in 15.95s (0 failed, 0 skipped, 0 errors, 0 regressions, 2 warnings).
- [x] Full demonstration and readiness check executed via `powershell -ExecutionPolicy Bypass -File ".\scripts\demo_check.ps1"`:
  - [1/6] Pytest test suite executed: PASS (139 passed)
  - [2/6] Model and evaluation artifacts verified: PASS (`truthlens_model.joblib`, 98.55% test accuracy)
  - [3/6] Server launch & `/health` endpoint: PASS (HTTP 200, `model_loaded=true`, debug mode OFF, zero info disclosure)
  - [4/6] API English prediction (`/api/predict`): PASS (HTTP 200, valid prediction and explanation)
  - [5/6] API Language Safety (`/api/predict` Hindi text): PASS (HTTP 200, `unsupported_language`, exact message: `"Unable to assess: this model was trained on English news."`)
  - [6/6] Web Dashboard (`GET /`): PASS (HTTP 200, full responsive interface with Live News Feed)
- [x] News Feed Rate-Limit & Fallback Resolution:
  - Fixed refresh rate-limiting: when `/api/news-feed?refresh=true` arrives within the rate-limit window or if GDELT rate limits, returns last cached headlines with `"cached, retrieved at <time>"` and HTTP **200** (not an empty 429). Returns an error only if no cached data exists.
  - Thread-safe serialization: enforced a `threading.Lock()` and a 6.0-second minimum interval between real GDELT calls.
  - Client-side cooldown: Refresh button disables for 10 seconds post-click with an active countdown timer (`⏳ Wait (10s)...`), re-enabling at 0.
  - Secondary fallback providers: configured `GNEWS_API_KEY` and `NEWSDATA_API_KEY` fallbacks when GDELT is unavailable and cache is empty; otherwise displays honest "Live headlines unavailable" state with Retry (zero fake/placeholder headlines).
- [x] Production Safety & Cloud Configuration:
  - Confirmed Flask debug mode is controlled by `FLASK_DEBUG`, is **OFF** by default, and `FLASK_ENV` defaults to `production`.
  - Added `gunicorn>=22.0.0,<23.0.0` to `requirements.txt`.
  - Updated `render.yaml` to single worker with threads: `gunicorn -w 1 --threads 4 -b 0.0.0.0:$PORT src.app:app` to preserve in-memory cache and rate-limit locks per process.
  - Confirmed `src/app.py` exposes a Flask object named `app` (verified import path via `python -c "from src.app import app"`).
  - Explicitly noted in documentation that Render cloud deployment configuration is prepared but live remote deployment is not verified.
- [x] Complete Documentation Suite Updated:
  - `README.md` (complete project guide, quickstart, demo instructions, exact commands, 139 tests)
  - `docs/PROGRESS.md` (all 6 stages completed and verified)
  - `docs/security.md` (SSRF defenses, GDELT security, API key management, WSGI recommendations)
  - `docs/model_card.md` (held-out metrics, language scope, and limitations)
  - `docs/evaluation_report.md` (real test metrics: 98.55% accuracy, 0.0174 Brier score)
  - `docs/judge_qa.md` (9 detailed technical Q&As covering all stages)
  - `docs/presentation.md` (5-7 minute presentation outline)
  - `docs/report.md` (college & hackathon technical project report)
  - `docs/architecture.mmd` (complete Mermaid diagram across all application layers)
  - `render.yaml` (production build command and start command `gunicorn -w 1 --threads 4 -b 0.0.0.0:$PORT src.app:app`)
  - `scripts/demo_check.ps1` (6-step automated PowerShell verification script)
- [x] Browser visual verification: marked manual, untested (no screenshots claimed). Project is 100% complete, reproducible, and ready for review.

---

### Stage 7: Performance Optimization & Production Hardening (Completed & Verified)
- [x] **Measured Baseline First**:
  - Implemented `scripts/benchmark_baseline.py` running real 3-iteration benchmarks against local server.
  - Identified major bottleneck: Home page (`GET /`) and prediction (`POST /predict`) were synchronously executing live GDELT API queries over TLS (taking 12–14s per request).
- [x] **Optimized Homepage & Live News Feed**:
  - Home page renders immediately without blocking on external APIs.
  - Client-side asynchronous fetch via `fetchNewsFeedAsync()` in `static/js/main.js` populates headlines on `DOMContentLoaded`.
  - Configured provider timeouts to 5.0s per provider with a strict 10.0s total cap.
  - Added background daemon thread `warm_news_feed_cache()` at app boot to warm the headlines cache.
- [x] **Model Preloading & Boot Warm-up**:
  - Loaded pipeline model into memory at application startup (`_PRELOADED_PIPELINE`) compatible with `gunicorn --preload`.
  - Executed dummy warm-up prediction during startup so zero cold-start delay occurs on first request.
- [x] **Cleaned Web Request Import Path**:
  - Removed top-level `import pandas as pd`, `import numpy as np`, and `from sklearn.model_selection import ...` from `src/preprocessing.py`.
  - Lazy-imported pandas inside training-only functions (`load_raw_dataset`, `audit_and_deduplicate`, `split_dataset`).
  - Implemented standalone `math.isnan` check in `clean_text` with zero external dependencies.
  - `src.preprocessing` import time dropped from ~600ms to 50.9ms.
- [x] **In-Memory Caching for Metadata & Reports**:
  - Pre-cached evaluation reports (`_PERF_EVAL_DATA`, `_PERF_QUALITY_DATA`, `_PERF_LEAKAGE_DATA`) and model metadata in memory at startup, avoiding repeated disk reads per request.
- [x] **Reused Transformed Vectors in Prediction**:
  - Fitted pipeline cached feature names and model coefficients directly on pipeline instance.
  - Reused pre-transformed TF-IDF sparse matrix (`X_vec`) across both classifier inference and per-token explanation, avoiding duplicate vectorization.
- [x] **Gzip Compression & Static Asset Caching**:
  - Integrated `flask-compress` (`Compress(app)`).
  - Set `SEND_FILE_MAX_AGE_DEFAULT = 31536000` with explicit `Cache-Control: public, max-age=31536000, immutable` headers for `/static` files.
- [x] **Compact Model Artifact**:
  - Evaluated model artifact size: 1.12 MB (1,176,673 bytes) with 25,000 TF-IDF n-gram vocabulary.
  - Tested joblib compression (`compress=3`, 510 KB) and measured load times: uncompressed loads in 110ms, compressed takes 254ms. Retained uncompressed artifact for optimal load latency and memory footprint.
  - Un-ignored `!models/truthlens_model.joblib` in `.gitignore` for zero-friction cloud deployment.
- [x] **Split Requirements & Clean Virtualenv Validation**:
  - Created minimal `requirements.txt` for production deployment (omitting pandas, matplotlib, seaborn, pytest).
  - Created `requirements-dev.txt` for development and training (`-r requirements.txt`, `pandas>=2.2.0,<2.3.0`, `pytest>=8.0.0,<9.0.0`).
  - Verified clean installation of both files in an isolated virtual environment (`scratch_venv`).
- [x] **Updated Cloud Deployment Config**:
  - Configured `render.yaml` to use:
    `buildCommand: "pip install -r requirements.txt"`
    `startCommand: "gunicorn --preload -w 1 --threads 8 --timeout 180 -b 0.0.0.0:$PORT src.app:app"`
  - Updated production deployment documentation in `docs/security.md`.
- [x] **Comprehensive Verification**:
  - Pytest full suite: **139 passed, 0 failed** in **2.47s** (0 failures, 0 regressions).
  - Hindi safety message verified exact string: `"Unable to assess: this model was trained on English news."`.
  - Predictions unchanged for identical inputs (Reuters: 0.0972, Clickbait: 0.9784).
  - URL security, fact-check, live headlines, and history functionality fully validated.

### Performance Benchmark Comparison (Real Measured Timings)

| Metric / Endpoint | Baseline (Before) | Optimized (After) | Speedup / Improvement |
| :--- | :---: | :---: | :---: |
| **Python Import (`src.preprocessing`)** | ~600 ms | **50.9 ms** | **~12x faster** |
| **Python Import (`src.app`)** | 1,534.1 ms | 1,572.1 ms | Includes model preload & warm-up |
| **Model Load Time (`load_model()`)** | 111.1 ms (cold per worker) | **0.00 ms (preloaded)** / 133.8 ms cold | Preloaded once at boot |
| **GET `/` (Homepage render)** | **13,754.2 ms** | **3.2 - 36.6 ms** | **>400x faster** |
| **GET `/health` (Health check)** | 14.2 ms | **0.08 - 14.3 ms** | Instant in-memory health check |
| **POST `/predict` (English paragraph)** | **12,681.4 ms** | **19.7 ms** | **643x faster** |
| **POST `/api/predict` (API)** | ~250 ms | **1.31 ms** | **~190x faster** |
| **GET `/history`** | 22.80 ms | **8.10 - 18.11 ms** | Indexed B-Tree scan (`id DESC LIMIT 50`) |
| **GET `/performance`** | 40.11 ms | **2.65 - 33.51 ms** | Served from in-memory cache |
| **GET `/about`** | 26.28 ms | **4.08 - 20.56 ms** | Zero disk I/O, no model load |
| **GET `/api/news-feed`** | **9,374.29 ms** (9.37s) | **2.00 - 16.09 ms** | **~500x faster, non-blocking** |
| **Pytest Full Suite (`139 tests`)** | 15.38 s | **2.47 s** | **>6x faster test execution** |

---

### Stage 8: Render Concurrency & Non-Blocking News Feed Optimization (Completed & Verified)
- [x] **Identified Root Cause of Free-Tier Navigation Stalls**:
  - When `/api/news-feed` was called on an empty/cold cache, it previously spent up to 9,374 ms synchronously awaiting external GDELT and fallback HTTP responses inside the request thread while holding `_NEWS_FEED_LOCK`.
  - In single-worker / low-thread environments (like Render free tier), any user clicking "History", "Performance", or "About" while `/api/news-feed` was pending became queued behind that 9.4-second network request.
  - Furthermore, `base.html` previously loaded Chart.js from an external CDN on every page, and news feed event listeners executed on every page.
- [x] **Non-Blocking `/api/news-feed` Endpoint**:
  - `/api/news-feed` now serves cached headlines immediately (`only_cached=True`), returning in **2–16 ms**.
  - All external provider fetching is offloaded to a single background daemon thread (`start_background_feed_worker()`) started at startup.
  - If no cache is ready yet, returns an immediate `{ status: "loading" }` response (HTTP 200, < 1ms), and `main.js` automatically retries after 2.5s.
  - `_NEWS_FEED_LOCK` is never held during `requests.get()`, `time.sleep()`, or network calls; rate limits are checked without blocking.
- [x] **Page Isolation**:
  - Live news feed script and refresh handlers restricted strictly to the Home page (`if (feedContentArea)`).
  - External CDN Chart.js removed from `base.html` and isolated exclusively to `performance.html` scripts block.
- [x] **Ultra-Cheap Navigation Routes**:
  - `inject_global_context()` uses in-memory preloaded model state (`_PRELOADED_PIPELINE is not None`) instead of invoking `load_model()` per request.
  - `init_db()` runs once at boot; SQLite history table indexed on `(id DESC)` and `(timestamp DESC)`.
  - `/about` and `/performance` perform zero disk reads and zero model re-inspections.
- [x] **Gunicorn Concurrency Scaled**:
  - Raised worker threads to 8 in `render.yaml` (`gunicorn --preload -w 1 --threads 8 --timeout 180 -b 0.0.0.0:$PORT src.app:app`).
- [x] **Verification**:
  - `pytest -q`: **139 passed, 0 failed in 2.47s**.
  - `demo_check.ps1`: All 6 checks passed.
  - Hindi safety string: `"Unable to assess: this model was trained on English news."` verified.



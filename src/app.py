"""Flask web application for TruthLens AI.

Follows strict security guidelines:
- Flask-WTF CSRF protection enabled across form POST routes
- No secrets, internal filesystem paths, or stack traces exposed
- Parameterized SQLite queries for optional local history
- Secure error handling and rate-limiting safeguards
"""
import json
import logging
import os
import threading
import time
from pathlib import Path
from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    redirect,
    url_for,
    flash,
    abort,
    g,
)
from flask_wtf.csrf import CSRFProtect, CSRFError
from flask_compress import Compress

logger = logging.getLogger("truthlens")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

from src.config import (
    SECRET_KEY,
    FLASK_ENV,
    FLASK_DEBUG,
    FLASK_PORT,
    ENABLE_LOCAL_HISTORY,
    PRIMARY_MODEL_PATH,
    MODEL_METADATA_PATH,
    DATA_QUALITY_REPORT_PATH,
    EVALUATION_REPORT_PATH,
    LEAKAGE_AUDIT_PATH,
    STANDARD_DISCLAIMER,
)
from src.predict import predict_text, load_model
from src.news_feed import fetch_gdelt_news, warm_news_feed_cache, get_cached_news_feed
from src.factcheck import search_fact_checks
from src.history import (
    save_history_record,
    get_recent_history,
    delete_history_record,
    clear_all_history,
)


# Demonstration examples clearly marked as unverified demo text
DEMO_EXAMPLES = [
    {
        "id": "demo-wire",
        "title": "Reuters-Style Wire Dispatch",
        "badge": "Demonstration example—not fact-checked",
        "description": "Standard institutional news reporting with attribution and neutral syntax.",
        "text": (
            "The Senate Budget Committee held a bipartisan hearing on federal discretionary spending targets "
            "for the upcoming fiscal year. Lawmakers from both parties discussed allocating infrastructure grants "
            "to bridge repair initiatives and public water system upgrades across thirty states. Agency officials "
            "emphasized that formal budget appropriations will require further legislative compromise before the deadline."
        ),
    },
    {
        "id": "demo-clickbait",
        "title": "Sensational Viral Headline & Claim",
        "badge": "Demonstration example—not fact-checked",
        "description": "Emotionally provocative clickbait with dramatic absolutes and urgent calls to share.",
        "text": (
            "SHOCKING DISCOVERY EXPOSED! You won't believe what secret documents reveal about corrupt government elites! "
            "Mainstream media is terrified to report the hidden truth! Share this before it gets deleted from the internet forever! "
            "This 100% proven revelation will blow your mind and destroys all their lies once and for all!"
        ),
    },
    {
        "id": "demo-ambiguous",
        "title": "Short Conversational Claim",
        "badge": "Demonstration example—not fact-checked",
        "description": "Brief conversational statement that triggers input-quality and uncertainty safeguards.",
        "text": "They said the new economy policy might change interest rates next week.",
    },
]

app = Flask(
    __name__,
    template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
    static_folder=str(Path(__file__).resolve().parent.parent / "static"),
)

app.config["SECRET_KEY"] = SECRET_KEY
app.config["WTF_CSRF_TIME_LIMIT"] = 3600
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000

# Enable Gzip/Brotli Compression
Compress(app)

# Enable CSRF Protection
csrf = CSRFProtect(app)


# ---------------------------------------------------------------------------
# Startup Preloading & In-Memory Caching (Gunicorn --preload compatible)
# ---------------------------------------------------------------------------
# 1. Load model once at startup and execute warm-up prediction
_PRELOADED_PIPELINE, _PRELOADED_METADATA = load_model()
if _PRELOADED_PIPELINE is not None:
    try:
        predict_text("Preload diagnostic warm-up prediction at boot.", search_factchecks=False)
        logger.info("[PERF] Boot model warm-up prediction completed successfully.")
    except Exception as _e:
        logger.warning("[PERF] Warm-up prediction notice: %s", _e)

# 2. Cache immutable evaluation artifacts in memory at startup
_PERF_EVAL_DATA = None
_PERF_QUALITY_DATA = None
_PERF_LEAKAGE_DATA = None

if EVALUATION_REPORT_PATH.exists():
    try:
        with open(EVALUATION_REPORT_PATH, "r", encoding="utf-8") as _f:
            _PERF_EVAL_DATA = json.load(_f)
    except Exception:
        pass

if DATA_QUALITY_REPORT_PATH.exists():
    try:
        with open(DATA_QUALITY_REPORT_PATH, "r", encoding="utf-8") as _f:
            _PERF_QUALITY_DATA = json.load(_f)
    except Exception:
        pass

if LEAKAGE_AUDIT_PATH.exists():
    try:
        with open(LEAKAGE_AUDIT_PATH, "r", encoding="utf-8") as _f:
            _PERF_LEAKAGE_DATA = json.load(_f)
    except Exception:
        pass

# 3. Warm feed cache in background thread without delaying server boot
threading.Thread(target=warm_news_feed_cache, daemon=True, name="feed-cache-warmer").start()


@app.before_request
def _start_request_timer():
    g._request_start_time = time.perf_counter()


@app.after_request
def _log_request_time(response):
    if hasattr(g, "_request_start_time"):
        duration_ms = (time.perf_counter() - g._request_start_time) * 1000.0
        logger.info("[PERF] %s %s -> %s in %.2fms", request.method, request.path, response.status_code, duration_ms)

    if request.path.startswith("/static/"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"

    return response


@app.context_processor
def inject_global_context():
    """Injects common context into all templates."""
    pipeline, metadata = load_model()
    model_loaded = pipeline is not None
    return {
        "model_loaded": model_loaded,
        "model_metadata": metadata or {},
        "enable_local_history": ENABLE_LOCAL_HISTORY,
        "standard_disclaimer": STANDARD_DISCLAIMER,
    }


@app.route("/", methods=["GET"])
def index():
    """Main dashboard page — renders immediately from cache or background warming."""
    feed = fetch_gdelt_news(only_cached=True)
    return render_template(
        "index.html",
        demo_examples=DEMO_EXAMPLES,
        news_feed=feed,
        result=None,
        submitted_text="",
        submitted_url="",
        active_tab="url",
    )


@app.route("/predict", methods=["POST"])
def handle_predict():
    """Processes user text or URL submission and returns analysis view."""
    input_mode = request.form.get("input_mode", "text")
    submitted_url = request.form.get("article_url", "").strip()
    submitted_text = request.form.get("news_text", "").strip()
    feed = fetch_gdelt_news(only_cached=True)

    if input_mode == "url" and submitted_url:
        from src.predict import predict_url
        result = predict_url(submitted_url)
    elif submitted_text:
        result = predict_text(submitted_text)
    elif submitted_url:
        from src.predict import predict_url
        result = predict_url(submitted_url)
    else:
        flash("Please enter a valid URL, headline, or article text to analyze.", "warning")
        return redirect(url_for("index"))

    # Save to local history if enabled
    if result.get("status") == "success" and ENABLE_LOCAL_HISTORY:
        save_history_record(
            predicted_label=result["predicted_label"],
            predicted_class=result["predicted_class"],
            decision_score=result.get("decision_score"),
            is_uncertain=result.get("is_uncertain", False),
            text=submitted_url if input_mode == "url" else submitted_text,
            model_version=result.get("model_version", "1.0.0"),
        )

    return render_template(
        "index.html",
        demo_examples=DEMO_EXAMPLES,
        news_feed=feed,
        result=result,
        submitted_text=submitted_text,
        submitted_url=submitted_url,
        active_tab=input_mode,
    )


@app.route("/api/news-feed", methods=["GET"])
def api_news_feed():
    """API endpoint to fetch or refresh live GDELT news feed."""
    force_refresh = request.args.get("refresh", "false").lower() in ("true", "1")
    feed = fetch_gdelt_news(force_refresh=force_refresh)
    if feed.get("status") == "success":
        status_code = 200
    elif "rate limit" in str(feed.get("message", "")).lower() or "rate limit" in str(feed.get("notice", "")).lower():
        status_code = 429
    else:
        status_code = 503
    return jsonify(feed), status_code


@app.route("/api/fact-check", methods=["GET"])
def api_fact_check():
    """API endpoint to search Google Fact Check Tools database."""
    query = request.args.get("query", "").strip()
    if not query:
        return jsonify({"status": "no_matches", "message": "Query parameter 'query' is required.", "reviews": []}), 400

    result = search_fact_checks(query)
    status_code = 200 if result.get("status") in ("success", "no_matches", "missing_key") else 503
    return jsonify(result), status_code




@app.route("/api/predict", methods=["POST"])
@csrf.exempt
def api_predict():
    """JSON API endpoint for text or URL prediction."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"status": "error", "message": "JSON body with 'text' or 'url' field required."}), 400

    if "url" in data and data["url"]:
        from src.predict import predict_url
        result = predict_url(str(data["url"]).strip())
    elif "text" in data and data["text"]:
        result = predict_text(str(data["text"]).strip())
    else:
        return jsonify({"status": "error", "message": "JSON body with 'text' or 'url' field required."}), 400

    return jsonify(result), (200 if result.get("status") in ("success", "unsupported_language", "model_missing", "extraction_failed") else 400)


@app.route("/about", methods=["GET"])
def about():
    """Methodology, dataset provenance, and limitations page."""
    return render_template("about.html")


@app.route("/performance", methods=["GET"])
def performance():
    """Genuine evaluation results and model audit charts — served from in-memory cache."""
    return render_template(
        "performance.html",
        evaluation=_PERF_EVAL_DATA,
        data_quality=_PERF_QUALITY_DATA,
        leakage=_PERF_LEAKAGE_DATA,
    )


@app.route("/history", methods=["GET"])
def history():
    """Local analysis history page."""
    if not ENABLE_LOCAL_HISTORY:
        flash("Local history is currently disabled in application configuration.", "info")
        return redirect(url_for("index"))

    records = get_recent_history(limit=50)
    return render_template("history.html", history_records=records)


@app.route("/history/<int:record_id>/delete", methods=["POST"])
def delete_history(record_id: int):
    """Deletes a single history entry via POST and CSRF protection."""
    if ENABLE_LOCAL_HISTORY:
        delete_history_record(record_id)
        flash("History entry removed.", "info")
    return redirect(url_for("history"))


@app.route("/history/clear", methods=["POST"])
def clear_history():
    """Clears all history entries via POST and CSRF protection."""
    if ENABLE_LOCAL_HISTORY:
        clear_all_history()
        flash("All local analysis history cleared.", "info")
    return redirect(url_for("history"))


@app.route("/health", methods=["GET"])
def health():
    """Safe health check endpoint without exposing sensitive internal data."""
    pipeline, metadata = load_model()
    is_ready = pipeline is not None

    payload = {
        "status": "healthy",
        "model_loaded": is_ready,
        "model_version": metadata.get("model_version", "none") if metadata else "none",
        "model_type": metadata.get("model_name", "unloaded") if metadata else "unloaded",
        "timestamp_utc": metadata.get("timestamp_utc", "unknown") if metadata else "unknown",
        "environment": "production" if FLASK_ENV == "production" else "development",
    }
    return jsonify(payload), (200 if is_ready else 503)


@app.errorhandler(404)
def not_found_error(error):
    return render_template("404.html"), 404


@app.errorhandler(500)
def internal_error(error):
    return render_template("500.html"), 500


@app.errorhandler(CSRFError)
def handle_csrf_error(e):
    return render_template("400.html", message=f"CSRF authentication error: {e.description}"), 400


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=FLASK_PORT, debug=FLASK_DEBUG)

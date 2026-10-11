"""Inference and text assessment engine for TruthLens AI.

Enforces strict input validation, out-of-distribution heuristics, cautious labeling,
and separation of machine-learning classification from rules-based writing signals.
"""
import json
import re
from pathlib import Path
from typing import Any, TypedDict
import joblib
from sklearn.pipeline import Pipeline

from src.config import (
    PRIMARY_MODEL_PATH,
    MODEL_METADATA_PATH,
    MIN_INPUT_LENGTH,
    MAX_INPUT_LENGTH,
    MIN_WORD_COUNT,
    LABEL_RELIABLE,
    LABEL_MISLEADING,
    LABEL_NAMES,
    LABEL_EXPLANATIONS,
    STANDARD_DISCLAIMER,
)
from src.preprocessing import clean_text
from src.explain import explain_text_prediction, ExplanationResult
from src.clickbait import analyze_writing_style, ClickbaitAnalysis
from src.factcheck import search_fact_checks, extract_factcheck_query, FactCheckResult
from src.language import detect_language, UNSUPPORTED_LANGUAGE_MESSAGE

# Cache loaded pipeline and metadata in-memory
_MODEL_PIPELINE: Pipeline | None = None
_MODEL_METADATA: dict[str, Any] | None = None

# Common English stopwords for language suitability heuristic
COMMON_ENGLISH_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
}

VERIFICATION_CHECKLIST = [
    {
        "step": 1,
        "title": "Check Multiple Independent Sources",
        "detail": "Verify if established national or international news organizations independently report the event.",
    },
    {
        "step": 2,
        "title": "Examine Author & Publisher Credentials",
        "detail": "Check author byline, editorial standards, masthead, and domain registration date.",
    },
    {
        "step": 3,
        "title": "Inspect Primary Sources & Documents",
        "detail": "Follow cited links, quotes, and research papers back to original official records or press releases.",
    },
    {
        "step": 4,
        "title": "Check Independent Fact-Checking Databases",
        "detail": "Search trusted fact-checking platforms such as Snopes, AP Fact Check, FactCheck.org, or Reuters Fact Check.",
    },
    {
        "step": 5,
        "title": "Reverse-Search Media & Images",
        "detail": "Perform reverse-image searches to detect out-of-context or repurposed historical media.",
    },
]


def load_model(
    model_path: Path | str = PRIMARY_MODEL_PATH,
    metadata_path: Path | str = MODEL_METADATA_PATH,
    force_reload: bool = False,
) -> tuple[Pipeline | None, dict[str, Any] | None]:
    """Loads and caches the persisted scikit-learn model pipeline and metadata."""
    global _MODEL_PIPELINE, _MODEL_METADATA

    if not force_reload and _MODEL_PIPELINE is not None:
        return _MODEL_PIPELINE, _MODEL_METADATA

    m_path = Path(model_path)
    meta_path = Path(metadata_path)

    if not m_path.exists():
        _MODEL_PIPELINE = None
        _MODEL_METADATA = None
        return None, None

    try:
        pipeline = joblib.load(m_path)
        metadata = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        _MODEL_PIPELINE = pipeline
        _MODEL_METADATA = metadata
        return _MODEL_PIPELINE, _MODEL_METADATA
    except Exception:
        _MODEL_PIPELINE = None
        _MODEL_METADATA = None
        return None, None


def evaluate_language_suitability(text: str) -> tuple[bool, str]:
    """Heuristic check on English word coverage and character composition."""
    tokens = [w.lower() for w in re.findall(r"\b[a-zA-Z]{2,}\b", text)]
    if len(tokens) < 4:
        return True, "Short text; language heuristic inconclusive."

    english_match_count = sum(1 for w in tokens if w in COMMON_ENGLISH_WORDS)
    ratio = english_match_count / len(tokens)

    if ratio < 0.10:
        return False, (
            "Language heuristic note: The text exhibits low English word coverage (<10%). "
            "Because TruthLens AI was trained exclusively on English-language articles, "
            "predictions may be inaccurate."
        )

    return True, "Passed language heuristic."


def compute_vocabulary_overlap(pipeline: Pipeline, cleaned_text: str) -> tuple[float, str]:
    """Computes fraction of unique input tokens present in the trained TF-IDF vocabulary."""
    try:
        vectorizer = pipeline.named_steps.get("tfidf") or pipeline.named_steps.get("vectorizer")
        if vectorizer is None or not hasattr(vectorizer, "vocabulary_"):
            return 1.0, "Vocabulary check unavailable."

        vocab = vectorizer.vocabulary_
        words = set(re.findall(r"\b\w+\b", cleaned_text.lower()))
        if not words:
            return 0.0, "No valid word tokens found."

        overlap_count = sum(1 for w in words if w in vocab)
        ratio = overlap_count / len(words)

        if ratio < 0.20:
            warning = (
                f"Input novelty warning: Only {ratio*100:.1f}% of unique words in this text "
                "appear in the model's training vocabulary. The classifier has limited familiarity "
                "with this vocabulary domain."
            )
        else:
            warning = f"Vocabulary overlap is {ratio*100:.1f}%."

        return round(ratio, 4), warning
    except Exception:
        return 1.0, "Vocabulary check failed."


def predict_text(text: str, search_factchecks: bool = True) -> dict[str, Any]:
    """Primary assessment function for submitted text.

    Returns structured analysis containing:
    1. Machine learning classification
    2. Transparent token-based explanation
    3. Separate rules-based writing signals
    4. Uncertainty and input quality warnings
    5. Independent verification checklist
    6. External related fact-checks (Google Fact Check Tools API)
    """
    # 1. Server-side validation
    if not text or not text.strip():
        return {
            "status": "error",
            "error_type": "empty_input",
            "message": "Input text is empty. Please enter a headline, article excerpt, or claim to analyze.",
        }

    # 2. Language safety check (TruthLens AI model was trained on English news)
    lang_check = detect_language(text)
    if not lang_check["is_english"]:
        fact_checks = None
        if search_factchecks:
            fc_query = extract_factcheck_query(text)
            fact_checks = search_fact_checks(fc_query)

        return {
            "status": "unsupported_language",
            "message": UNSUPPORTED_LANGUAGE_MESSAGE,
            "detected_language": lang_check.get("detected_language", "Non-English"),
            "language_reason": lang_check.get("reason", ""),
            "predicted_class": -1,
            "predicted_label": None,
            "verdict": None,
            "confidence_score": None,
            "decision_score": None,
            "prob_reliable": None,
            "prob_misleading": None,
            "clickbait_analysis": None,
            "explanation": None,
            "is_uncertain": True,
            "notice": "This is an automated language constraint, not a verdict about the claim or article veracity.",
            "verification_checklist": VERIFICATION_CHECKLIST,
            "fact_checks": fact_checks,
            "standard_disclaimer": STANDARD_DISCLAIMER,
        }

    raw_length = len(text)
    if raw_length > MAX_INPUT_LENGTH:
        text = text[:MAX_INPUT_LENGTH]
        length_warning = f"Input exceeded {MAX_INPUT_LENGTH} characters and was truncated for analysis."
    else:
        length_warning = None

    words = re.findall(r"\b\w+\b", text)
    word_count = len(words)

    quality_warnings: list[str] = []
    if length_warning:
        quality_warnings.append(length_warning)

    if raw_length < MIN_INPUT_LENGTH or word_count < MIN_WORD_COUNT:
        quality_warnings.append(
            f"Input is very short ({raw_length} characters, {word_count} words). "
            "NLP classifiers are less reliable on extremely brief snippets."
        )

    # Language heuristic check
    lang_ok, lang_note = evaluate_language_suitability(text)
    if not lang_ok:
        quality_warnings.append(lang_note)

    # 3. Rules-based writing style analysis (always computed independently)
    clickbait_result = analyze_writing_style(text)

    # External fact check search (if enabled)
    fact_checks = None
    if search_factchecks:
        fc_query = extract_factcheck_query(text)
        fact_checks = search_fact_checks(fc_query)

    # 3. Model pipeline loading
    pipeline, metadata = load_model()
    if pipeline is None:
        return {
            "status": "model_missing",
            "message": (
                "No trained model artifact was found at 'models/truthlens_model.joblib'. "
                "To train the model on the validated dataset, run: 'python -m src.train' in your terminal."
            ),
            "input_preview": text[:200] + ("..." if len(text) > 200 else ""),
            "clickbait_analysis": clickbait_result,
            "quality_warnings": quality_warnings,
            "verification_checklist": VERIFICATION_CHECKLIST,
            "fact_checks": fact_checks,
            "standard_disclaimer": STANDARD_DISCLAIMER,
        }

    # 4. Preprocessing & Out-of-Distribution check
    cleaned = clean_text(text, remove_datelines=True)
    vocab_ratio, vocab_warning = compute_vocabulary_overlap(pipeline, cleaned)
    if vocab_ratio < 0.20:
        quality_warnings.append(vocab_warning)

    # 5. Model Inference
    try:
        classifier = pipeline.named_steps.get("clf") or pipeline.named_steps.get("classifier")

        # Probability assessment
        calibrated = metadata.get("calibration", {}).get("is_calibrated", False) if metadata else False
        score_label = "Calibrated probability" if calibrated else "Model decision score (uncalibrated)"

        prob_misleading = 0.5
        prob_reliable = 0.5
        score_value = 0.5

        if hasattr(pipeline, "predict_proba"):
            probs = pipeline.predict_proba([cleaned])[0]
            # probs[0] is reliable, probs[1] is misleading
            prob_reliable = float(probs[LABEL_RELIABLE])
            prob_misleading = float(probs[LABEL_MISLEADING])
            score_value = prob_misleading
        elif hasattr(pipeline, "decision_function"):
            df_val = float(pipeline.decision_function([cleaned])[0])
            # Sigmoid approximation for uncalibrated decision score
            import numpy as np
            score_value = float(1 / (1 + np.exp(-df_val)))
            prob_misleading = score_value
            prob_reliable = 1.0 - score_value
            score_label = "SVM decision score (uncalibrated)"

        # Class determination with uncertainty band
        # If probability is within 0.45 to 0.55, or vocabulary overlap is extremely low (< 0.15) on short text
        is_uncertain = False
        uncertain_reason = ""

        if 0.44 <= score_value <= 0.56:
            is_uncertain = True
            uncertain_reason = "Model decision score is close to the 50% boundary, indicating low statistical margin."
        elif vocab_ratio < 0.15 and word_count < 15:
            is_uncertain = True
            uncertain_reason = "Input has minimal vocabulary overlap with training data and is very brief."

        if is_uncertain:
            predicted_class = -1
            predicted_label = "Uncertain / Unable to assess"
            class_explanation = f"Classification deferred: {uncertain_reason}"
        elif score_value >= 0.50:
            predicted_class = LABEL_MISLEADING
            predicted_label = LABEL_NAMES[LABEL_MISLEADING]
            class_explanation = LABEL_EXPLANATIONS[LABEL_MISLEADING]
        else:
            predicted_class = LABEL_RELIABLE
            predicted_label = LABEL_NAMES[LABEL_RELIABLE]
            class_explanation = LABEL_EXPLANATIONS[LABEL_RELIABLE]

        # 6. Model Explanations (TF-IDF x linear coefficients)
        explanation = explain_text_prediction(pipeline, cleaned, top_n=6)

        return {
            "status": "success",
            "predicted_class": predicted_class,
            "predicted_label": predicted_label,
            "class_explanation": class_explanation,
            "is_uncertain": is_uncertain,
            "uncertain_reason": uncertain_reason if is_uncertain else None,
            "decision_score": round(score_value, 4),
            "decision_score_percentage": round(score_value * 100, 1),
            "score_label": score_label,
            "calibrated": calibrated,
            "prob_reliable": round(prob_reliable, 4),
            "prob_misleading": round(prob_misleading, 4),
            "model_version": metadata.get("model_version", "1.0.0") if metadata else "1.0.0",
            "model_name": metadata.get("model_name", "TF-IDF + LogisticRegression") if metadata else "TF-IDF + LogisticRegression",
            "explanation": explanation,
            "clickbait_analysis": clickbait_result,
            "quality_warnings": quality_warnings,
            "input_stats": {
                "character_count": raw_length,
                "word_count": word_count,
                "vocab_overlap_ratio": vocab_ratio,
            },
            "fact_checks": fact_checks,
            "verification_checklist": VERIFICATION_CHECKLIST,
            "standard_disclaimer": STANDARD_DISCLAIMER,
        }

    except Exception as e:
        return {
            "status": "error",
            "error_type": "inference_failure",
            "message": f"Inference processing failed: {str(e)}",
            "clickbait_analysis": clickbait_result,
            "quality_warnings": quality_warnings,
            "fact_checks": fact_checks,
            "standard_disclaimer": STANDARD_DISCLAIMER,
        }


def predict_url(url: str) -> dict[str, Any]:
    """Fetches article text from a URL safely and runs classification & explanations.

    Returns structured analysis containing URL metadata, extracted title, domain,
    fact-check evidence, and prediction results.
    """
    from src.url_fetcher import fetch_and_extract_url

    extraction = fetch_and_extract_url(url)
    if extraction["status"] != "success":
        return {
            "status": "extraction_failed",
            "error_type": extraction["status"],
            "message": extraction["message"],
            "url": extraction["url"],
            "source_domain": extraction["source_domain"],
            "standard_disclaimer": STANDARD_DISCLAIMER,
            "quality_warnings": [extraction["message"]],
            "verification_checklist": VERIFICATION_CHECKLIST,
        }

    # Run ML & clickbait prediction on extracted text (without duplicate fact check search)
    result = predict_text(extraction["extracted_text"], search_factchecks=False)

    # Search fact checks using the extracted title (or extracted text if title missing)
    fc_query = extract_factcheck_query(
        extraction["extracted_text"], title=extraction["extracted_title"]
    )
    result["fact_checks"] = search_fact_checks(fc_query)

    # Attach URL metadata to result
    result["url_metadata"] = {
        "url": extraction["url"],
        "source_domain": extraction["source_domain"],
        "extracted_title": extraction["extracted_title"],
        "extracted_excerpt": extraction["extracted_excerpt"],
        "publication_date": extraction["publication_date"],
        "fetch_notice": extraction["fetch_notice"],
    }

    return result

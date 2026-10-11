"""Unit tests for machine learning pipeline, explanation, and prediction structures.

Uses ISOLATED synthetic fixtures only.
"""
from pathlib import Path
import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from src.explain import explain_text_prediction, get_feature_names_and_coefs
from src.predict import (
    predict_text,
    evaluate_language_suitability,
    compute_vocabulary_overlap,
    load_model,
)
from src.config import LABEL_RELIABLE, LABEL_MISLEADING, LABEL_NAMES
from tests.fixtures import get_synthetic_raw_data


def test_synthetic_pipeline_training_and_serialization(tmp_path: Path):
    fake_df, true_df = get_synthetic_raw_data()
    fake_df["label"] = LABEL_MISLEADING
    true_df["label"] = LABEL_RELIABLE
    df = pd.concat([fake_df, true_df], ignore_index=True)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(min_df=1)),
        ("clf", LogisticRegression(random_state=42)),
    ])
    pipeline.fit(df["text"], df["label"])

    model_file = tmp_path / "test_model.joblib"
    joblib.dump(pipeline, model_file)
    assert model_file.exists()

    loaded = joblib.load(model_file)
    names, coefs, intercept = get_feature_names_and_coefs(loaded)
    assert len(names) > 0
    assert len(coefs) == len(names)


def test_explanation_token_contributions():
    fake_df, true_df = get_synthetic_raw_data()
    fake_df["label"] = LABEL_MISLEADING
    true_df["label"] = LABEL_RELIABLE
    df = pd.concat([fake_df, true_df], ignore_index=True)

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(min_df=1)),
        ("clf", LogisticRegression(random_state=42)),
    ])
    pipeline.fit(df["text"], df["label"])

    # Test explanation on text
    sample = "Secret alien plot uncovered by rogue scientist in Washington"
    explanation = explain_text_prediction(pipeline, sample, top_n=5)

    assert explanation["available"] is True
    assert "TF-IDF" in explanation["explanation_method"]
    assert "Token contributions describe" in explanation["disclaimer"]
    assert len(explanation["top_misleading_tokens"]) > 0 or len(explanation["top_reliable_tokens"]) > 0


def test_language_suitability_heuristic():
    english_sample = "The prime minister met with cabinet members to discuss economic trade agreements."
    ok, note = evaluate_language_suitability(english_sample)
    assert ok is True

    gibberish_or_non_english = "1234567 890123 456789 0123456"
    ok_g, note_g = evaluate_language_suitability(gibberish_or_non_english)
    # Few or no english words
    assert "heuristic" in note_g.lower()


def test_missing_model_behavior(tmp_path: Path):
    # Call predict_text when model file is missing
    non_existent_model = tmp_path / "absent.joblib"
    non_existent_meta = tmp_path / "absent.json"
    p, m = load_model(non_existent_model, non_existent_meta, force_reload=True)
    assert p is None
    assert m is None


def test_input_validation_empty_and_short():
    empty_res = predict_text("")
    assert empty_res["status"] == "error"
    assert empty_res["error_type"] == "empty_input"

    whitespace_res = predict_text("     \n\t   ")
    assert whitespace_res["status"] == "error"

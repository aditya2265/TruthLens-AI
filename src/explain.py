"""Model explanation module for TruthLens AI.

Extracts genuine per-token feature contributions (TF-IDF value * linear coefficient)
from the fitted scikit-learn Pipeline. Never fabricates rationales.
"""
from typing import Any, TypedDict
import numpy as np
from sklearn.pipeline import Pipeline


class TokenContribution(TypedDict):
    token: str
    contribution: float
    direction: str  # "misleading" or "reliable"
    weight_abs: float


class ExplanationResult(TypedDict):
    available: bool
    explanation_method: str
    disclaimer: str
    intercept: float
    top_misleading_tokens: list[TokenContribution]
    top_reliable_tokens: list[TokenContribution]
    total_active_features: int
    note: str


EXPLANATION_DISCLAIMER = (
    "Token contributions describe how the model weighted specific terms during classification, "
    "based on patterns in its training data. They explain the model's internal decision, "
    "NOT whether the claim is factually true or false. A highlighted word does not prove an article is false."
)


def get_feature_names_and_coefs(pipeline: Pipeline) -> tuple[np.ndarray, np.ndarray, float]:
    """Extracts vocabulary feature names and model coefficients from a fitted pipeline.
    Caches decomposition on the pipeline instance for zero-cost repeated lookups."""
    cached = getattr(pipeline, "_cached_feature_names_and_coefs", None)
    if cached is not None:
        return cached

    vectorizer = pipeline.named_steps.get("tfidf") or pipeline.named_steps.get("vectorizer")
    classifier = pipeline.named_steps.get("clf") or pipeline.named_steps.get("classifier")

    if vectorizer is None or classifier is None:
        raise ValueError("Pipeline must contain 'tfidf' and 'clf' (or 'classifier') steps.")

    feature_names = np.array(vectorizer.get_feature_names_out())

    # Handle binary LogisticRegression / LinearSVC coefficients
    if hasattr(classifier, "coef_"):
        coefs = classifier.coef_[0]
        intercept = float(classifier.intercept_[0]) if hasattr(classifier, "intercept_") else 0.0
    elif hasattr(classifier, "calibrated_classifiers_"):
        # For CalibratedClassifierCV
        base_clf = classifier.calibrated_classifiers_[0].estimator
        if hasattr(base_clf, "coef_"):
            coefs = base_clf.coef_[0]
            intercept = float(base_clf.intercept_[0]) if hasattr(base_clf, "intercept_") else 0.0
        else:
            raise ValueError("Underlying calibrated classifier does not expose linear coefficients.")
    else:
        raise ValueError("Classifier does not expose linear coefficients.")

    result = (feature_names, coefs, intercept)
    try:
        pipeline._cached_feature_names_and_coefs = result
    except Exception:
        pass
    return result


def explain_text_prediction(
    pipeline: Pipeline,
    cleaned_text: str,
    top_n: int = 8,
    X_vec: Any = None,
) -> ExplanationResult:
    """Computes exact per-token feature contributions for a single input text.

    Contribution = tfidf_value * model_coefficient.
    Positive values push toward label 1 (Misleading-style).
    Negative values push toward label 0 (Reliable-style).
    """
    if not cleaned_text or not cleaned_text.strip():
        return {
            "available": False,
            "explanation_method": "TF-IDF x Linear Coefficient Decomposition",
            "disclaimer": EXPLANATION_DISCLAIMER,
            "intercept": 0.0,
            "top_misleading_tokens": [],
            "top_reliable_tokens": [],
            "total_active_features": 0,
            "note": "Input text was empty. No explanation could be computed.",
        }

    try:
        vectorizer = pipeline.named_steps.get("tfidf") or pipeline.named_steps.get("vectorizer")
        feature_names, coefs, intercept = get_feature_names_and_coefs(pipeline)

        # Transform single input text to sparse TF-IDF row if not already provided
        if X_vec is None:
            X_vec = vectorizer.transform([cleaned_text])
        nonzero_indices = X_vec.indices
        nonzero_values = X_vec.data

        if len(nonzero_indices) == 0:
            return {
                "available": False,
                "explanation_method": "TF-IDF x Linear Coefficient Decomposition",
                "disclaimer": EXPLANATION_DISCLAIMER,
                "intercept": intercept,
                "top_misleading_tokens": [],
                "top_reliable_tokens": [],
                "total_active_features": 0,
                "note": (
                    "None of the words in the submitted text match the model's training vocabulary. "
                    "The model relied exclusively on its base intercept/prior distribution."
                ),
            }

        # Calculate contributions
        contributions: list[tuple[str, float]] = []
        for idx, tfidf_val in zip(nonzero_indices, nonzero_values):
            feat_name = str(feature_names[idx])
            feat_coef = float(coefs[idx])
            contrib = float(tfidf_val * feat_coef)
            contributions.append((feat_name, contrib))

        # Sort into misleading (positive) and reliable (negative)
        misleading_sorted = sorted([c for c in contributions if c[1] > 0], key=lambda x: x[1], reverse=True)
        reliable_sorted = sorted([c for c in contributions if c[1] < 0], key=lambda x: x[1])

        top_misleading: list[TokenContribution] = [
            {
                "token": term,
                "contribution": round(val, 4),
                "direction": "misleading",
                "weight_abs": round(abs(val), 4),
            }
            for term, val in misleading_sorted[:top_n]
        ]

        top_reliable: list[TokenContribution] = [
            {
                "token": term,
                "contribution": round(val, 4),
                "direction": "reliable",
                "weight_abs": round(abs(val), 4),
            }
            for term, val in reliable_sorted[:top_n]
        ]

        return {
            "available": True,
            "explanation_method": "TF-IDF x Linear Coefficient Decomposition",
            "disclaimer": EXPLANATION_DISCLAIMER,
            "intercept": round(intercept, 4),
            "top_misleading_tokens": top_misleading,
            "top_reliable_tokens": top_reliable,
            "total_active_features": len(nonzero_indices),
            "note": (
                f"Computed contributions across {len(nonzero_indices)} matching vocabulary features. "
                "Terms with positive contributions elevated the misleading-style score; terms with "
                "negative contributions elevated the reliable-style score."
            ),
        }

    except Exception as e:
        return {
            "available": False,
            "explanation_method": "TF-IDF x Linear Coefficient Decomposition",
            "disclaimer": EXPLANATION_DISCLAIMER,
            "intercept": 0.0,
            "top_misleading_tokens": [],
            "top_reliable_tokens": [],
            "total_active_features": 0,
            "note": f"Explanation unavailable: {str(e)}",
        }


def extract_global_top_coefficients(pipeline: Pipeline, top_n: int = 30) -> dict[str, Any]:
    """Extracts highest positive and highest negative global model coefficients.

    Used strictly for global model audit and the performance page.
    """
    feature_names, coefs, intercept = get_feature_names_and_coefs(pipeline)

    sorted_indices = np.argsort(coefs)
    top_negative_indices = sorted_indices[:top_n]
    top_positive_indices = sorted_indices[-top_n:][::-1]

    top_reliable = [
        {"token": str(feature_names[i]), "coefficient": round(float(coefs[i]), 4)}
        for i in top_negative_indices
    ]
    top_misleading = [
        {"token": str(feature_names[i]), "coefficient": round(float(coefs[i]), 4)}
        for i in top_positive_indices
    ]

    return {
        "label": "Global model information—not a per-article explanation",
        "intercept": round(intercept, 4),
        "total_features": len(feature_names),
        "top_misleading_features": top_misleading,
        "top_reliable_features": top_reliable,
    }

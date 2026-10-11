"""Evaluation CLI and reporting script for TruthLens AI.

Runnable as: python -m src.evaluate
Inspects the persisted model and held-out test split, prints formatted metrics,
and updates the evaluation artifacts.
"""
import json
import sys
from pathlib import Path

import joblib
import pandas as pd

from src.config import (
    PRIMARY_MODEL_PATH,
    MODEL_METADATA_PATH,
    TEST_DATA_PATH,
    EVALUATION_REPORT_PATH,
    EVALUATION_MD_PATH,
    LABEL_RELIABLE,
    LABEL_MISLEADING,
)
from src.train import compute_metrics


def run_evaluation() -> None:
    """Evaluates the persisted model on the saved held-out test split."""
    print("=" * 65)
    print("TruthLens AI — Model Evaluation Inspection")
    print("=" * 65)

    if not PRIMARY_MODEL_PATH.exists():
        print(f"[!] Error: Model artifact not found at: {PRIMARY_MODEL_PATH}")
        print("    Please train the model first by running: python -m src.train")
        sys.exit(1)

    if not TEST_DATA_PATH.exists():
        print(f"[!] Error: Held-out test split not found at: {TEST_DATA_PATH}")
        print("    Please prepare data and train first: python -m src.train")
        sys.exit(1)

    print(f"Loading model pipeline from: {PRIMARY_MODEL_PATH}")
    pipeline = joblib.load(PRIMARY_MODEL_PATH)

    print(f"Loading held-out test data from: {TEST_DATA_PATH}")
    test_df = pd.read_csv(TEST_DATA_PATH)
    test_n = len(test_df)
    print(f"Evaluating on held-out test split (n = {test_n})...")

    y_true = test_df["label"].values
    y_pred = pipeline.predict(test_df["cleaned_text"])
    y_prob = None
    if hasattr(pipeline, "predict_proba"):
        y_prob = pipeline.predict_proba(test_df["cleaned_text"])[:, LABEL_MISLEADING]

    metrics = compute_metrics(y_true, y_pred, y_prob)

    # Load existing metadata if available
    metadata = {}
    if MODEL_METADATA_PATH.exists():
        with open(MODEL_METADATA_PATH, "r", encoding="utf-8") as f:
            metadata = json.load(f)

    print("\n--- Genuine Evaluation Results ---")
    print(f"Dataset Split: Cleaned Held-Out Test Set (n = {test_n})")
    print(f"Model Pipeline: {metadata.get('model_name', 'TF-IDF + LogisticRegression')}")
    print(f"Accuracy:    {metrics['accuracy']*100:.2f}%")
    print(f"Precision:   {metrics['precision']*100:.2f}%")
    print(f"Recall:      {metrics['recall']*100:.2f}%")
    print(f"F1 Score:    {metrics['f1']*100:.2f}%")
    print(f"Macro-F1:    {metrics['macro_f1']*100:.2f}%")
    print(f"Weighted-F1: {metrics['weighted_f1']*100:.2f}%")
    if metrics.get("brier_score") is not None:
        print(f"Brier Score: {metrics['brier_score']}")

    print("\nConfusion Matrix:")
    cm = metrics["confusion_matrix"]
    print(f"  True Negatives (Reliable correctly identified):   {cm['tn']}")
    print(f"  False Positives (Reliable flagged as Misleading): {cm['fp']}")
    print(f"  False Negatives (Misleading missed):              {cm['fn']}")
    print(f"  True Positives (Misleading correctly identified): {cm['tp']}")

    print("\nPer-Class Breakdown:")
    print(f"  Reliable-style:   P={metrics['per_class']['reliable_class_0']['precision']*100:.1f}%, R={metrics['per_class']['reliable_class_0']['recall']*100:.1f}%, F1={metrics['per_class']['reliable_class_0']['f1']*100:.1f}%")
    print(f"  Misleading-style: P={metrics['per_class']['misleading_class_1']['precision']*100:.1f}%, R={metrics['per_class']['misleading_class_1']['recall']*100:.1f}%, F1={metrics['per_class']['misleading_class_1']['f1']*100:.1f}%")

    print("\n[Notice] TruthLens AI is an automated text classifier, not an authoritative fact-checker.")
    print("=" * 65)


if __name__ == "__main__":
    run_evaluation()

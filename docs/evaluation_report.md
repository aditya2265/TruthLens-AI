# TruthLens AI — Model Evaluation Report

**Evaluation Date:** 2026-10-10T10:15:10.575694+00:00
**Model Pipeline:** TF-IDF (1-2 grams, max 25k) + LogisticRegression (C=1.0)
**Dataset:** Fake and Real News Dataset (ISOT / Clement Bisaillon) (Cleaned held-out test split)
**Total Training Pipeline Duration:** 148.11 seconds

---

## 1. Held-Out Test Evaluation (n = 6615)
*This held-out test set was evaluated exactly once after model selection and thresholds were frozen.*

| Metric | Score | Note |
|---|---|---|
| **Accuracy** | **98.55%** | Overall fraction of correct classifications |
| **Precision** | **98.83%** | True positives / (True positives + False positives) |
| **Recall** | **98.36%** | True positives / (True positives + False negatives) |
| **F1 Score** | **98.59%** | Harmonic mean of precision and recall |
| **Macro F1** | **98.55%** | Unweighted mean of per-class F1 scores |
| **Weighted F1** | **98.55%** | Class-frequency weighted mean F1 |
| **Brier Score** | **0.0174** | Mean squared difference between probabilities and outcomes |

### Per-Class Test Performance
- **Reliable-style Patterns (Class 0):** Precision: 98.25%, Recall: 98.75%, F1: 98.50%
- **Misleading-style Patterns (Class 1):** Precision: 98.83%, Recall: 98.36%, F1: 98.59%

### Confusion Matrix (Test Split)
- **True Negatives (Reliable correctly identified):** 3152
- **False Positives (Reliable misclassified as Misleading):** 40
- **False Negatives (Misleading misclassified as Reliable):** 56
- **True Positives (Misleading correctly identified):** 3367

---

## 2. Validation Split Model Comparison (n = 6636)
| Model Candidate | Val Accuracy | Val Precision | Val Recall | Val F1 | Brier Score |
|---|---|---|---|---|---|
| **LogisticRegression (Selected)** | 98.60% | 98.76% | 98.50% | 98.63% | 0.0166 |
| **LinearSVC** | 99.11% | 99.20% | 99.06% | 99.13% | N/A (SVM decision margin) |

**Selection Rationale:** LogisticRegression was chosen because it achieves comparable or superior generalization while providing genuine calibrated probability scores and linear per-token additive explanations.

---

## 3. Leakage Audit & Limitations
- **Publisher/Dateline Filtering:** Journalistic headers like `(Reuters) -` were stripped prior to training.
- **Scope Limitation:** Training data originates from US political coverage circa 2016-2017. Current real-world claims outside this distribution should be treated with appropriate uncertainty.
- **Language Scope:** The model was evaluated exclusively on English-language texts. Non-English submissions are intercepted by the Stage 5 language safety guard and are not evaluated against this model.
- **Operational Rule:** TruthLens AI output represents statistical text similarity, NOT fact verification.

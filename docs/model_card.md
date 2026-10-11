# Model Card: TruthLens AI Text Classifier

## 1. Model Overview
- **Model Architecture:** scikit-learn Pipeline with `TfidfVectorizer(ngram_range=(1,2), max_features=25000, min_df=3, max_df=0.85, sublinear_tf=True)` and `LogisticRegression(C=1.0, max_iter=1000, random_state=42, solver='lbfgs')`.
- **Model Version:** 1.0.0
- **Release Date:** October 2026
- **License:** CC0 Public Domain (aligned with training data)
- **Frameworks:** scikit-learn 1.5.2, Python 3.12.10
- **Training Artifact:** `models/truthlens_model.joblib`
- **Metadata Artifact:** `models/model_metadata.json`

---

## 2. Intended Use and Scientific Boundaries
- **Intended Use:** Educational and demonstration tool for NLP text classification, transparent token-level feature attribution, writing style analysis, and external evidence retrieval.
- **Out-of-Scope / Prohibited Uses:**
  - Automated censorship, content moderation, or account suspension.
  - Asserting legal or factual truth regarding individuals, political candidates, or private organizations.
  - Using the model score as an authoritative "probability that news is true".

---

## 3. Training & Validation Data
- **Corpus:** Fake and Real News Dataset (ISOT / Clément Bisaillon)
- **Raw Records:** 44,898 articles
- **Deduplicated & Retained Rows:** 44,267 articles across 37,862 SimHash prefix clusters
- **Split Strategy:** Stratified Group-Aware Partitioning:
  - **Training Split (70%):** 31,016 articles
  - **Validation Split (15%):** 6,636 articles
  - **Held-Out Test Split (15%):** 6,615 articles
- **Leakage Prevention:** Reuters lead datelines (`WASHINGTON (Reuters) -`) and boilerplate photo credits stripped prior to TF-IDF fitting.

---

## 4. Empirical Evaluation Results (Held-Out Test Split, n = 6,615)
*Evaluated strictly once after preprocessing, model selection, and thresholds were frozen.*

| Metric | Score | Note |
|---|---|---|
| **Accuracy** | **98.55%** | Overall correct classification fraction |
| **Precision** | **98.83%** | Positive Predictive Value |
| **Recall** | **98.36%** | Sensitivity for Misleading Class |
| **F1 Score** | **98.59%** | Harmonic mean of precision and recall |
| **Macro F1** | **98.55%** | Unweighted average across both classes |
| **Weighted F1** | **98.55%** | Class-weighted average F1 |
| **Brier Score** | **0.0174** | Calibrated posterior probability loss on test set |

### Confusion Matrix (Test Split)
- **True Negatives (Reliable correctly identified):** 3,152
- **False Positives (Reliable misclassified as Misleading):** 40
- **False Negatives (Misleading misclassified as Reliable):** 56
- **True Positives (Misleading correctly identified):** 3,367

---

## 5. Model Explanation Mechanism
- Explanations are derived directly from the linear decomposition of the fitted model:
  $$\text{Contribution}_i = \text{TF-IDF}(w_i) \times \beta_i$$
- A positive contribution pushes the model toward Class 1 (Misleading-style).
- A negative contribution pushes the model toward Class 0 (Reliable-style).
- **Caveat:** Token contributions explain *model feature weights*, not factual truth.

---

## 6. Language Safety & Classifier Isolation
- **English-Only Scope:** The classifier was trained exclusively on English-language news reporting.
- **Language Safety Guard (`src/language.py`):** User inputs undergo pre-inference script and stopword analysis.
- **Strict Short-Circuiting:** Non-English inputs (including Hindi in Devanagari script, Cyrillic, Arabic, CJK, Spanish, French, German, and romanized Hindi) immediately bypass `load_model()` and pipeline inference.
- **User Notice:** Returns the exact message: `"Unable to assess: this model was trained on English news."` with no verdict, no decision score, and no fake/real label.

---

## 7. Known Limitations
1. **Domain & Temporal Specificity:** Sourced predominantly from 2016-2017 US political articles.
2. **Short Text Sensitivity:** Accuracy degrades on short snippets (<15 words). The system raises explicit uncertainty alerts in such cases.
3. **Journalistic Syntax Reliance:** The model heavily weights formal wire attribution verbs (e.g., "said", "on wednesday") which can cause well-written falsehoods to mimic reliable syntax.
4. **Short Non-English Snippets:** Non-English phrases under 4 words without distinguishing script markers (e.g., foreign proper nouns in Latin script) may pass the language guard and rely on the input-brevity quality warning.

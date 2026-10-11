# TruthLens AI — College & Hackathon Project Technical Report

**Project Title:** TruthLens AI: Autonomous NLP-Based Misleading Content Detector & Fact-Check Explorer  
**Author / Developer:** Solo Project Developer  
**Technologies:** Python 3.12, scikit-learn, Flask, Jinja2, pandas, SQLite, requests, trafilatura, Chart.js  
**Evaluation Date:** October 2026  

---

## 1. Abstract
The rapid diffusion of digital misinformation presents a substantial challenge to civic discourse and information literacy. However, conventional automated systems frequently present opaque, binary verdicts that deceive users with unearned confidence. **TruthLens AI** was developed as an open, explainable text-classification and evidence-discovery system that assists readers in dissecting news headlines, full-length articles, and short claims. Rather than purporting to act as an authoritative oracle, TruthLens AI strictly separates machine-learning lexical patterns, transparent rules-based sensationalism indicators, external fact-checks from the official Google Fact Check Tools API, and actionable human verification guidance.

---

## 2. Theoretical Architecture & Methodology

### 2.1 Machine Learning Pipeline
- **Vectorization:** TF-IDF with word unigrams and bigrams, capped vocabulary of 25,000 features, minimum document frequency $min\_df=3$, maximum document frequency $max\_df=0.85$, and sublinear term-frequency scaling.
- **Classification Baseline:** Logistic Regression with L2 regularization ($C=1.0$) and lbfgs solver. Logistic Regression was prioritized over Support Vector Machines because it natively minimizes log-loss, yielding well-calibrated posterior probabilities and allowing additive linear feature attributions.

### 2.2 Leakage Prevention and Data Hygiene
1. **Journalistic Dateline Filtering:** The ISOT Fake and Real News benchmark features systematic wire service headers (`WASHINGTON (Reuters) -`) in ground-truth articles. Without mitigation, classifiers learn trivial token shortcuts. TruthLens AI strips datelines and boilerplate image credits using regex prior to TF-IDF transformation.
2. **Cluster-Aware Splitting:** 10,768 duplicate and syndicated articles were identified in the raw data. To prevent cross-split contamination, records were grouped into 37,862 SimHash prefix clusters and split using group-aware stratified partitioning (70% train, 15% validation, 15% test).

### 2.3 Remote Article Ingestion & SSRF Mitigation
In `src/url_fetcher.py`, URL submissions undergo strict security auditing:
- Protocol restriction to HTTP/HTTPS.
- Comprehensive IP range auditing (`is_ip_prohibited`) blocking loopback, RFC 1918, link-local, multicast, and cloud metadata (`169.254.169.254`, `metadata.google.internal`).
- Pre-flight DNS resolution of all IP addresses associated with the host.
- Redirect verification (max 3) with per-hop IP auditing.
- Bounded 2 MB streaming limits and strict (5s connect, 10s read) timeouts.
- Clean text extraction utilizing Trafilatura.

### 2.4 External Evidence & Live News Integration
- **GDELT 2.0 Live News Feed (`src/news_feed.py`):** Consumes keyless open GDELT DOC API dispatches with bounded timeouts (15s connect, 25s read), URL canonicalization, client-side 5s request throttling, and rate-limit (HTTP 429) defense.
- **Google Fact Check Tools API (`src/factcheck.py`):** Queries `v1alpha1/claims:search` using article titles/claims. Results are displayed as supporting evidence in Pillar C, explicitly distinct from the ML score.

### 2.5 Language Safety Safeguard (`src/language.py`)
- Standard-library-only (`unicodedata`, `re`) language safety guard.
- Inspects Unicode script blocks for non-Latin alphabets (Devanagari `\u0900-\u097F`, Cyrillic, Arabic, CJK, etc.) and evaluates Latin foreign stopword frequencies.
- If non-English text is detected, the English-trained ML model is **never invoked**. Returns:
  > *"Unable to assess: this model was trained on English news."*
  with no verdict, no decision score, and an explicit note that this is a language constraint, not a claim judgment.

---

## 3. Empirical Results & Evaluation
The final frozen model was evaluated strictly once on the held-out test split ($n = 6,615$):

- **Accuracy:** 98.55%
- **Precision:** 98.83%
- **Recall:** 98.36%
- **F1 Score:** 98.59%
- **Macro-F1:** 98.55%
- **Brier Calibration Score:** 0.0174 (Demonstrating reliable probability calibration)

### Confusion Matrix ($n = 6,615$):
- True Negatives (Reliable correctly identified): 3,152
- False Positives (Reliable misclassified as Misleading): 40
- False Negatives (Misleading misclassified as Reliable): 56
- True Positives (Misleading correctly identified): 3,367

---

## 4. Explainability & Transparent Writing Signals
- **Additive Token Contributions:** Influential tokens are decomposed as $\text{Contrib}_i = \text{TF-IDF}_i \times \beta_i$. Terms pushing toward misleading patterns (e.g., "via", "read more", "watch") and reliable wire syntax (e.g., "said", "on wednesday", "told reporters") are transparently displayed.
- **Rules-Based Clickbait Engine:** A separate heuristic module evaluates uppercase letter ratios, repeated punctuation, urgency calls-to-action, and absolute claims. This engine operates independently and never overrides the machine-learning verdict.

---

## 5. Security, Privacy, and Software Quality
- Full CSRF protection across all state-changing forms using Flask-WTF.
- Input bounds of 15,000 characters to prevent resource exhaustion.
- Complete omission of sensitive file paths, secrets, or internal stack traces from `/health` and error views.
- Parameterized SQLite queries for optional local analysis history, ensuring total user privacy.
- Deterministic automated test suite: 134 automated pytest tests passing in ~14 seconds.

---

## 6. Conclusion and Future Directions
TruthLens AI successfully demonstrates that an NLP classifier can be accurate, transparent, and ethically bounded. By separating machine learning, heuristic writing signals, external fact-checking evidence, and language safety guards, the application establishes a new standard for responsible AI in media literacy. Future extensions include packaging the container for IBM Cloud Code Engine and incorporating IBM watsonx.ai for claim summarization.

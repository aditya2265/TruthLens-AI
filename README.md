# TruthLens AI — Fake News and Misleading Content Detector

> **Autonomous NLP-based text classifier, token-level feature explainer, rules-based sensationalism analyzer, and fact-check explorer.**  
> Built for a solo IBM-aligned hackathon and college project on Windows.

---

## 1. Project Overview & Mission

**TruthLens AI** is an explainable natural-language-processing web application designed to help users examine news headlines, full-length articles, and short claims.

Unlike opaque black-box tools that purport to "prove whether news is true", TruthLens AI operates under strict scientific integrity:
1. **Automated text-classification assessment, NOT authoritative fact-checking:** It identifies linguistic, stylistic, and vocabulary patterns associated with historical training corpora.
2. **Four strictly separated pillars:**
   - **Pillar A (Machine Learning):** Empirical patterns learned from a real dataset (TF-IDF + Logistic Regression).
   - **Pillar B (Rules-Based Signals):** Transparent writing cues (sensational phrases, ALL CAPS, repeated punctuation, urgency bait).
   - **Pillar C (External Evidence):** Independent fact-checks from the official Google Fact Check Tools API (`v1alpha1/claims:search`).
   - **Pillar D (Human Verification):** Actionable 5-step checklist for critical source evaluation.
3. **Conservative, honest labeling:** Results are presented as *"Reliable-style patterns"*, *"Misleading-style patterns"*, or *"Uncertain / Unable to assess"*, never "100% verified true" or "definitely fake".
4. **Strict Language Safety:** Isolates the English-trained model; non-English inputs (e.g. Hindi in Devanagari script) safely short-circuit with exact message: *"Unable to assess: this model was trained on English news."*

---

## 2. Key Features

- **Genuine Trained Model:** Fitted on the real Fake and Real News Dataset (ISOT / Clément Bisaillon) on 44,267 cleaned articles.
- **Leakage-Safe Preprocessing:** Strips journalistic datelines (`WASHINGTON (Reuters) -`) and template image credits before vectorization to prevent trivial shortcut learning.
- **Group-Aware Splitting:** 10,768 duplicate and syndicated texts grouped into 37,862 SimHash prefix clusters to ensure identical stories never cross splits.
- **Additive Token Explanations:** Computes exact per-token feature contributions ($\text{TF-IDF} \times \beta$) displaying influential terms that pushed the prediction toward either class.
- **Separate Clickbait & Sensationalism Analysis:** Independent rules-based detection that checks excessive capitalization, repeated punctuation, urgency calls-to-action, and absolute claims.
- **Safe Remote URL Analysis:** Trafilatura article extraction protected by strict SSRF defenses: blocked private RFC 1918, loopback, link-local, and cloud metadata IPs, pre-flight DNS resolution, redirect auditing, 2 MB size caps, and strict timeouts.
- **Live GDELT News Feed:** Front-page discovery feed from the official GDELT 2.0 DOC API with 5-second rate throttling, URL canonicalization, and dynamic client-side refresh without full page reloads.
- **External Related Fact-Checks:** Integration with the official Google Fact Check Tools API; displays publisher attribution and verbatim ratings as supporting evidence, completely separated from the ML score.
- **Language Safety Guard:** Pure-Python (`unicodedata`, `re`) script and stopword analysis. Blocks non-English inputs before classifier loading, returning exact expected notice without verdicts.
- **Consumer UI & Dark Mode:** Light theme by default with seamless dark-mode toggle persisted in `localStorage`, responsive cards, and Chart.js performance visualizations.
- **Comprehensive Test Suite:** 139 automated pytest tests passing in ~16 seconds without live external API dependencies.

---

## 3. Technology Stack

- **Backend:** Python 3.12, Flask 3.0.3, Jinja2 3.1.6, Flask-WTF 1.2.2 (CSRF protection), SQLite3
- **Machine Learning & NLP:** scikit-learn 1.5.2, pandas 2.2.3, numpy 2.1.3, scipy 1.18.1, joblib 1.4.2
- **Remote Extraction & Ingestion:** requests 2.32.3, trafilatura 1.12.2
- **Frontend:** Semantic HTML5, Vanilla CSS3 (Custom design system with dark mode), Vanilla JavaScript, Chart.js 4.4.1
- **Testing & Environment:** pytest 8.4.2, python-dotenv 1.0.1, Windows PowerShell

---

## 4. Repository Structure

```text
TruthLens AI/
├── .env.example             # Configuration template
├── .gitignore               # Version control ignore rules
├── requirements.txt         # Pinned/constrained dependencies
├── render.yaml              # Cloud deployment configuration
├── data/
│   ├── raw/                 # Original datasets (Fake.csv, True.csv)
│   └── processed/           # Cleaned splits (train.csv, val.csv, test.csv)
├── models/
│   ├── truthlens_model.joblib   # Persisted fitted scikit-learn Pipeline
│   └── model_metadata.json      # Comprehensive training & evaluation metadata
├── results/
│   ├── data_quality_report.json # Dataset audit and length distributions
│   ├── evaluation_report.json   # Held-out test metrics and confusion matrix
│   └── leakage_audit.json       # Top 30 positive & negative coefficients
├── src/
│   ├── __init__.py
│   ├── config.py            # Paths, labels, and parameters
│   ├── preprocessing.py     # Text cleaning, SimHash grouping, splits
│   ├── train.py             # Reproducible training & evaluation pipeline
│   ├── evaluate.py          # Standalone evaluation inspection CLI
│   ├── predict.py           # Inference engine with uncertainty heuristics
│   ├── explain.py           # Linear per-token contribution calculator
│   ├── clickbait.py         # Rules-based sensationalism analyzer
│   ├── url_fetcher.py       # Trafilatura extraction & SSRF defenses
│   ├── news_feed.py         # Live GDELT 2.0 DOC API consumer
│   ├── factcheck.py         # Google Fact Check Tools API client
│   ├── language.py          # Language safety & non-English guard
│   ├── history.py           # Local SQLite history with CSRF actions
│   └── app.py               # Flask application and security routes
├── templates/
│   ├── base.html            # Core layout, navigation, and disclaimer
│   ├── index.html           # Main dashboard and results display
│   ├── about.html           # Methodology, architecture, and ethics
│   ├── performance.html     # Real evaluation metrics and charts
│   ├── history.html         # Local analysis history and delete actions
│   ├── 400.html             # Bad request / CSRF error view
│   ├── 404.html             # Custom 404 page
│   └── 500.html             # Custom 500 error page
├── static/
│   ├── css/style.css        # Responsive stylesheet with dark theme
│   └── js/main.js           # Client interactions and demo loaders
├── tests/
│   ├── __init__.py
│   ├── fixtures.py          # Isolated synthetic test fixtures
│   ├── test_clickbait.py    # Unit tests for sensationalism rules
│   ├── test_preprocessing.py# Tests for cleaning and group-aware splitting
│   ├── test_model.py        # Pipeline fitting and explanation tests
│   ├── test_url_fetcher.py  # Tests for SSRF defenses and article extraction
│   ├── test_news_feed.py    # Tests for GDELT API and caching behavior
│   ├── test_factcheck.py    # Tests for Google Fact Check integration
│   ├── test_language.py     # Tests for language safety and Hindi rejection
│   └── test_flask.py        # Integration and security tests
├── docs/
│   ├── PROGRESS.md          # Stage checklists and milestone verification
│   ├── implementation_plan.md# Architecture and engineering plan
│   ├── dataset_card.md      # Dataset source, schema, and license card
│   ├── data_quality_report.md# Detailed data distribution report
│   ├── model_card.md        # Model architecture and test metrics
│   ├── evaluation_report.md # Held-out test results and confusion matrix
│   ├── security.md          # Security architecture and CSRF controls
│   ├── judge_qa.md          # Hackathon judge Q&A guide
│   ├── presentation.md      # 5-7 minute presentation script
│   ├── report.md            # College project technical report
│   ├── architecture.mmd     # Mermaid system architecture diagram
│   └── blockers.md          # Blockers and mitigations log
└── scripts/
    └── demo_check.ps1       # Automated PowerShell verification script
```

---

## 5. Quickstart Guide (Windows PowerShell)

### Prerequisites
- Windows 10/11
- Python 3.11 or 3.12 installed (`python --version`)

### Step 1: Open PowerShell and Navigate to Workspace
```powershell
cd "d:\TruthLens AI"
```

### Step 2: Create and Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### Step 3: Install Dependencies
```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### Step 4: Configure Environment Variables (Optional)
Copy `.env.example` to `.env` if custom configuration is desired:
```powershell
Copy-Item .env.example .env
```
To enable live Google Fact Check searches, set your API key in `.env`:
```text
GOOGLE_FACTCHECK_API_KEY=your_actual_api_key_here
```
*(If left unconfigured, the fact-check section displays a clear configuration guide and primary classification operates seamlessly.)*

### Step 5: Run Automated Test Suite
```powershell
.\.venv\Scripts\python.exe -m pytest -q
```
*Expected result: 139 passed in ~16 seconds.*

### Step 6: Run Complete Verification & Demonstration Script
```powershell
powershell -ExecutionPolicy Bypass -File ".\scripts\demo_check.ps1"
```
*Automates test execution, model artifact verification, server startup, `/health` check, English prediction, Hindi language rejection, and homepage loading.*

### Step 7: Launch the Application
```powershell
.\.venv\Scripts\python.exe -m src.app
```
Open your browser and navigate to:
**`http://127.0.0.1:5000`**

---

## 6. Empirical Evaluation Results

Evaluated strictly on the held-out test set ($n = 6,615$ articles):

| Metric | Score | Note |
|---|---|---|
| **Test Accuracy** | **98.55%** | Correct classifications fraction |
| **Test Precision** | **98.83%** | True positives / (True pos + False pos) |
| **Test Recall** | **98.36%** | True positives / (True pos + False neg) |
| **Test F1 Score** | **98.59%** | Harmonic mean of precision & recall |
| **Macro F1** | **98.55%** | Unweighted mean across classes |
| **Weighted F1** | **98.55%** | Class-weighted average F1 |
| **Brier Score** | **0.0174** | Calibrated posterior probability error |

---

## 7. How to Demonstrate to Hackathon Judges

1. **Start the application:**
   ```powershell
   .\.venv\Scripts\python.exe -m src.app
   ```
   Open `http://127.0.0.1:5000`.
2. **Demo 1 — Reuters Wire Dispatch:** Click the *"Reuters-Style Wire Dispatch"* demo card. Click **"Analyze Content"**. Show judges that the model detects *"Reliable-style patterns"* and highlights formal attribution verbs ("said", "hearing", "officials").
3. **Demo 2 — Sensational Clickbait:** Click the *"Sensational Viral Headline"* demo card. Click **"Analyze Content"**. Point out:
   - Machine learning flags *"Misleading-style patterns"* based on lexical features ("via", "shocking", "blow your mind").
   - Pillar B independently flags **Elevated Sensationalism** (ALL CAPS, repeated punctuation, urgency bait).
4. **Demo 3 — Stage 5 Language Safety (Hindi Input):** Paste a Hindi headline:
   ```text
   भारत सरकार ने किसानों के लिए एक नई योजना की घोषणा की है।
   ```
   Click **"Analyze Content"**. Show judges that TruthLens safely short-circuits with:
   > *"Unable to assess: this model was trained on English news."*
   and does **not** call the English model or produce arbitrary fake/real scores.
5. **Demo 4 — URL Analysis & SSRF Defense:** Paste a news article URL into the Article Link tab. Point out extracted title, source domain, excerpt, and related fact-checks.
6. **Demo 5 — Live News Feed (GDELT):** Show the 6–9 live headlines from GDELT, click **"⚡ Analyze"** on any headline, and show the **"🔄 Refresh"** button.
7. **Demo 6 — Performance Page (`/performance`):** Show judges the genuine confusion matrix ($n=6,615$), the validation model comparison, and the interactive Chart.js graphs.
8. **Reference the Judge Q&A Guide (`docs/judge_qa.md`):** Be prepared to answer why 99% accuracy is not real-world fact verification, how dateline leakage was mitigated, and how SSRF protection was implemented.

---

## 8. Ethical Boundaries & Known Limitations

- **Not an Authoritative Fact-Checker:** The model evaluates textual and lexical similarity to historical training data, not factual truth.
- **Temporal Scope:** Training data reflects US political journalism from approximately 2016-2017. Current real-world events outside this distribution should be treated with appropriate uncertainty.
- **Language Scope:** Trained exclusively on English-language texts. Non-English submissions are intercepted by the Stage 5 language safety guard.
- **Mandatory Disclaimer on All Results:**
  > *"This result is an automated text-classification assessment, not independent fact verification. The model can make mistakes and may reflect biases or limitations in its training data. Check important claims against reliable, independent sources."*

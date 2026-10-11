# Implementation Plan — TruthLens AI

## 1. Executive Summary & Objective
TruthLens AI is an NLP-based fake news and misleading content detector designed for a solo IBM-related hackathon and college project. It operates as an **automated text-classification assessment**, clearly distinguished from authoritative fact-checking. It provides:
- Machine learning classification using real dataset labels and cautious wording ("Reliable-style patterns", "Misleading-style patterns", "Uncertain").
- Transparent model explanation showing influential token contributions (TF-IDF × linear coefficients).
- Separate, transparent rules-based writing signals (sensationalism, excessive capitalization, clickbait cues).
- Honest model evaluation metrics based strictly on genuine held-out test splits.
- Verification checklists and clear uncertainty/limitation warnings.
- Robust, beginner-friendly local execution on Windows with zero paid external APIs.

## 2. Architecture & Components
- **Backend**: Python 3.12, Flask, Jinja2, Flask-WTF (CSRF protection), SQLite (optional local history).
- **ML & NLP**: pandas, numpy, scikit-learn (Pipeline: TfidfVectorizer + LogisticRegression baseline, LinearSVC comparison), joblib.
- **Frontend**: Dark intelligence-dashboard aesthetic (Navy/Slate/Teal), semantic HTML5, Vanilla CSS3, Vanilla JS, Chart.js (evaluation graphs).
- **Testing**: pytest test suite covering preprocessing, leakage checks, models, Flask routes, clickbait rules, security.

## 3. Stages & Milestones
- **Stage 1: Workspace Inspection & Plan**: Inspect OS, Python 3.12, directory structure. Establish plan & progress tracker.
- **Stage 2: Environment & Foundation**: Setup `.venv` using Python 3.12, install pinned dependencies, configure `.gitignore` and `.env.example`.
- **Stage 3: Dataset Discovery & Preparation**: Locate or download `Fake.csv` and `True.csv` (`clmentbisaillon/fake-and-real-news-dataset`). Generate `docs/data_quality_report.md` & `results/data_quality_report.json`. Implement reproducible preprocessing, exact duplicate removal, near-duplicate handling, and stratified group-aware splits (70/15/15).
- **Stage 4: Training & Evaluation**: Train baseline TF-IDF + Logistic Regression, perform coefficient inspection & leakage audit (filter out Reuters datelines/publisher markers), compare models, freeze final model, evaluate on test set once, generate `docs/evaluation_report.md` & `results/evaluation_report.json`.
- **Stage 5: Prediction & Explanation**: Build `src/predict.py`, `src/explain.py`, `src/clickbait.py`. Incorporate input suitability heuristics (vocabulary coverage, length checks).
- **Stage 6: Flask Backend & Interface**: Implement Flask routes (`/`, `/predict`, `/about`, `/performance`, `/health`), CSRF protection, rate limiting, error handlers (404/500), dark UI dashboard.
- **Stage 7: Testing & Verification**: Comprehensive pytest suite with isolated synthetic fixtures; PowerShell verification script `scripts/demo_check.ps1`.
- **Stage 8: Enhancements (Priority 2)**: Clickbait analysis integration, Performance dashboard with real charts, local history (SQLite with delete/clear), demo examples.
- **Stage 9: Documentation**: `README.md`, `docs/dataset_card.md`, `docs/model_card.md`, `docs/security.md`, `docs/report.md`, `docs/presentation.md`, `docs/judge_qa.md`.
- **Stage 10: Final Verification & Evidence Ledger**: Run all tests, start server, verify via browser/HTTP, assemble evidence ledger.

## 4. Technical Constraints & Integrity Rules
- No fabricated metrics, predictions, screenshots, or citations.
- Preprocessing and vectorizer fitted on training split only.
- Test set evaluated exactly once after model freezing.
- Strict separation: ML classification vs. Rules-based writing signals vs. External evidence checklist.
- Conservative wording: Never claim an article is "proven true" or "definitely fake".

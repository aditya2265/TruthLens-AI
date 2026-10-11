# TruthLens AI — 5 to 7 Minute Hackathon Presentation Outline

## Slide 1: Title & The Problem (1:00)
- **Title:** TruthLens AI — Transparent NLP Misleading Content & Fact-Check Explorer
- **Problem Statement:** Misinformation is proliferating online, but black-box AI tools often over-promise, claiming to "prove truth" while making confident blunders.
- **Our Vision:** Build an explainable, scientifically honest tool that empowers users to analyze text patterns without false certainty.

---

## Slide 2: The Core Philosophy — Strictly Separated Pillars (1:00)
- **Never combine different reasoning types into one fake "truth score":**
  - **Pillar A (Machine Learning):** Empirical lexical patterns learned from real news corpora (TF-IDF + Logistic Regression).
  - **Pillar B (Rules-Based Signals):** Transparent writing cues (sensational phrases, ALL CAPS, repeated punctuation, urgency bait).
  - **Pillar C (External Evidence):** Independent fact-checks from the official Google Fact Check Tools API.
  - **Pillar D (Human Verification):** Actionable 5-step checklist for critical source evaluation.

---

## Slide 3: Dataset Rigor & Leakage Prevention (1:00)
- Trained on the ISOT / Clément Bisaillon Fake and Real News Dataset (44,898 raw records).
- **The "Reuters" Shortcut Problem:** Raw real news leads with `(Reuters) -`. Uncorrected models cheat and achieve 99% accuracy trivially.
- **Our Mitigation:** Automated dateline regex stripping, duplicate deduplication across 37,862 SimHash groups to prevent train-test contamination.

---

## Slide 4: Empirical Results & Calibration (0:45)
- **Held-Out Test Set (n = 6,615):** Evaluated strictly once after model freezing.
  - **Accuracy:** 98.55%
  - **Precision:** 98.83% | **Recall:** 98.36% | **F1 Score:** 98.59%
  - **Brier Calibration Score:** 0.0174 (Demonstrating genuine probability calibration).
- **Model Comparison:** Evaluated LogisticRegression vs. LinearSVC on validation split. Chose LogisticRegression for direct calibrated probabilities and linear token explanations.

---

## Slide 5: Live Ingestion & Enterprise Security (1:00)
- **Safe URL Analysis:** Trafilatura article extraction with strict SSRF defenses (RFC 1918, loopback, cloud metadata blocking, redirect re-auditing, 2 MB size caps).
- **Live GDELT News Feed:** Dynamic headlines from the official GDELT 2.0 DOC API with 5-second rate throttling, URL canonicalization, and zero fabricated content.
- **Related Fact-Checks:** Queries Google Fact Check Tools API; displays publisher attribution and verbatim ratings without overriding the ML model.

---

## Slide 6: Language Safety & Ethical Guardrails (0:45)
- **Model Scope Constraint:** The ML model was trained solely on English news.
- **Zero-Dependency Language Guard (`src/language.py`):** Pre-inference Unicode script analysis detects Hindi (Devanagari `\u0900-\u097F`), Cyrillic, Arabic, CJK, and foreign Latin text.
- **Short-Circuit Protection:** Non-English input immediately bypasses the classifier, returning:
  > *"Unable to assess: this model was trained on English news."*
  with no verdict and clear notice that this is a language safeguard, not a judgment on the claim.

---

## Slide 7: Live Demonstration & Future Roadmap (1:00)
- **Demo Workflow:**
  1. Paste a Reuters-style wire dispatch -> Model highlights formal attribution verbs ("said", "hearing").
  2. Paste sensational clickbait -> Model flags misleading patterns + rules flag ALL CAPS and urgency bait.
  3. Enter Hindi text -> System safely short-circuits with exact language notice.
  4. One-click analyze a headline from the Live News Feed -> Demonstrates end-to-end integration.
- **Future IBM Alignment:** Integration with IBM watsonx.ai for claim summarization and deployment to IBM Cloud Code Engine.
- **Closing Thought:** *"TruthLens AI is an NLP classifier, not a fact-checker. AI should augment human critical thinking, not replace it."*

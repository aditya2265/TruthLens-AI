# TruthLens AI — Hackathon Judge Q&A Guide

Prepared for hackathon and project evaluation presentations. Provides clear, scientifically honest responses to tough technical questions.

---

### Q1: "Your model achieved ~98.5% accuracy on the test set. Does that mean it will be 98.5% accurate on tomorrow's news?"
**Answer:**
> "No, absolutely not—and that is a critical distinction we emphasize throughout TruthLens AI. 
> 
> A high test score on an in-distribution test split merely proves that the model learned the statistical patterns present in the 2016-2017 training corpus. Real-world news exhibits **temporal drift** (new topics, political figures, and terminology) and **domain shifts**. 
> 
> In fact, claiming 99% real-world accuracy on fake news is scientifically dishonest. That is why TruthLens AI incorporates vocabulary novelty warnings, uncertainty bands, and a mandatory disclaimer clarifying that automated classification is not independent fact verification."

---

### Q2: "What is data leakage in NLP, and how did you prevent it in TruthLens AI?"
**Answer:**
> "Data leakage occurs when predictive information that would not naturally be present at test time leaks into training features, or when identical records cross train-test splits.
> 
> In this dataset, there were two major leakage risks:
> 1. **Journalistic Dateline Leakage:** In raw data, genuine news articles almost universally began with `WASHINGTON (Reuters) -` or `(Reuters) -`. Models left uncleaned simply memorize the word 'Reuters' as a shortcut for 'True'. We mitigated this in `src/preprocessing.py` by regex-stripping dateline headers before TF-IDF tokenization.
> 2. **Duplicate & Syndicated Leakage:** We found 10,768 duplicate or syndicated articles. If one copy was in train and another in test, test accuracy would be artificially inflated. We implemented SimHash prefix clustering to ensure that syndicated clusters never crossed train, validation, and test splits."

---

### Q3: "Why is TruthLens AI designed as a text classifier rather than an automated fact-checker?"
**Answer:**
> "Automated fact-checking requires evaluating the objective truth value of an external proposition against verifiable real-world evidence (e.g., verifying if a corporate merger took place, or if a statistical census figure is correct). 
> 
> An NLP classifier only evaluates lexical style, vocabulary choices, and sentence patterns. A completely false story written in dry, formal journalistic wire style could deceive the model, while a true citizen journalist report written with passionate language might register as informal.
> 
> Conflating classification with fact verification creates dangerous false trust. We separate our system into distinct pillars: Machine Learning Patterns, Transparent Writing Signals, External Fact-Checks, and an Independent Human Verification Checklist."

---

### Q4: "How are the token explanations computed, and what are their limitations?"
**Answer:**
> "We compute explanations using exact linear feature attribution: the input token's TF-IDF score multiplied by the fitted model coefficient ($\beta_i$). Terms with positive weights push the score toward misleading patterns, while terms with negative weights push it toward reliable journalistic patterns.
> 
> Their limitation is that they reflect **corpus correlation, not factual falsehood**. For instance, seeing the word 'via' or 'twitter com' highlighted merely indicates that unverified blogs in 2016 frequently embedded tweets. It does not prove that Twitter embeds are inherently false."

---

### Q5: "How does the URL analysis feature work, and how do you protect against Server-Side Request Forgery (SSRF)?"
**Answer:**
> "In `src/url_fetcher.py`, when a user submits an article link, we extract clean body text using Trafilatura while enforcing strict defense-in-depth against SSRF:
> 1. We reject unsupported protocols and only permit HTTP and HTTPS.
> 2. We resolve hostnames via `socket.getaddrinfo` and audit *every* resolved IP address against prohibited subnets: loopback (`127.0.0.0/8`, `::1`), private RFC 1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`), link-local (`169.254.0.0/16`), multicast, and cloud metadata endpoints (`169.254.169.254`, `metadata.google.internal`).
> 3. Redirects are manually inspected and capped at 3, with destination IP re-auditing at every step.
> 4. We enforce bounded timeouts (5s connect, 10s read) and a 2 MB streaming size cap."

---

### Q6: "Why did you integrate GDELT for the front-page news feed, and how do you handle rate limits and timeouts?"
**Answer:**
> "GDELT provides global, keyless open access to live international news dispatches. In Stage 3, we integrated the GDELT 2.0 DOC API to give users fresh, real-world articles they can analyze with one click.
> 
> Because GDELT cross-dataset queries can take 10-15 seconds and enforce a 1 request per 5 seconds rate limit, we implemented:
> 1. Bounded connect (15s) and read (25s) timeouts with a 1 MB streaming cap.
> 2. Client-side 5-second request throttling and rate limit (HTTP 429) detection.
> 3. Caching and asynchronous dynamic refresh (`/api/news-feed?refresh=true`) so the homepage never freezes or shows fabricated headlines."

---

### Q7: "How does the Google Fact Check Tools API integration work, and how is it kept separate from the ML classifier?"
**Answer:**
> "In `src/factcheck.py`, we query the official Google Fact Check Tools API (`v1alpha1/claims:search`) using a concise query extracted from the article headline.
> 
> Crucially, external fact-checks are presented in **Pillar C (External Evidence)** as supporting context about related claims, completely separate from the machine-learning score. A fact-check match about a specific quote does not automatically dictate the whole-article label. Furthermore, if the API key is unconfigured or quota is exhausted, primary text classification continues seamlessly without disruption."

---

### Q8: "Why does TruthLens reject non-English text like Hindi, and how does the language detector work without heavy dependencies?"
**Answer:**
> "Our ML classifier was trained exclusively on English news data. Feeding non-English text into an English TF-IDF vectorizer produces arbitrary, misleading predictions based on random character n-grams.
> 
> In Stage 5, we implemented `src/language.py` using standard-library-only (`unicodedata`, `re`, `typing`):
> 1. It inspects Unicode script ranges for non-Latin alphabets—specifically detecting Devanagari (Hindi `\u0900-\u097F`), Cyrillic, Arabic, CJK, etc.
> 2. It checks high-frequency foreign stopwords (Spanish, French, German, Italian, romanized Hindi).
> 3. When non-English input is detected, the model pipeline is **never invoked** (verified via mock tests). Instead, it returns exactly: `'Unable to assess: this model was trained on English news.'` with no verdict and a clear notice that this is a language safeguard, not a verdict on the claim."

---

### Q9: "How could IBM Cloud or watsonx be integrated in future phases?"
**Answer:**
> "TruthLens AI is designed with an extensible modular backend. In future iterations, we could integrate IBM technologies in two high-value ways:
> 1. **watsonx.ai Governance & LLM Summarization:** Utilizing IBM watsonx.ai foundation models to generate balanced, multi-perspective summaries of disputed claims alongside our fast local classifier.
> 2. **IBM Cloud Code Engine Deployment:** Packaging TruthLens AI as a serverless container on IBM Cloud Code Engine for autoscaling and enterprise-grade resilience.
> 
> In this hackathon submission, we prioritized an independent, reproducible local deployment that runs without external API dependencies."

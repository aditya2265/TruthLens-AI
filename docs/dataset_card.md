# Dataset Card: Fake and Real News Dataset (ISOT / Clément Bisaillon)

## 1. Summary
The **Fake and Real News Dataset** is an open machine-learning benchmark collected and published by Clément Bisaillon on Kaggle, based largely on the Information Security and Object Technology (ISOT) research dataset from the University of Victoria. It comprises two primary CSV files containing real-world political articles published predominantly between 2016 and 2017.

- **Primary Source:** [Kaggle Dataset: clmentbisaillon/fake-and-real-news-dataset](https://www.kaggle.com/datasets/clmentbisaillon/fake-and-real-news-dataset)
- **License:** CC0: Public Domain (as declared on the Kaggle source page).
- **Redistribution:** Permitted under CC0, though raw CSV files are git-ignored in this repository to prevent repository bloat (>116 MB uncompressed).

---

## 2. Dataset Structure and Schema
The dataset consists of two files:

| File Name | Record Count | Ground-Truth Semantic Meaning | TruthLens Internal Label |
|---|---|---|---|
| `data/raw/Fake.csv` | 23,481 | Articles flagged as fake/misleading from unverified blogs & flagged sources | `1` (Misleading-style patterns) |
| `data/raw/True.csv` | 21,417 | Articles sourced from Reuters news wire service | `0` (Reliable-style patterns) |
| **Total Raw** | **44,898** | Binary classification corpus | Balanced (~52.3% vs 47.7%) |

### Column Definitions
Both files share the identical 4-column schema:
- `title` *(string)*: Headline or article title.
- `text` *(string)*: Full textual body of the news article. Primary predictive feature in TruthLens AI.
- `subject` *(string)*: Category tag (e.g., `politicsNews`, `worldnews`, `News`, `politics`, `Government News`, `US_News`, `left-news`). Excluded from model features to prevent category shortcuts.
- `date` *(string)*: Formatted publication date string (e.g., `December 31, 2017`). Excluded from model features to prevent temporal overfitting.

---

## 3. Label Meanings and Conceptual Nuances
- **Class 0 — "Reliable-style patterns":** Sourced from Reuters professional journalism. Articles adhere to formal journalistic wire service conventions, attributing quotes and utilizing standard editorial syntax.
- **Class 1 — "Misleading-style patterns":** Sourced from websites flagged by fact-checkers (PolitiFact, unverified political blogs). Articles frequently contain conversational editorializing, hyperbole, and speculative framing.

> [!WARNING]
> **Scientific Integrity Notice:** The labels reflect corpus origin, not absolute factual ground truth for every individual sentence. TruthLens AI classifies *textual styling and lexical patterns associated with these corpora*, not verified ontological truth.

---

## 4. Known Artifacts and Preprocessing Mitigations
1. **Reuters Dateline Leakage:** In raw data, nearly all articles in `True.csv` begin with a geographic dateline such as `WASHINGTON (Reuters) -` or `(Reuters) -`. Uncorrected models achieve 99%+ accuracy by trivial shortcut memorization of the word "Reuters".
   - *Mitigation:* `src/preprocessing.py` strips all regex-matched journalistic datelines (`^[A-Z\s,./\-_]+?\((?:Reuters|REUTERS)\)\s*[-—–]\s*`) prior to TF-IDF tokenization.
2. **Template Footers & Photo Credits:** Fake news articles frequently terminate with phrases such as `Photo by Andrew Burton/Getty Images` or `Featured image via...`.
   - *Mitigation:* Stripped via regex patterns in the cleaning pipeline.
3. **Exact Duplicates and Syndication:** Multiple articles appear verbatim or near-verbatim across different outlets.
   - *Mitigation:* Grouped into clusters using SimHash token prefix hashing to guarantee that duplicate or syndicated articles NEVER cross training, validation, and test splits.
4. **Conflicting Duplicate Texts:** If identical text appears under both `Fake.csv` and `True.csv`, both instances are discarded during the audit gate.

---

## 5. Scope and Limitations
- **Temporal Window:** Sourced from 2016–2017 US presidential election and early administration cycles.
- **Geographic & Topical Focus:** Predominantly US federal politics and international diplomacy.
- **Out-of-Distribution Warning:** Generalization to modern events (e.g., post-2020 events, specialized scientific papers, local news) is not guaranteed and requires uncertainty flags.
- **Non-English Texts:** The dataset is exclusively in English.

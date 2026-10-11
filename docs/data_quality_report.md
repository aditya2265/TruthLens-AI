# TruthLens AI — Data Quality Report

**Generated:** 2026-10-10T10:12:45.565714+00:00
**Dataset:** Fake and Real News Dataset (ISOT / Clement Bisaillon)
**Source:** [https://www.kaggle.com/datasets/clmentbisaillon/fake-and-real-news-dataset](https://www.kaggle.com/datasets/clmentbisaillon/fake-and-real-news-dataset)
**License:** CC0: Public Domain (as declared on Kaggle source)

---

## 1. Raw Dataset Overview
- **Total Raw Records:** 44898
- **Misleading Articles (Fake.csv):** 23481
- **Reliable Articles (True.csv):** 21417
- **Class Balance:** 52.3% Misleading / 47.7% Reliable
- **Missing / Empty Text Records:** 0

## 2. Text Length Distributions
- **Mean Character Length:** 2469.1 chars
- **Median Character Length:** 2186.0 chars
- **Mean Word Count:** 405.3 words
- **Misleading Class Mean Words:** 423.2 words
- **Reliable Class Mean Words:** 385.6 words

## 3. Deduplication and Group-Aware Audit
- **Initial Cleaned Rows:** 44898
- **Conflicting Label Duplicates Dropped:** 0 (0 unique text hashes)
- **Exact Duplicate Rows Grouped:** 10768
- **Unique Group Clusters (SimHash prefix):** 37862
- **Final Retained Rows for Splitting:** 44267

## 4. Known Artifacts & Preprocessing Mitigation
- **Dateline Leakage Risk:** In raw data, nearly all genuine news begins with `(Reuters) -`. If left uncleaned, classifiers learn the shortcut "contains Reuters => real" rather than actual writing patterns.
- **Mitigation Applied:** The cleaning pipeline regex-strips journalistic datelines (`^[A-Z\s,]+ \(Reuters\)\s*[-—]`) and template image credits before vectorization.
- **Temporal & Subject Boundaries:** Dataset reflects US political coverage from ~2016-2017. Scope limitations are explicitly displayed on the application dashboard.

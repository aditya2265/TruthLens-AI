"""Preprocessing, text cleaning, duplicate handling, and dataset splitting module for TruthLens AI.

Follows strict leakage prevention and reproducible data processing guidelines.
"""
import hashlib
import html
import re
from pathlib import Path
from typing import Any
import pandas as pd
import numpy as np
from sklearn.model_selection import StratifiedGroupKFold, train_test_split

from src.config import (
    FAKE_RAW_PATH,
    TRUE_RAW_PATH,
    LABEL_RELIABLE,
    LABEL_MISLEADING,
    RANDOM_STATE,
    TRAIN_SPLIT,
    VAL_SPLIT,
    TEST_SPLIT,
)


# Regex patterns for journalistic datelines and known publisher artifacts
# Real news in the ISOT / Clement Bisaillon dataset typically starts with:
# "WASHINGTON (Reuters) - ...", "MOSCOW (Reuters) - ...", "(Reuters) - "
REUTERS_DATELINE_PATTERN = re.compile(
    r"^(?:[A-Z\s,./\-_]+)?\((?:Reuters|REUTERS)\)\s*[-—–]\s*",
    re.IGNORECASE,
)

# Common editorial markers and photo credits found in datasets
PHOTO_CREDIT_PATTERN = re.compile(
    r"(?:(?:featured\s+)?image\s+via\s+[^.\n]+|photo\s+by\s+[^.\n]+|getty\s+images|21st\s+century\s+wire)",
    re.IGNORECASE,
)

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
WHITESPACE_PATTERN = re.compile(r"\s+")


def clean_text(text: Any, remove_datelines: bool = True) -> str:
    """Cleans a single article string with optional journalistic dateline stripping.

    Args:
        text: Input string or object.
        remove_datelines: If True, strips Reuters dateline headers to prevent
                          trivial shortcut learning.

    Returns:
        Cleaned, normalized string.
    """
    if text is None or pd.isna(text):
        return ""

    s = str(text)

    # Decode HTML entities and strip HTML tags
    s = html.unescape(s)
    s = HTML_TAG_PATTERN.sub(" ", s)

    # Strip datelines if requested (critical for ISOT dataset leakage prevention)
    if remove_datelines:
        s = REUTERS_DATELINE_PATTERN.sub("", s)
        s = PHOTO_CREDIT_PATTERN.sub("", s)

    # Normalize whitespace
    s = WHITESPACE_PATTERN.sub(" ", s).strip()
    return s


def load_raw_dataset(
    fake_path: Path | str = FAKE_RAW_PATH,
    true_path: Path | str = TRUE_RAW_PATH,
) -> pd.DataFrame:
    """Loads and combines raw Fake and True news CSV datasets.

    Assigns:
        LABEL_MISLEADING (1) to Fake.csv
        LABEL_RELIABLE (0) to True.csv

    Returns:
        Combined DataFrame with columns ['title', 'text', 'subject', 'date', 'label']

    Raises:
        FileNotFoundError: If either dataset file is missing.
        ValueError: If files lack expected text columns.
    """
    fake_p = Path(fake_path)
    true_p = Path(true_path)

    if not fake_p.exists():
        raise FileNotFoundError(f"Fake news dataset file not found at: {fake_p.resolve()}")
    if not true_p.exists():
        raise FileNotFoundError(f"True news dataset file not found at: {true_p.resolve()}")

    df_fake = pd.read_csv(fake_p)
    df_true = pd.read_csv(true_p)

    for name, df in [("Fake", df_fake), ("True", df_true)]:
        if "text" not in df.columns:
            raise ValueError(f"Dataset {name} missing required 'text' column. Found: {list(df.columns)}")

    df_fake["label"] = LABEL_MISLEADING
    df_fake["source_file"] = fake_p.name

    df_true["label"] = LABEL_RELIABLE
    df_true["source_file"] = true_p.name

    combined = pd.concat([df_fake, df_true], ignore_index=True)
    return combined


def compute_text_hash(text: str) -> str:
    """Generates MD5 hash for exact matching."""
    return hashlib.md5(text.encode("utf-8", errors="ignore")).hexdigest()


def compute_simhash_signature(text: str, n: int = 3) -> str:
    """Generates a fast n-gram token prefix signature for CPU-friendly near-duplicate clustering.

    Takes first 15 normalized word tokens to group syndicated or lightly edited articles.
    """
    words = re.findall(r"\b\w+\b", text.lower())
    if len(words) < 5:
        return "short_" + compute_text_hash(text)[:8]
    prefix = "_".join(words[:12])
    return hashlib.md5(prefix.encode("utf-8")).hexdigest()[:12]


def audit_and_deduplicate(
    df: pd.DataFrame,
    clean_datelines: bool = True,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Cleans text, audits duplicates, resolves conflicting labels, and assigns cluster groups.

    Duplicate handling rules:
    1. If identical text exists with CONFLICTING labels, discard all conflicting records
       (genuine ambiguity cannot be reliably supervised).
    2. Exact duplicate texts are retained as unique records but assigned a shared group_id
       so they never cross train/validation/test splits.
    3. Near-duplicate syndicated prefixes are assigned shared group_ids.
    """
    report: dict[str, Any] = {
        "initial_row_count": len(df),
        "missing_text_count": 0,
        "empty_text_after_clean_count": 0,
        "exact_duplicate_texts": 0,
        "conflicting_label_duplicates": 0,
        "conflicting_rows_dropped": 0,
        "final_retained_rows": 0,
        "unique_groups_count": 0,
    }

    work_df = df.copy()

    # Pre-clean text
    work_df["cleaned_text"] = work_df["text"].apply(lambda t: clean_text(t, remove_datelines=clean_datelines))

    # Detect missing or empty after cleaning
    missing_mask = work_df["cleaned_text"].str.strip().eq("") | work_df["cleaned_text"].isna()
    report["missing_text_count"] = int(missing_mask.sum())
    work_df = work_df[~missing_mask].copy()

    # Calculate exact duplicate hashes
    work_df["text_hash"] = work_df["cleaned_text"].apply(compute_text_hash)

    # Check for conflicting labels on exact duplicate texts
    label_counts_per_hash = work_df.groupby("text_hash")["label"].nunique()
    conflicting_hashes = label_counts_per_hash[label_counts_per_hash > 1].index

    report["conflicting_label_duplicates"] = len(conflicting_hashes)
    conflicting_mask = work_df["text_hash"].isin(conflicting_hashes)
    report["conflicting_rows_dropped"] = int(conflicting_mask.sum())

    if len(conflicting_hashes) > 0:
        work_df = work_df[~conflicting_mask].copy()

    # Count exact duplicates
    total_duplicates = work_df.duplicated(subset=["text_hash"], keep=False).sum()
    report["exact_duplicate_texts"] = int(total_duplicates)

    # Near-duplicate clustering by prefix simhash signature
    work_df["group_id"] = work_df["cleaned_text"].apply(compute_simhash_signature)

    report["final_retained_rows"] = len(work_df)
    report["unique_groups_count"] = int(work_df["group_id"].nunique())

    return work_df, report


def split_dataset(
    df: pd.DataFrame,
    train_ratio: float = TRAIN_SPLIT,
    val_ratio: float = VAL_SPLIT,
    test_ratio: float = TEST_SPLIT,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Splits data into train, val, and test sets.

    Ensures:
    1. Stratification by target label.
    2. Group-awareness (records with the same group_id stay in the same split to avoid leakage).
    """
    if not np.isclose(train_ratio + val_ratio + test_ratio, 1.0):
        raise ValueError("Train, val, and test ratios must sum to 1.0")

    # Group by group_id and aggregate label (majority label for group)
    group_summary = df.groupby("group_id")["label"].agg(lambda s: s.mode()[0]).reset_index()

    # Split groups into train_val and test
    test_size = test_ratio
    train_val_groups, test_groups = train_test_split(
        group_summary,
        test_size=test_size,
        stratify=group_summary["label"],
        random_state=random_state,
    )

    # Split train_val into train and val
    val_rel_size = val_ratio / (train_ratio + val_ratio)
    train_groups, val_groups = train_test_split(
        train_val_groups,
        test_size=val_rel_size,
        stratify=train_val_groups["label"],
        random_state=random_state,
    )

    train_df = df[df["group_id"].isin(train_groups["group_id"])].copy()
    val_df = df[df["group_id"].isin(val_groups["group_id"])].copy()
    test_df = df[df["group_id"].isin(test_groups["group_id"])].copy()

    return train_df, val_df, test_df

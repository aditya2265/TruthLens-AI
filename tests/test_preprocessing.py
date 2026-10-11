"""Unit and integration tests for dataset preprocessing and leakage prevention."""
import pytest
import pandas as pd
from src.preprocessing import (
    clean_text,
    audit_and_deduplicate,
    split_dataset,
    load_raw_dataset,
    compute_text_hash,
)
from src.config import LABEL_MISLEADING, LABEL_RELIABLE
from tests.fixtures import get_synthetic_raw_data


def test_clean_text_normalizes_and_removes_datelines():
    raw_sample = "WASHINGTON (Reuters) - The Senate voted 92-8 on Thursday. <p>Details inside &amp; more.</p>"
    cleaned = clean_text(raw_sample, remove_datelines=True)
    assert "(Reuters)" not in cleaned
    assert "<p>" not in cleaned
    assert "&amp;" not in cleaned
    assert cleaned.startswith("The Senate voted 92-8")


def test_clean_text_preserves_core_content():
    raw_sample = "A simple statement with normal words and punctuation."
    cleaned = clean_text(raw_sample, remove_datelines=True)
    assert cleaned == "A simple statement with normal words and punctuation."


def test_clean_text_handles_empty_and_none():
    assert clean_text(None) == ""
    assert clean_text("") == ""
    assert clean_text("   \n\t  ") == ""


def test_audit_and_deduplicate_with_conflicting_labels():
    # Construct synthetic test dataframe with duplicate text but CONFLICTING labels
    data = {
        "text": [
            "Identical claim about solar flare.",
            "Identical claim about solar flare.",  # same text, conflicting label
            "Unique reliable news article about astronomy.",
            "Unique misleading claim about lunar eclipse.",
        ],
        "label": [LABEL_RELIABLE, LABEL_MISLEADING, LABEL_RELIABLE, LABEL_MISLEADING],
        "title": ["Claim A", "Claim B", "News C", "News D"],
    }
    df = pd.DataFrame(data)
    deduped_df, report = audit_and_deduplicate(df)

    # The conflicting identical texts must be discarded
    assert report["conflicting_label_duplicates"] == 1
    assert report["conflicting_rows_dropped"] == 2
    assert len(deduped_df) == 2
    assert "Identical claim" not in deduped_df["cleaned_text"].values


def test_exact_duplicates_assigned_shared_group_id():
    data = {
        "text": [
            "Syndicated news dispatch verbatim copied across outlets.",
            "Syndicated news dispatch verbatim copied across outlets.",
            "Completely distinct article with different vocabulary.",
        ],
        "label": [LABEL_RELIABLE, LABEL_RELIABLE, LABEL_MISLEADING],
        "title": ["Copy 1", "Copy 2", "Distinct"],
    }
    df = pd.DataFrame(data)
    deduped_df, report = audit_and_deduplicate(df)

    assert report["exact_duplicate_texts"] == 2
    assert len(deduped_df) == 3
    # Both identical items must share the same group_id
    group_ids = deduped_df[deduped_df["cleaned_text"].str.contains("Syndicated")]["group_id"].unique()
    assert len(group_ids) == 1


def test_split_dataset_prevents_group_leakage():
    fake_df, true_df = get_synthetic_raw_data()
    fake_df["label"] = LABEL_MISLEADING
    true_df["label"] = LABEL_RELIABLE
    combined = pd.concat([fake_df, true_df], ignore_index=True)

    deduped, _ = audit_and_deduplicate(combined)
    train_df, val_df, test_df = split_dataset(deduped, train_ratio=0.6, val_ratio=0.2, test_ratio=0.2)

    # Verify splits do not share group_ids
    train_groups = set(train_df["group_id"])
    val_groups = set(val_df["group_id"])
    test_groups = set(test_df["group_id"])

    assert len(train_groups.intersection(val_groups)) == 0, "Leakage detected between train and val!"
    assert len(train_groups.intersection(test_groups)) == 0, "Leakage detected between train and test!"
    assert len(val_groups.intersection(test_groups)) == 0, "Leakage detected between val and test!"


def test_missing_dataset_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        load_raw_dataset("non_existent_fake.csv", "non_existent_true.csv")

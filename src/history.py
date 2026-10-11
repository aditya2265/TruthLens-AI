"""Local SQLite history storage for TruthLens AI.

Enforces:
- Local-only storage (no external transmission)
- Storing only length-limited excerpts (max 140 chars)
- Parameterized SQL queries
- Independent, non-blocking execution (history failure never blocks prediction)
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import DB_PATH, ENABLE_LOCAL_HISTORY


_DB_INITIALIZED: bool = False


def init_db(db_path: Path = DB_PATH) -> None:
    """Initializes the SQLite database schema and indexes if not already present."""
    global _DB_INITIALIZED
    if not ENABLE_LOCAL_HISTORY:
        return

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                predicted_label TEXT NOT NULL,
                predicted_class INTEGER NOT NULL,
                decision_score REAL,
                is_uncertain INTEGER NOT NULL,
                text_excerpt TEXT NOT NULL,
                model_version TEXT NOT NULL
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_id_desc ON analysis_history(id DESC)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_history_timestamp_desc ON analysis_history(timestamp DESC)
            """
        )
        conn.commit()
    _DB_INITIALIZED = True


def save_history_record(
    predicted_label: str,
    predicted_class: int,
    decision_score: float | None,
    is_uncertain: bool,
    text: str,
    model_version: str = "1.0.0",
    db_path: Path = DB_PATH,
) -> int | None:
    """Stores a single analysis record with truncated text excerpt."""
    if not ENABLE_LOCAL_HISTORY:
        return None

    try:
        if not _DB_INITIALIZED:
            init_db(db_path)
        # Store only length-limited excerpt to preserve user privacy
        clean_excerpt = " ".join(text.strip().split())
        excerpt = clean_excerpt[:120] + ("..." if len(clean_excerpt) > 120 else "")

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO analysis_history (
                    timestamp, predicted_label, predicted_class,
                    decision_score, is_uncertain, text_excerpt, model_version
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_str,
                    predicted_label,
                    predicted_class,
                    decision_score,
                    1 if is_uncertain else 0,
                    excerpt,
                    model_version,
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except Exception:
        # History errors must never break prediction
        return None


def get_recent_history(limit: int = 25, db_path: Path = DB_PATH) -> list[dict[str, Any]]:
    """Retrieves recent history records, ordered newest first."""
    if not ENABLE_LOCAL_HISTORY or not db_path.exists():
        return []

    try:
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, predicted_label, predicted_class,
                       decision_score, is_uncertain, text_excerpt, model_version
                FROM analysis_history
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def delete_history_record(record_id: int, db_path: Path = DB_PATH) -> bool:
    """Deletes a single history record by ID."""
    if not ENABLE_LOCAL_HISTORY or not db_path.exists():
        return False

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM analysis_history WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


def clear_all_history(db_path: Path = DB_PATH) -> bool:
    """Deletes all history records."""
    if not ENABLE_LOCAL_HISTORY or not db_path.exists():
        return False

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM analysis_history")
            conn.commit()
            return True
    except Exception:
        return False

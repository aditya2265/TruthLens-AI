"""Configuration module for TruthLens AI."""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATA_RAW_DIR = DATA_DIR / "raw"
DATA_PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = BASE_DIR / "models"
RESULTS_DIR = BASE_DIR / "results"
DOCS_DIR = BASE_DIR / "docs"

# Expected Raw Dataset Paths
FAKE_RAW_PATH = DATA_RAW_DIR / "Fake.csv"
TRUE_RAW_PATH = DATA_RAW_DIR / "True.csv"

# Processed Dataset Paths
CLEANED_DATA_PATH = DATA_PROCESSED_DIR / "cleaned_news.csv"
TRAIN_DATA_PATH = DATA_PROCESSED_DIR / "train.csv"
VAL_DATA_PATH = DATA_PROCESSED_DIR / "val.csv"
TEST_DATA_PATH = DATA_PROCESSED_DIR / "test.csv"

# Model & Evaluation Artifact Paths
PRIMARY_MODEL_PATH = MODELS_DIR / "truthlens_model.joblib"
MODEL_METADATA_PATH = MODELS_DIR / "model_metadata.json"
DATA_QUALITY_REPORT_PATH = RESULTS_DIR / "data_quality_report.json"
DATA_QUALITY_MD_PATH = DOCS_DIR / "data_quality_report.md"
EVALUATION_REPORT_PATH = RESULTS_DIR / "evaluation_report.json"
EVALUATION_MD_PATH = DOCS_DIR / "evaluation_report.md"
LEAKAGE_AUDIT_PATH = RESULTS_DIR / "leakage_audit.json"

# Database path for local history (SQLite)
DB_PATH = BASE_DIR / "instance" / "truthlens_history.sqlite3"

# Labels and Text Mappings
# In our binary classifier:
# 0 -> Reliable-style (from True.csv)
# 1 -> Misleading-style (from Fake.csv)
LABEL_RELIABLE = 0
LABEL_MISLEADING = 1

LABEL_NAMES = {
    LABEL_RELIABLE: "Reliable-style patterns",
    LABEL_MISLEADING: "Misleading-style patterns",
}

LABEL_EXPLANATIONS = {
    LABEL_RELIABLE: "Patterns associated with the dataset's reliable-news class.",
    LABEL_MISLEADING: "Patterns associated with the dataset's fake-news class.",
}

STANDARD_DISCLAIMER = (
    "This result is an automated text-classification assessment, not independent "
    "fact verification. The model can make mistakes and may reflect biases or limitations "
    "in its training data. Check important claims against reliable, independent sources."
)

# Text length constraints
MIN_INPUT_LENGTH = 15
MAX_INPUT_LENGTH = int(os.getenv("MAX_INPUT_LENGTH", "15000"))
MIN_WORD_COUNT = 3

# Model training parameters
RANDOM_STATE = 42
TRAIN_SPLIT = 0.70
VAL_SPLIT = 0.15
TEST_SPLIT = 0.15

# Flask application configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-insecure-key-truthlens-local-only-never-prod")
FLASK_ENV = os.getenv("FLASK_ENV", "production")
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
ENABLE_LOCAL_HISTORY = os.getenv("ENABLE_LOCAL_HISTORY", "true").lower() in ("true", "1", "yes")

# Google Fact Check Tools API configuration (Stage 4)
GOOGLE_FACTCHECK_API_KEY = os.getenv("GOOGLE_FACTCHECK_API_KEY", "").strip()

# Fallback news providers for live news feed (Stage 6)
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "").strip()
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip()

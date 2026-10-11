"""Language safety and detection module for TruthLens AI (Stage 5).

Ensures that the English-only classification model and lexical rules are only
invoked on supported English inputs. Accurately detects non-English text,
including Hindi in Devanagari script, non-Latin scripts, and non-English
Latin-script languages, failing safely when language is unsupported.
"""
import re
import unicodedata
from typing import TypedDict

UNSUPPORTED_LANGUAGE_MESSAGE = "Unable to assess: this model was trained on English news."

# Non-Latin Unicode script ranges
NON_LATIN_SCRIPTS = [
    ("Devanagari (Hindi)", 0x0900, 0x097F),
    ("Bengali", 0x0980, 0x09FF),
    ("Gurmukhi", 0x0A00, 0x0A7F),
    ("Gujarati", 0x0A80, 0x0AFF),
    ("Oriya", 0x0B00, 0x0B7F),
    ("Tamil", 0x0B80, 0x0BFF),
    ("Telugu", 0x0C00, 0x0C7F),
    ("Kannada", 0x0C80, 0x0CFF),
    ("Malayalam", 0x0D00, 0x0D7F),
    ("Sinhala", 0x0D80, 0x0DFF),
    ("Thai", 0x0E00, 0x0E7F),
    ("Lao", 0x0E80, 0x0EFF),
    ("Tibetan", 0x0F00, 0x0FFF),
    ("Burmese", 0x1000, 0x109F),
    ("Georgian", 0x10A0, 0x10FF),
    ("Ethiopic", 0x1200, 0x137F),
    ("Cherokee", 0x13A0, 0x13FF),
    ("Ogham", 0x1680, 0x169F),
    ("Runic", 0x16A0, 0x16FF),
    ("Khmer", 0x1780, 0x17FF),
    ("Mongolian", 0x1800, 0x18AF),
    ("Arabic", 0x0600, 0x06FF),
    ("Arabic Supplement", 0x0750, 0x077F),
    ("Cyrillic", 0x0400, 0x04FF),
    ("Greek", 0x0370, 0x03FF),
    ("Hebrew", 0x0590, 0x05FF),
    ("CJK (Chinese/Japanese)", 0x4E00, 0x9FFF),
    ("Hiragana", 0x3040, 0x309F),
    ("Katakana", 0x30A0, 0x30FF),
    ("Hangul (Korean)", 0xAC00, 0xD7AF),
]

# Most frequent English function words (stopwords)
COMMON_ENGLISH_WORDS = {
    "the", "be", "to", "of", "and", "a", "in", "that", "have", "i",
    "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her",
    "she", "or", "an", "will", "my", "one", "all", "would", "there",
    "their", "what", "so", "up", "out", "if", "about", "who", "get",
    "which", "go", "me", "when", "make", "can", "like", "time", "no",
    "just", "him", "know", "take", "people", "into", "year", "your",
    "good", "some", "could", "them", "see", "other", "than", "then",
    "now", "look", "only", "come", "its", "over", "think", "also",
    "back", "after", "use", "two", "how", "our", "work", "first",
    "well", "way", "even", "new", "want", "because", "any", "these",
    "give", "day", "most", "us", "is", "are", "was", "were", "been",
    "has", "had", "said", "did", "does", "where", "much", "before",
}

# Distinguishing function words for common Latin-script non-English languages
FOREIGN_STOPWORDS = {
    "hindi_romanized": {
        "hai", "hain", "ke", "ki", "ka", "ko", "se", "aur", "mein", "par",
        "yeh", "woh", "tha", "thi", "kya", "nahi", "nahin", "karna", "gaya",
        "rahe", "huye", "baat", "sarkar", "desh", "unhe", "usne", "unhone",
    },
    "spanish": {
        "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
        "en", "para", "por", "con", "que", "como", "su", "sus", "pero", "este",
        "esta", "estos", "estas", "porque", "cuando", "donde", "quien", "mas",
        "más", "sobre", "entre", "sin", "año", "años", "gobierno", "noticia",
    },
    "french": {
        "le", "la", "les", "un", "une", "des", "du", "de", "en", "pour",
        "dans", "avec", "sur", "qui", "que", "ce", "cette", "ces", "mais",
        "ou", "donc", "car", "est", "sont", "ont", "été", "fait", "faire",
        "plus", "tout", "tous", "comme", "gouvernement", "projet",
    },
    "german": {
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer",
        "eines", "einem", "einen", "und", "in", "von", "zu", "mit", "auf",
        "für", "ist", "sind", "war", "waren", "nicht", "auch", "als", "werden",
        "wird", "wurde", "über", "nach", "regierung", "bericht",
    },
    "italian": {
        "il", "lo", "la", "i", "gli", "le", "un", "uno", "una", "di",
        "del", "della", "dei", "delle", "a", "al", "allo", "alla", "agli",
        "alle", "da", "dal", "in", "nel", "nella", "con", "su", "per", "tra",
        "fra", "che", "non", "sono", "è", "notizia", "governo",
    },
    "portuguese": {
        "o", "a", "os", "as", "um", "uma", "uns", "umas", "de", "do",
        "da", "dos", "das", "em", "no", "na", "nos", "nas", "para", "por",
        "com", "que", "como", "mas", "ou", "se", "seu", "sua", "seus", "suas",
        "mais", "muito", "quando", "governo", "notícia",
    },
}


class LanguageCheckResult(TypedDict):
    is_english: bool
    detected_language: str
    reason: str
    message: str


def detect_language(text: str) -> LanguageCheckResult:
    """Evaluates whether the input text is supported English or non-English.

    Returns:
        LanguageCheckResult with is_english flag, detected language name,
        diagnostic reason, and exact user-facing message on failure.
    """
    if not text or not text.strip():
        return {
            "is_english": True,
            "detected_language": "empty",
            "reason": "Empty text provided.",
            "message": "",
        }

    raw = text.strip()

    # 1. Non-Latin script detection (Devanagari, Cyrillic, Arabic, CJK, etc.)
    non_latin_counts: dict[str, int] = {}
    total_letters = 0

    for char in raw:
        if unicodedata.category(char).startswith("L"):  # Is letter
            total_letters += 1
            cp = ord(char)
            for script_name, start, end in NON_LATIN_SCRIPTS:
                if start <= cp <= end:
                    non_latin_counts[script_name] = non_latin_counts.get(script_name, 0) + 1
                    break

    # If text contains non-Latin scripts:
    # E.g. Any Devanagari character, or > 10% non-Latin letters, or >= 3 non-Latin chars
    if non_latin_counts:
        top_script, count = max(non_latin_counts.items(), key=lambda x: x[1])
        if count >= 2 or (total_letters > 0 and (count / total_letters) > 0.10):
            return {
                "is_english": False,
                "detected_language": top_script,
                "reason": f"Non-Latin script detected: {top_script} ({count} characters)",
                "message": UNSUPPORTED_LANGUAGE_MESSAGE,
            }

    # 2. Tokenize Latin words
    words = [w.lower() for w in re.findall(r"\b[^\W\d_]+\b", raw, re.UNICODE)]
    if not words:
        # Numbers or symbols only
        return {
            "is_english": True,
            "detected_language": "symbols_only",
            "reason": "No alphabetic word tokens found.",
            "message": "",
        }

    total_words = len(words)

    # 3. Check for distinguishing non-English Latin stopwords
    for lang_name, stopwords in FOREIGN_STOPWORDS.items():
        matches = [w for w in words if w in stopwords]
        # If at least 3 foreign markers or >= 18% of word tokens match foreign stopwords
        if len(matches) >= 3 or (total_words >= 5 and (len(matches) / total_words) >= 0.18):
            return {
                "is_english": False,
                "detected_language": lang_name,
                "reason": f"Foreign vocabulary indicators detected ({lang_name}: {matches[:3]})",
                "message": UNSUPPORTED_LANGUAGE_MESSAGE,
            }

    # 4. English stopword frequency check on multi-word text
    # In standard English sentences with >= 5 words, common function words appear consistently.
    english_matches = [w for w in words if w in COMMON_ENGLISH_WORDS]
    if total_words >= 6 and len(english_matches) == 0:
        return {
            "is_english": False,
            "detected_language": "unknown_non_english",
            "reason": f"Text contains {total_words} words but zero common English function words.",
            "message": UNSUPPORTED_LANGUAGE_MESSAGE,
        }

    # 5. Passed language safety check
    return {
        "is_english": True,
        "detected_language": "en",
        "reason": f"Supported English text ({len(english_matches)} common English words matched).",
        "message": "",
    }

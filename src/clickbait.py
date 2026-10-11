"""Rules-based writing style and sensationalism analyzer for TruthLens AI.

DISCLAIMER & SEPARATION:
This is a transparent, rules-based heuristic indicator—NOT part of the machine-learning model.
Sensational wording does not prove falsehood, and neutral wording does not prove truthfulness.
This module never overrides or modifies the machine-learning prediction.
"""
import re
from typing import TypedDict


class RuleResult(TypedDict):
    rule_id: str
    name: str
    description: str
    triggered: bool
    evidence: list[str]
    explanation: str


class ClickbaitAnalysis(TypedDict):
    component_name: str
    disclaimer: str
    sensationalism_score: float  # 0.0 to 1.0 heuristic score
    risk_level: str  # Low, Moderate, Elevated
    rules_triggered_count: int
    total_rules: int
    rule_results: list[RuleResult]
    summary: str


# Documented lexicons of sensational, urgency, and absolute phrasing
SENSATIONAL_PHRASES = [
    r"\bshocking\b",
    r"\bunbelievable\b",
    r"\byou won't believe\b",
    r"\bwon't believe what\b",
    r"\bwill blow your mind\b",
    r"\bsecret plot\b",
    r"\bmiracle cure\b",
    r"\bwhat they don't want you to know\b",
    r"\bhidden truth\b",
    r"\bexposed\b",
    r"\bexplosive revelation\b",
    r"\bjaw-dropping\b",
    r"\bbombshell\b",
    r"\bpanic\b",
    r"\bterrified\b",
    r"\bmainstream media won't tell you\b",
    r"\bthey are lying to you\b",
]

URGENCY_CURIOSITY_PHRASES = [
    r"\bbreaking now\b",
    r"\burgent warning\b",
    r"\bshare before it's deleted\b",
    r"\bshare before it gets taken down\b",
    r"\bwatch before it's banned\b",
    r"\bsee this now\b",
    r"\beveryone needs to see this\b",
    r"\bdon't miss this\b",
    r"\bhurry\b",
]

ABSOLUTE_CLAIMS = [
    r"\b100% proven\b",
    r"\bundeniable proof\b",
    r"\babsolute fact\b",
    r"\bdestroys all\b",
    r"\bcures all\b",
    r"\bguaranteed to\b",
    r"\bnever seen before\b",
    r"\bconspiracy uncovered\b",
]


def check_excessive_caps(text: str) -> RuleResult:
    """Detects excessive uppercase letters across alphabetic characters."""
    alpha_chars = [c for c in text if c.isalpha()]
    if len(alpha_chars) < 20:
        return {
            "rule_id": "caps_ratio",
            "name": "Excessive Capitalization",
            "description": "High proportion of capitalized letters often used to grab attention.",
            "triggered": False,
            "evidence": [],
            "explanation": "Text too short to evaluate capitalization pattern reliably.",
        }

    caps = [c for c in alpha_chars if c.isupper()]
    ratio = len(caps) / len(alpha_chars)

    # Find full uppercase words of length >= 4
    words = re.findall(r"\b[A-Z]{4,}\b", text)
    # Ignore common news acronyms
    filtered_words = [w for w in words if w not in {"US", "USA", "UK", "UN", "NATO", "COVID", "NASA", "FBI", "CIA", "GOP", "DNC"}]

    triggered = ratio > 0.28 or len(filtered_words) >= 3
    evidence = filtered_words[:5]
    if ratio > 0.28 and not evidence:
        evidence = [f"{ratio*100:.1f}% uppercase characters"]

    return {
        "rule_id": "caps_ratio",
        "name": "Excessive Capitalization",
        "description": "High proportion of capitalized letters often used to grab attention.",
        "triggered": triggered,
        "evidence": evidence,
        "explanation": f"Uppercase letter ratio is {ratio*100:.1f}%. Capitalizing full words is a common sensationalist formatting cue.",
    }


def check_excessive_punctuation(text: str) -> RuleResult:
    """Detects repeated exclamation points, question marks, or interrobangs."""
    patterns = re.findall(r"([!?]{2,})", text)
    single_exclamations = text.count("!")

    triggered = len(patterns) >= 1 or single_exclamations >= 3
    evidence = patterns[:5]
    if not evidence and single_exclamations >= 3:
        evidence = [f"{single_exclamations} exclamation marks"]

    return {
        "rule_id": "repeated_punctuation",
        "name": "Repeated Punctuation",
        "description": "Multiple consecutive exclamation marks or question marks (e.g., '!!!', '?!').",
        "triggered": triggered,
        "evidence": evidence,
        "explanation": "Frequent or repeated exclamation/question marks convey artificial urgency or emotion rather than measured reporting.",
    }


def check_sensational_phrases(text: str) -> RuleResult:
    """Detects documented sensational or inflammatory phrases."""
    found = []
    text_lower = text.lower()
    for pattern in SENSATIONAL_PHRASES:
        matches = re.findall(pattern, text_lower)
        if matches:
            found.extend(matches)

    triggered = len(found) > 0
    return {
        "rule_id": "sensational_phrases",
        "name": "Sensational Phrasing",
        "description": "Emotionally provocative phrases designed to evoke shock or outrage.",
        "triggered": triggered,
        "evidence": list(set(found))[:5],
        "explanation": "Sensational phrases are frequently employed in clickbait to elicit impulsive sharing.",
    }


def check_urgency_curiosity(text: str) -> RuleResult:
    """Detects urgency or curiosity bait designed to manipulate user sharing."""
    found = []
    text_lower = text.lower()
    for pattern in URGENCY_CURIOSITY_PHRASES:
        matches = re.findall(pattern, text_lower)
        if matches:
            found.extend(matches)

    triggered = len(found) > 0
    return {
        "rule_id": "urgency_curiosity",
        "name": "Urgency & Curiosity Bait",
        "description": "Calls-to-action urging immediate sharing or warning of impending censorship.",
        "triggered": triggered,
        "evidence": list(set(found))[:5],
        "explanation": "Urging readers to share before deletion is a classic social media engagement trap.",
    }


def check_unsupported_absolutes(text: str) -> RuleResult:
    """Detects exaggerated absolute claims."""
    found = []
    text_lower = text.lower()
    for pattern in ABSOLUTE_CLAIMS:
        matches = re.findall(pattern, text_lower)
        if matches:
            found.extend(matches)

    triggered = len(found) > 0
    return {
        "rule_id": "absolute_claims",
        "name": "Absolute & Exaggerated Claims",
        "description": "Totalizing assertions such as '100% proven' or 'destroys all'.",
        "triggered": triggered,
        "evidence": list(set(found))[:5],
        "explanation": "Rigorous reporting typically includes nuance, caveats, and attribution rather than sweeping absolute guarantees.",
    }


def analyze_writing_style(text: str) -> ClickbaitAnalysis:
    """Runs all rules-based detectors and produces a transparent summary.

    This analysis is completely independent of the statistical machine learning model.
    """
    if not text or not text.strip():
        return {
            "component_name": "Rules-based Writing Style Analysis",
            "disclaimer": "Rules-based writing signal—not part of the machine-learning model. Sensational style does not prove falsehood.",
            "sensationalism_score": 0.0,
            "risk_level": "None",
            "rules_triggered_count": 0,
            "total_rules": 5,
            "rule_results": [],
            "summary": "No text provided for writing style analysis.",
        }

    rules = [
        check_excessive_caps(text),
        check_excessive_punctuation(text),
        check_sensational_phrases(text),
        check_urgency_curiosity(text),
        check_unsupported_absolutes(text),
    ]

    triggered_count = sum(1 for r in rules if r["triggered"])
    total_rules = len(rules)
    score = triggered_count / total_rules

    if triggered_count >= 3:
        risk_level = "Elevated"
        summary = "Multiple sensationalist writing markers detected (e.g. dramatic phrasing, excessive punctuation, or capitalization)."
    elif triggered_count >= 1:
        risk_level = "Moderate"
        summary = "Some informal or emotional writing cues detected, but within moderate limits."
    else:
        risk_level = "Low"
        summary = "Writing appears measured, with conventional punctuation and low sensationalist framing."

    return {
        "component_name": "Rules-based Writing Style Analysis",
        "disclaimer": "Rules-based writing signal—not part of the machine-learning model. Sensational style does not prove falsehood.",
        "sensationalism_score": round(score, 2),
        "risk_level": risk_level,
        "rules_triggered_count": triggered_count,
        "total_rules": total_rules,
        "rule_results": rules,
        "summary": summary,
    }

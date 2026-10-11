"""Unit tests for the rules-based clickbait & writing style analyzer."""
from src.clickbait import (
    analyze_writing_style,
    check_excessive_caps,
    check_excessive_punctuation,
    check_sensational_phrases,
    check_urgency_curiosity,
    check_unsupported_absolutes,
)


def test_empty_and_short_text():
    empty_result = analyze_writing_style("")
    assert empty_result["risk_level"] == "None"
    assert empty_result["rules_triggered_count"] == 0

    short_caps = check_excessive_caps("HI THERE")
    # Should not trigger on overly short snippet
    assert not short_caps["triggered"]


def test_caps_rule():
    screaming_text = "THIS IS AN EXTREMELY URGENT WARNING TO ALL CITIZENS ACROSS THE WORLD RIGHT NOW"
    result = check_excessive_caps(screaming_text)
    assert result["triggered"]
    assert len(result["evidence"]) > 0

    normal_text = "The Federal Reserve raised interest rates by a quarter percentage point on Wednesday afternoon."
    normal_result = check_excessive_caps(normal_text)
    assert not normal_result["triggered"]


def test_punctuation_rule():
    sensational_punct = "Unbelievable discovery announced today! Could this be true?! Look at this now!!!"
    result = check_excessive_punctuation(sensational_punct)
    assert result["triggered"]

    calm_punct = "The committee held a hearing on Wednesday. Three witnesses were called to testify."
    calm_result = check_excessive_punctuation(calm_punct)
    assert not calm_result["triggered"]


def test_sensational_phrases():
    sensational_text = "Scientists find shocking miracle cure that will blow your mind and uncover the secret plot."
    result = check_sensational_phrases(sensational_text)
    assert result["triggered"]
    assert any("miracle cure" in item or "shocking" in item for item in result["evidence"])

    measured_text = "Scientists published their peer-reviewed findings in the medical journal on Tuesday."
    assert not check_sensational_phrases(measured_text)["triggered"]


def test_urgency_and_curiosity():
    urgent_text = "Share before it's deleted! Breaking now: everyone needs to see this video immediately!"
    result = check_urgency_curiosity(urgent_text)
    assert result["triggered"]

    standard_text = "The full report was released on the public agency website for citizen review."
    assert not check_urgency_curiosity(standard_text)["triggered"]


def test_unsupported_absolutes():
    absolute_text = "This is 100% proven and undeniable proof that cures all diseases without failure."
    result = check_unsupported_absolutes(absolute_text)
    assert result["triggered"]

    hedged_text = "Initial preliminary data suggests potential benefits, though further clinical trials are needed."
    assert not check_unsupported_absolutes(hedged_text)["triggered"]


def test_overall_analysis_separation_and_disclaimer():
    clean_article = (
        "WASHINGTON - The Senate passed a bipartisan highway funding authorization bill by a wide margin on Thursday. "
        "The legislation provides federal grants for bridge repairs, road maintenance, and railway infrastructure."
    )
    res = analyze_writing_style(clean_article)
    assert res["risk_level"] == "Low"
    assert "not part of the machine-learning model" in res["disclaimer"]
    assert res["rules_triggered_count"] == 0

    sensational_article = (
        "SHOCKING MIRACLE CURE EXPOSED!!! Share before it's deleted! "
        "This 100% proven discovery destroys all known infections and mainstream media won't tell you!"
    )
    res_sensational = analyze_writing_style(sensational_article)
    assert res_sensational["risk_level"] == "Elevated"
    assert res_sensational["rules_triggered_count"] >= 3

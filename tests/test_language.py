"""Stage 5 tests: Language safety and non-English text isolation for TruthLens AI.

Verifies:
1. Standard English text passes through to the classifier.
2. Hindi (Devanagari) returns exactly: "Unable to assess: this model was trained on English news."
3. Non-English URL-extracted text is not classified.
4. The model pipeline (load_model / inference) is NOT invoked for unsupported text (proven via mock).
5. Empty, very short, mixed-language, and ambiguous text are handled safely.
6. Flask web UI and JSON API endpoints correctly handle non-English submissions.
"""
import json
from unittest.mock import patch, MagicMock
import pytest

from src.language import detect_language, UNSUPPORTED_LANGUAGE_MESSAGE
from src.predict import predict_text, predict_url
from src.app import app


# ---------------------------------------------------------------------------
# Unit Tests: detect_language
# ---------------------------------------------------------------------------

def test_detect_language_standard_english():
    sample = "The Department of Energy announced new investments in clean energy research on Tuesday."
    res = detect_language(sample)
    assert res["is_english"] is True
    assert res["detected_language"] == "en"
    assert res["message"] == ""


def test_detect_language_hindi_devanagari():
    hindi_sample = "भारत सरकार ने किसानों के लिए एक नई योजना की घोषणा की है।"
    res = detect_language(hindi_sample)
    assert res["is_english"] is False
    assert "Devanagari" in res["detected_language"]
    assert res["message"] == UNSUPPORTED_LANGUAGE_MESSAGE
    assert res["message"] == "Unable to assess: this model was trained on English news."


def test_detect_language_other_non_latin_scripts():
    # Russian (Cyrillic)
    cyrillic_sample = "Президент объявил о новом плане развития экономики страны."
    res_ru = detect_language(cyrillic_sample)
    assert res_ru["is_english"] is False
    assert "Cyrillic" in res_ru["detected_language"]
    assert res_ru["message"] == UNSUPPORTED_LANGUAGE_MESSAGE

    # Arabic
    arabic_sample = "أعلنت وزارة الصحة عن خطة جديدة للرعاية الطبية في جميع المستشفيات"
    res_ar = detect_language(arabic_sample)
    assert res_ar["is_english"] is False
    assert "Arabic" in res_ar["detected_language"]
    assert res_ar["message"] == UNSUPPORTED_LANGUAGE_MESSAGE

    # Chinese
    cjk_sample = "国家航天局宣布成功发射新一代地球观测卫星并进入预定轨道"
    res_zh = detect_language(cjk_sample)
    assert res_zh["is_english"] is False
    assert "CJK" in res_zh["detected_language"]
    assert res_zh["message"] == UNSUPPORTED_LANGUAGE_MESSAGE


def test_detect_language_foreign_latin_scripts():
    # Spanish
    spanish_sample = "El gobierno de España anunció una nueva política económica para ayudar a los ciudadanos en el país."
    res_es = detect_language(spanish_sample)
    assert res_es["is_english"] is False
    assert res_es["detected_language"] == "spanish"
    assert res_es["message"] == UNSUPPORTED_LANGUAGE_MESSAGE

    # French
    french_sample = "Le président de la République a annoncé une nouvelle loi avec le gouvernement pour les citoyens."
    res_fr = detect_language(french_sample)
    assert res_fr["is_english"] is False
    assert res_fr["detected_language"] == "french"
    assert res_fr["message"] == UNSUPPORTED_LANGUAGE_MESSAGE

    # Romanized Hindi
    romanized_hindi = "Yeh ek bahut badi khabar hai aur sarkar ne naya niyam desh mein banaya hai."
    res_hi = detect_language(romanized_hindi)
    assert res_hi["is_english"] is False
    assert res_hi["detected_language"] == "hindi_romanized"
    assert res_hi["message"] == UNSUPPORTED_LANGUAGE_MESSAGE


def test_detect_language_empty_and_whitespace():
    res_empty = detect_language("")
    assert res_empty["is_english"] is True
    assert res_empty["detected_language"] == "empty"

    res_spaces = detect_language("   \n\t   ")
    assert res_spaces["is_english"] is True
    assert res_spaces["detected_language"] == "empty"


def test_detect_language_very_short_text():
    # Brief phrases should not crash and pass safe language check
    res_short = detect_language("Breaking news")
    assert res_short["is_english"] is True

    res_single = detect_language("Headline")
    assert res_single["is_english"] is True


def test_detect_language_symbols_and_numbers():
    res_sym = detect_language("12345 67890 9999 $$$ %%%")
    assert res_sym["is_english"] is True
    assert res_sym["detected_language"] == "symbols_only"


def test_detect_language_mixed_devanagari_and_english():
    # English text with significant Devanagari content
    mixed = "Breaking news: भारत सरकार ने नया फैसला लागू किया regarding international trade."
    res = detect_language(mixed)
    assert res["is_english"] is False
    assert "Devanagari" in res["detected_language"]
    assert res["message"] == UNSUPPORTED_LANGUAGE_MESSAGE


def test_detect_language_english_with_borrowed_word():
    # English sentence containing a lone loanword should pass as English
    loanword_sample = "The diplomatic delegation enjoyed tacos and guacamole during their official summit in Austin."
    res = detect_language(loanword_sample)
    assert res["is_english"] is True


# ---------------------------------------------------------------------------
# Integration Tests: predict_text & predict_url
# ---------------------------------------------------------------------------

def test_predict_text_english_passes_through_to_classifier():
    article = (
        "The Federal Reserve committee voted unanimously to maintain the benchmark lending rate on Wednesday. "
        "Economic analysts expect stable mortgage rates for the remainder of the quarter."
    )
    result = predict_text(article, search_factchecks=False)
    assert result["status"] == "success"
    assert "predicted_label" in result
    assert result["predicted_label"] is not None
    assert "decision_score" in result
    assert result["decision_score"] is not None
    assert result["explanation"] is not None


def test_predict_text_hindi_returns_exact_message_and_no_verdict():
    hindi_text = "अंतरिक्ष एजेंसी ने आज एक नए उपग्रह के सफल प्रक्षेपण की पुष्टि की है।"
    result = predict_text(hindi_text, search_factchecks=False)

    assert result["status"] == "unsupported_language"
    assert result["message"] == "Unable to assess: this model was trained on English news."
    assert result["message"] == UNSUPPORTED_LANGUAGE_MESSAGE

    # Must contain NO verdict, NO confidence score, and NO fake/real label
    assert result["predicted_label"] is None
    assert result["verdict"] is None
    assert result["confidence_score"] is None
    assert result["decision_score"] is None
    assert result["prob_reliable"] is None
    assert result["prob_misleading"] is None
    assert result["clickbait_analysis"] is None
    assert result["explanation"] is None

    # Must indicate this is not a verdict on claim veracity
    assert "not a verdict" in result["notice"].lower()


def test_predict_text_mock_proves_model_not_invoked_on_unsupported_language():
    hindi_text = "मुख्य न्यायाधीश ने अदालत में नए दिशानिर्देश जारी किए।"
    with patch("src.predict.load_model") as mock_load, patch("src.predict.analyze_writing_style") as mock_style:
        result = predict_text(hindi_text, search_factchecks=False)

        assert result["status"] == "unsupported_language"
        assert result["message"] == "Unable to assess: this model was trained on English news."
        # PROVE the ML classifier and writing style rules were NEVER called
        mock_load.assert_not_called()
        mock_style.assert_not_called()


def test_predict_url_non_english_extracted_text_not_classified():
    mock_extraction = {
        "status": "success",
        "message": "Successfully extracted main article text.",
        "url": "https://hindi.example.com/news/123",
        "source_domain": "hindi.example.com",
        "extracted_title": "सरकार का बड़ा फैसला",
        "extracted_text": "सरकार ने ग्रामीण विकास के लिए कई महत्वपूर्ण योजनाओं को मंजूरी दी है और बजट जारी किया।",
        "extracted_excerpt": "सरकार ने ग्रामीण विकास के लिए...",
        "publication_date": "2026-10-10",
        "fetch_notice": "Extracted article from hindi.example.com",
    }

    with patch("src.url_fetcher.fetch_and_extract_url", return_value=mock_extraction), \
         patch("src.predict.load_model") as mock_load:

        result = predict_url("https://hindi.example.com/news/123")

        assert result["status"] == "unsupported_language"
        assert result["message"] == "Unable to assess: this model was trained on English news."
        assert result["predicted_label"] is None
        assert result["decision_score"] is None

        # URL metadata must be preserved
        assert "url_metadata" in result
        assert result["url_metadata"]["source_domain"] == "hindi.example.com"
        assert result["url_metadata"]["extracted_title"] == "सरकार का बड़ा फैसला"

        # Model classifier MUST NOT be invoked
        mock_load.assert_not_called()


def test_predict_text_empty_input_handled_safely():
    result = predict_text("   ")
    assert result["status"] == "error"
    assert result["error_type"] == "empty_input"


def test_predict_text_very_short_english_handled_safely():
    result = predict_text("Just in", search_factchecks=False)
    # Does not crash, handles brief input safely and attaches brevity quality warning
    assert result["status"] == "success"
    assert any("short" in str(w).lower() for w in result.get("quality_warnings", []))


# ---------------------------------------------------------------------------
# Flask Route & UI Tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client(tmp_path):
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as c:
        yield c


def test_flask_predict_hindi_text_renders_safe_ui(client):
    hindi_text = "भारत ने अपने नए अंतरिक्ष मिशन की सफलता की घोषणा की।"
    response = client.post("/predict", data={"news_text": hindi_text})

    assert response.status_code == 200
    content = response.data.decode("utf-8")

    # Exact message must be present
    assert "Unable to assess: this model was trained on English news." in content

    # Note that this is not a verdict about the claim
    assert "not a verdict" in content.lower()

    # Must NOT contain fake/real labels or decision scores
    assert "Reliable-style patterns" not in content
    assert "Misleading-style patterns" not in content
    assert "Model decision score" not in content


def test_flask_api_predict_hindi_text_returns_200_and_exact_message(client):
    payload = {"text": "प्रधानमंत्री ने नई परियोजना का उद्घाटन किया और भाषण दिया।"}
    response = client.post("/api/predict", json=payload)

    assert response.status_code == 200
    data = json.loads(response.data)

    assert data["status"] == "unsupported_language"
    assert data["message"] == "Unable to assess: this model was trained on English news."
    assert data["predicted_label"] is None
    assert data["confidence_score"] is None
    assert data["decision_score"] is None


def test_flask_api_predict_url_hindi_text_returns_200(client):
    mock_extraction = {
        "status": "success",
        "message": "Successfully extracted main article text.",
        "url": "https://hindi.example.com/news/456",
        "source_domain": "hindi.example.com",
        "extracted_title": "नई शिक्षा नीति की समीक्षा",
        "extracted_text": "शिक्षा मंत्रालय ने देश भर के स्कूलों के लिए नई नीति की समीक्षा बैठक आयोजित की।",
        "extracted_excerpt": "शिक्षा मंत्रालय ने देश भर के...",
        "publication_date": "2026-10-10",
        "fetch_notice": "Extracted article from hindi.example.com",
    }

    with patch("src.url_fetcher.fetch_and_extract_url", return_value=mock_extraction):
        payload = {"url": "https://hindi.example.com/news/456"}
        response = client.post("/api/predict", json=payload)

        assert response.status_code == 200
        data = json.loads(response.data)

        assert data["status"] == "unsupported_language"
        assert data["message"] == "Unable to assess: this model was trained on English news."
        assert data["url_metadata"]["source_domain"] == "hindi.example.com"

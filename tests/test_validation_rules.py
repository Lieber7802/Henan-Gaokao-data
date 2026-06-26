from scripts.validate_pilot import normalize_numeric_text, parse_application_line, validate_score_row


def test_normalize_numeric_text_fixes_common_ocr_confusions():
    assert normalize_numeric_text("1O3") == "103"
    assert normalize_numeric_text("5B7") == "587"
    assert normalize_numeric_text("l25") == "125"
    assert normalize_numeric_text("4D0") == "400"


def test_validate_score_row_accepts_consistent_application_row():
    row = {
        "year": "2024",
        "batch": "本科二批",
        "min_score": "503",
        "score_diff": "107",
    }
    result = validate_score_row(row)
    assert result["review_status"] == "auto_pass"


def test_validate_score_row_flags_wrong_diff():
    row = {
        "year": "2024",
        "batch": "本科二批",
        "min_score": "503",
        "score_diff": "999",
    }
    result = validate_score_row(row)
    assert result["review_status"] == "needs_review"
    assert "score_diff_mismatch" in result["issues"]


def test_parse_application_line_extracts_core_numeric_fields():
    parsed = parse_application_line("首都体育学院 2024 7 7 503 102 100 0 107 142935")
    assert parsed["year"] == "2024"
    assert parsed["min_score"] == "503"
    assert parsed["score_diff"] == "107"
    assert parsed["rank"] == "142935"

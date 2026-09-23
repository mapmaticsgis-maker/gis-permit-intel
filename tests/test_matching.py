from scripts.report_audit.matching import match_candidate, normalize, alnum_tokens, digit_signature


def test_normalize_strips_separators_and_uppercases():
    assert normalize("LA-CAD_2216N13W") == "LACAD2216N13W"


def test_digit_signature_concatenates_digits_in_order():
    assert digit_signature("LA-CAD_2216N13W") == "221613"
    assert digit_signature("22-16N-13W") == "221613"


def test_alnum_tokens_excludes_short_and_stopwords():
    tokens = alnum_tokens("LA-CAD_UNIT59_ABSTATUS")
    assert "UNIT" not in tokens  # stopword
    assert "ABSTATUS" in tokens
    assert "LA" not in tokens  # below length-3 minimum


def test_match_candidate_exact_when_basename_is_literal_substring():
    result = match_candidate("LA-CAD_2216N13W", "20260922-LA-CAD_2216N13W-NEWTRACTS.pdf")
    assert result["confidence"] == "Exact"


def test_match_candidate_token_when_only_digit_signature_overlaps():
    result = match_candidate("LA-CAD_2216N13W", "22-16N-13W - Unit Survey update (1).xlsx")
    assert result is not None
    assert result["confidence"] == "Token"


def test_match_candidate_token_when_only_alpha_token_overlaps():
    result = match_candidate("TX-SHELBY-LEASE_STATUS", "20260917_TX-SHELBY-MINERAL_TRACTS.pdf")
    assert result is not None
    assert result["confidence"] == "Token"
    assert "SHELBY" in result["matched_tokens"]


def test_match_candidate_none_when_unrelated():
    assert match_candidate("LA-CAD_2216N13W", "invoice_1740252.pdf") is None


def test_match_candidate_none_for_short_digit_signature_no_alpha_overlap():
    # mxd with a short digit run shouldn't false-positive-match on digits alone
    assert match_candidate("LA-CAD_UNIT59_ABSTATUS", "invoice_1740252.pdf") is None

from benchmark import metrics


def test_numeric_exact_match_preserves_leading_zero_and_counts_duplicates():
    result = metrics('தமிழ் 001', 'தமிழ் 001 012', ['001','001','12'])
    assert result['numeric_matches'] == 1
    assert result['numeric_total'] == 3


def test_error_counts():
    result = metrics('abc def','abc deg',[])
    assert result['character_errors'] == 1
    assert result['word_errors'] == 1

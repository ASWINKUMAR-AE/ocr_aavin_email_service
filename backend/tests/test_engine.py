import pytest
from app.services.ocr_engine import normalize_result


def test_alignment_unicode_and_original_coordinates():
    result = {'rec_texts': ['தமிழ்', '000000000001'], 'rec_scores': [.81, .2],
              'rec_polys': [[[10,20],[50,20],[50,40],[10,40]], [[1,2],[5,2],[5,4],[1,4]]]}
    lines = normalize_result(result, 2, 2, 3)
    assert lines[0]['raw_text'] == '000000000001'
    assert lines[1]['raw_text'] == 'தமிழ்'
    assert lines[1]['polygon'][0] == [20,60]
    assert lines[0]['page_index'] == 2
    assert lines[0]['corrected_text'] is None
    assert not lines[0]['reviewed']


def test_misaligned_result_is_rejected():
    with pytest.raises(ValueError):
        normalize_result({'rec_texts':['a'], 'rec_scores':[], 'rec_polys':[]}, 0)


def test_empty_result():
    assert normalize_result({'rec_texts':[], 'rec_scores':[], 'rec_polys':[]}, 0) == []

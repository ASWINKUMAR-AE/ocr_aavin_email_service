from app.services.layout import order_document, text_for_page, visual_rows


def line(identifier, x, y, text='sample', w=70, h=20, page=0):
    return dict(id=identifier, polygon=[[x,y],[x+w,y],[x+w,y+h],[x,y+h]], raw_text=text,
                corrected_text=None, confidence=.95, reviewed=False, page_index=page, reading_order=0)


def test_rows_tolerate_handwriting_baseline_jitter_without_interleaving():
    lines = [line('right',200,98,'0123456789'),line('left',20,105,'தமிழ்'),line('next',20,140,'next row')]
    assert [[l['id'] for l in row] for row in visual_rows(lines)] == [['left','right'],['next']]
    assert text_for_page(lines) == 'தமிழ்\t0123456789\nnext row'


def test_existing_region_ids_and_corrections_survive_reordering():
    a,b = line('0:18',20,105), line('0:9',200,98)
    a['corrected_text'] = ''
    doc = order_document({'pages':[{'index':0}], 'lines':[b,a]})
    assert [l['id'] for l in doc['lines']] == ['0:18','0:9']
    assert [l['reading_order'] for l in doc['lines']] == [0,1]
    assert a['corrected_text'] == ''
    assert a['row_index'] == b['row_index'] == 0

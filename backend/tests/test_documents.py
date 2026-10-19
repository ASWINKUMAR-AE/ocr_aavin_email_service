import io
import pytest
from PIL import Image
from app.services import documents


def test_pdf_pages_and_limit(tmp_path, monkeypatch):
    path = tmp_path / 'source.pdf'
    image = Image.new('RGB', (100,100), 'white')
    image.save(path, save_all=True, append_images=[image], format='PDF')
    pages = documents.decode_pages(path, tmp_path)
    assert len(pages) == 2
    assert pages[1]['index'] == 1
    monkeypatch.setattr(documents, 'MAX_PAGES', 1)
    with pytest.raises(ValueError):
        documents.decode_pages(path, tmp_path)


def test_pixel_limit_before_decode(tmp_path, monkeypatch):
    path = tmp_path / 'source.png'
    Image.new('RGB',(20,20)).save(path)
    monkeypatch.setattr(documents, 'MAX_PIXELS', 100)
    with pytest.raises(ValueError):
        documents.decode_pages(path, tmp_path)

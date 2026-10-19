"""Real model smoke test. Prints only synthetic fixture output and package metadata."""
import inspect
import json
import os
import sys
import time
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'

from make_fixture import make_fixture
from app.services.documents import inference_image
from app.services.ocr_engine import OCREngine
from app.runtime import configure_offline_runtime


def main():
    configure_offline_runtime()
    from paddleocr import PaddleOCR
    installed = {name: version(name) for name in ('paddleocr', 'paddlex', 'paddlepaddle', 'numpy')}
    print(json.dumps(installed))
    signature = inspect.signature(PaddleOCR.__init__)
    for argument in ('text_recognition_model_name', 'text_detection_model_dir', 'use_doc_unwarping'):
        assert argument in signature.parameters, argument
    assert hasattr(PaddleOCR, 'predict')
    fixture = ROOT / 'backend/tests/fixtures/synthetic-bilingual.png'
    if not fixture.exists():
        fixture = make_fixture()
    image, sx, sy = inference_image(fixture)
    engine = OCREngine()
    started = time.perf_counter()
    lines = engine.recognize(image, 0, sx, sy)
    assert lines, 'OCR returned no lines'
    assert any(any('\u0b80' <= c <= '\u0bff' for c in line['raw_text']) for line in lines), 'No Tamil recognized'
    assert any(any(c.isascii() and c.isalpha() for c in line['raw_text']) for line in lines), 'No English recognized'
    report = dict(packages=installed, seconds=round(time.perf_counter() - started, 3), lines=lines,
                  fixture='synthetic printed text; does not measure handwriting accuracy')
    (ROOT / 'data').mkdir(exist_ok=True)
    (ROOT / 'data/smoke-result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True, indent=2))


if __name__ == '__main__':
    main()

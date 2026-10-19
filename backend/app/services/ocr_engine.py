"""Explicit PaddleOCR 3.x adapter. No network/model downloads during app use."""
import os
import threading
import math

from app.config import MODELS, DETECTOR, RECOGNIZER, CPU_THREADS
from app.runtime import configure_offline_runtime
from app.services.layout import visual_rows


def normalize_result(result, page_index, scale_x=1.0, scale_y=1.0):
    texts = result['rec_texts']
    scores = result['rec_scores']
    polygons = result['rec_polys']
    if not (len(texts) == len(scores) == len(polygons)):
        raise ValueError('Incompatible OCR result arrays')
    lines = []
    for text, score, polygon in zip(texts, scores, polygons):
        points = [[float(x) * scale_x, float(y) * scale_y] for x, y in polygon]
        if len(points) != 4 or not all(math.isfinite(v) for p in points for v in p):
            raise ValueError('Invalid OCR polygon')
        confidence = float(score)
        if not math.isfinite(confidence) or not 0 <= confidence <= 1:
            raise ValueError('Invalid OCR confidence')
        lines.append(dict(raw_text=str(text), corrected_text=None, confidence=confidence,
                          polygon=points, page_index=page_index, reviewed=False))
    lines = [line for group in visual_rows(lines) for line in group]
    for order, line in enumerate(lines):
        line.update(id=f'{page_index}:{order}', reading_order=order)
    return lines


class OCREngine:
    def __init__(self):
        self._pipeline = None
        self._lock = threading.Lock()

    def load(self):
        if self._pipeline is not None:
            return self._pipeline
        for name in (DETECTOR, RECOGNIZER):
            folder = MODELS / name
            if not all((folder / file).is_file() for file in ('inference.json', 'inference.pdiparams', 'inference.yml')):
                raise RuntimeError('Local OCR models missing. Run scripts/cache_models.py during installation.')
        configure_offline_runtime()
        from paddleocr import PaddleOCR
        self._pipeline = PaddleOCR(
            text_detection_model_name=DETECTOR,
            text_detection_model_dir=str(MODELS / DETECTOR),
            text_recognition_model_name=RECOGNIZER,
            text_recognition_model_dir=str(MODELS / RECOGNIZER),
            use_doc_orientation_classify=False, use_doc_unwarping=False,
            use_textline_orientation=False, device='cpu', cpu_threads=CPU_THREADS,
            enable_mkldnn=False, text_recognition_batch_size=1,
            text_det_limit_side_len=1280, text_det_limit_type='max',
            text_rec_score_thresh=0.0,
        )
        return self._pipeline

    def recognize(self, image, page_index, scale_x=1.0, scale_y=1.0):
        with self._lock:
            pipeline = self.load()
            results = pipeline.predict(image)
            if len(results) != 1:
                raise ValueError('Unexpected OCR result page count')
            return normalize_result(results[0], page_index, scale_x, scale_y)

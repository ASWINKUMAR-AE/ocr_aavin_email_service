import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.getenv('OCR_DATA_DIR', ROOT / 'data')).resolve()
MODELS = Path(os.getenv('OCR_MODEL_DIR', ROOT / 'models')).resolve()
MAX_UPLOAD = int(os.getenv('OCR_MAX_UPLOAD_MB', '25')) * 1024 * 1024
MAX_PAGES = int(os.getenv('OCR_MAX_PAGES', '10'))
MAX_PIXELS = int(os.getenv('OCR_MAX_PIXELS', '24000000'))
MAX_SIDE = int(os.getenv('OCR_MAX_SIDE', '2000'))
PDF_DPI = int(os.getenv('OCR_PDF_DPI', '150'))
CPU_THREADS = int(os.getenv('OCR_CPU_THREADS', '4'))
DETECTOR = 'PP-OCRv5_mobile_det'
RECOGNIZER = 'ta_PP-OCRv5_mobile_rec'

"""Decode bounded inputs to canonical PNG pages, preserving EXIF orientation."""
import warnings
from contextlib import closing
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

from app.config import MAX_PIXELS, MAX_PAGES, PDF_DPI, MAX_SIDE


def save_page(image, folder, index):
    if image.width * image.height > MAX_PIXELS:
        raise ValueError('Page exceeds pixel limit')
    image = image.convert('RGB')
    filename = f'page-{index}.png'
    image.save(folder / filename)
    return dict(index=index, width=image.width, height=image.height, image=filename)


def decode_pages(source: Path, folder: Path):
    pages = []
    if source.suffix == '.pdf':
        import pypdfium2 as pdfium
        with closing(pdfium.PdfDocument(source)) as pdf:
            if not 0 < len(pdf) <= MAX_PAGES:
                raise ValueError(f'PDF must contain 1–{MAX_PAGES} pages')
            for index in range(len(pdf)):
                with closing(pdf[index]) as page:
                    w, h = page.get_size()
                    scale = PDF_DPI / 72
                    if w * h * scale ** 2 > MAX_PIXELS:
                        raise ValueError('PDF page exceeds pixel limit; reduce OCR_PDF_DPI')
                    bitmap = page.render(scale=scale)
                    try:
                        pages.append(save_page(bitmap.to_pil(), folder, index))
                    finally:
                        bitmap.close()
    else:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(source) as image:
                if image.format not in ('JPEG', 'PNG'):
                    raise ValueError('Only PNG and JPEG images are supported')
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError('Image exceeds pixel limit')
                pages.append(save_page(ImageOps.exif_transpose(image), folder, 0))
    return pages


def inference_image(path):
    # imdecode handles Unicode Windows paths.
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Image decoding failed')
    h, w = image.shape[:2]
    scale = min(1.0, MAX_SIDE / max(h, w))
    if scale < 1:
        image = cv2.resize(image, (max(1, round(w * scale)), max(1, round(h * scale))), interpolation=cv2.INTER_AREA)
    return image, w / image.shape[1], h / image.shape[0]

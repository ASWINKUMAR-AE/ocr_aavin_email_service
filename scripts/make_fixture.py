"""Generate synthetic printed text; this is not a handwriting accuracy test."""
import argparse
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
TEXTS = ['தமிழ் மொழி', 'பெயர் : மாதிரி', 'English sample', '0123456789', '000000000001']


def make_fixture(font_path=None):
    folder = ROOT / 'backend' / 'tests' / 'fixtures'
    folder.mkdir(parents=True, exist_ok=True)
    font_path = font_path or 'C:/Windows/Fonts/Nirmala.ttc'
    font = ImageFont.truetype(font_path, 48)
    image = Image.new('RGB', (1200, 650), 'white')
    draw = ImageDraw.Draw(image)
    for i, text in enumerate(TEXTS):
        draw.text((70, 40 + i * 110), text, font=font, fill='black')
    path = folder / 'synthetic-bilingual.png'
    image.save(path)
    (folder / 'synthetic-bilingual.json').write_text(json.dumps({'image': path.name, 'text': '\n'.join(TEXTS),
        'numeric_fields': ['0123456789', '000000000001'], 'kind': 'synthetic printed; not handwriting'}, ensure_ascii=False, indent=2), encoding='utf-8')
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--font')
    print(make_fixture(parser.parse_args().font))

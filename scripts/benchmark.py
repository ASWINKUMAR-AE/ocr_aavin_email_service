"""Usage: python scripts/benchmark.py labels.json --output data/benchmark.json

Labels: [{"image":"path/relative/to/labels.png", "text":"reference text",
          "numeric_fields":["000000000001"]}]
Numeric metric matches exact digit runs, not table field assignments.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys
import time
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))


def distance(a, b):
    row = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        next_row = [i]
        for j, right in enumerate(b, 1):
            next_row.append(min(next_row[-1] + 1, row[j] + 1, row[j - 1] + (left != right)))
        row = next_row
    return row[-1]


def metrics(reference, prediction, numbers):
    reference, prediction = [unicodedata.normalize('NFC', t) for t in (reference, prediction)]
    available = Counter(re.findall(r'(?<!\d)\d+(?!\d)', prediction))
    hits = 0
    for number in numbers:
        if available[number]:
            hits += 1
            available[number] -= 1
    return dict(character_errors=distance(reference, prediction), reference_characters=len(reference),
                word_errors=distance(reference.split(), prediction.split()), reference_words=len(reference.split()),
                numeric_matches=hits, numeric_total=len(numbers))


def main():
    from app.services.documents import inference_image
    from app.services.ocr_engine import OCREngine
    parser = argparse.ArgumentParser()
    parser.add_argument('labels', type=Path)
    parser.add_argument('--output', type=Path, default=Path('data/benchmark.json'))
    args = parser.parse_args()
    labels = json.loads(args.labels.read_text(encoding='utf-8'))
    engine = OCREngine()
    started = time.perf_counter()
    engine.load()
    initialization = time.perf_counter() - started
    results = []
    for item in labels:
        started = time.perf_counter()
        image, sx, sy = inference_image(args.labels.parent / item['image'])
        prediction = '\n'.join(l['raw_text'] for l in engine.recognize(image, 0, sx, sy))
        results.append(dict(**metrics(item['text'], prediction, item.get('numeric_fields', [])), seconds=time.perf_counter() - started))
    totals = {key: sum(r[key] for r in results) for key in ('character_errors','reference_characters','word_errors','reference_words','numeric_matches','numeric_total')}
    report = dict(samples=results, initialization_seconds=initialization,
        cer=totals['character_errors'] / totals['reference_characters'] if totals['reference_characters'] else None,
        wer=totals['word_errors'] / totals['reference_words'] if totals['reference_words'] else None,
        numeric_exact_match=totals['numeric_matches'] / totals['numeric_total'] if totals['numeric_total'] else None,
        totals=totals)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

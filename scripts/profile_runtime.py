"""Compare runtime size, exact OCR/table outputs and warmed inference timing.

Run in each environment with the same --images, then --compare baseline.json.
Reports contain hashes, not source text, image paths or personal identifiers.
Installed sizes describe this platform, not a Vercel/Linux deployment bundle.
"""
import argparse
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
from statistics import median
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()


def package_sizes():
    packages = []
    for distribution in distributions():
        paths = {Path(distribution.locate_file(f)).resolve() for f in distribution.files or []}
        size = sum(p.stat().st_size for p in paths if p.is_file())
        packages.append(dict(name=distribution.metadata['Name'], version=distribution.version, bytes=size))
    return sorted(packages, key=lambda p: p['bytes'], reverse=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--images', type=Path, nargs='+', default=[ROOT / 'backend/tests/fixtures/synthetic-bilingual.png'])
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error('--runs must be positive')
    from app.services.ocr_engine import OCREngine
    from app.services.documents import inference_image
    from app.services.table_parser import suggest_layout, materialize
    from app.config import MODELS, DETECTOR, RECOGNIZER
    packages = package_sizes()
    engine = OCREngine()
    started = time.perf_counter()
    engine.load()
    initialization = time.perf_counter() - started
    records = []
    for index, path in enumerate(args.images):
        image, sx, sy = inference_image(path)
        lines = engine.recognize(image, 0, sx, sy)  # Warmup, excluded from timed runs.
        expected = digest(lines)
        times = []
        for _ in range(args.runs):
            started = time.perf_counter()
            result = engine.recognize(image, 0, sx, sy)
            times.append(time.perf_counter() - started)
            if digest(result) != expected:
                raise RuntimeError('Repeated OCR outputs differ; investigate before removing dependencies')
        page = dict(index=0, width=round(image.shape[1] * sx), height=round(image.shape[0] * sy))
        table = materialize(suggest_layout(path, page, lines), lines)
        records.append(dict(sample=index, input_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            lines=len(lines), ocr_sha256=expected, table_sha256=digest(table),
            seconds=times, median_seconds=median(times)))
    models = {f'{name}/{f.name}': hashlib.sha256(f.read_bytes()).hexdigest()
              for name in (DETECTOR, RECOGNIZER) for f in (MODELS / name).glob('inference.*')}
    report = dict(platform=platform.platform(), python=platform.python_version(), packages=packages,
                  package_bytes=sum(p['bytes'] for p in packages), model_hashes=models,
                  initialization_seconds=initialization, samples=records)
    if args.compare:
        before = json.loads(args.compare.read_text(encoding='utf-8'))
        if before['model_hashes'] != models or len(before['samples']) != len(records):
            raise RuntimeError('Different models or sample counts')
        for old, new in zip(before['samples'], records):
            for key in ('input_sha256', 'ocr_sha256', 'table_sha256'):
                if old[key] != new[key]:
                    raise RuntimeError(f'Comparison mismatch: sample {new["sample"]}, {key}')
        report['comparison'] = dict(exact_outputs_match=True,
            saved_bytes=before['package_bytes'] - report['package_bytes'],
            median_time_ratios=[b['median_seconds'] / a['median_seconds'] for a, b in zip(before['samples'], records)])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('packages','model_hashes','samples')}, indent=2))
    print(json.dumps({'samples':[{k:s[k] for k in ('sample','lines','median_seconds')} for s in records]}))


if __name__ == '__main__':
    main()

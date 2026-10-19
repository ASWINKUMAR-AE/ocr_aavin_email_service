"""Installation-only download. Inference always uses these explicit local paths."""
import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.config import MODELS, DETECTOR, RECOGNIZER


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--verify-only', action='store_true')
    args = parser.parse_args()
    MODELS.mkdir(parents=True, exist_ok=True)
    manifest_path = MODELS / 'manifest.json'
    if args.verify_only:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        for relative, expected in manifest.items():
            actual = hashlib.sha256((MODELS / relative).read_bytes()).hexdigest()
            if actual != expected:
                raise RuntimeError(f'Model integrity check failed: {relative}')
        print('Local model integrity verified.')
        return
    os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
    os.environ['HF_HUB_DISABLE_XET'] = '1'
    from huggingface_hub import snapshot_download
    for name in (DETECTOR, RECOGNIZER):
        snapshot_download(repo_id=f'PaddlePaddle/{name}', local_dir=MODELS / name,
                          allow_patterns=['inference.json', 'inference.pdiparams', 'inference.yml', 'README.md', 'config.json'])
    manifest = {str(p.relative_to(MODELS)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                for name in (DETECTOR, RECOGNIZER) for p in (MODELS / name).glob('inference.*')}
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('Models cached. Run scripts/verify_ocr.py with networking disabled to check offline inference.')


if __name__ == '__main__':
    main()

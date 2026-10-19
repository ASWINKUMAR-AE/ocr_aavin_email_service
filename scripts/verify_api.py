"""Integration smoke: real API job, real models, synthetic data, isolated storage."""
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
os.environ['OCR_DATA_DIR'] = str(ROOT / '.cache/api-smoke')
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from app.main import app


with TestClient(app) as client:
    image = ROOT / 'backend/tests/fixtures/synthetic-bilingual.png'
    with image.open('rb') as source:
        response = client.post('/api/documents', files={'file': ('synthetic.png', source, 'image/png')})
    assert response.status_code == 202, response.text
    identifier = response.json()['id']
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        doc = client.get(f'/api/documents/{identifier}').json()
        if doc['status'] in ('complete', 'failed'):
            break
        time.sleep(.25)
    assert doc['status'] == 'complete', doc.get('error', doc['status'])
    assert len(doc['lines']) == 5
    assert client.get(f'/api/documents/{identifier}/pages/0').status_code == 200
    for format in ('xlsx', 'csv', 'json', 'txt'):
        exported = client.get(f'/api/documents/{identifier}/export/{format}')
        assert exported.status_code == 200 and exported.content
    print(json.dumps({'status': doc['status'], 'lines': len(doc['lines']), 'seconds': doc['processing_seconds'], 'exports': '4 passed'}))

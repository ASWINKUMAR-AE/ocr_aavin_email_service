import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DATA


@contextmanager
def connection():
    DATA.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATA / 'studio.sqlite3', timeout=20) as db:
        db.row_factory = sqlite3.Row
        yield db


def initialize():
    with connection() as db:
        db.execute('CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
        for row in db.execute('SELECT id, payload FROM documents').fetchall():
            doc = json.loads(row['payload'])
            if doc['status'] in ('queued', 'processing'):
                doc.update(status='failed', error='Processing interrupted by server restart. Upload again to retry.')
                db.execute('UPDATE documents SET payload=? WHERE id=?', (json.dumps(doc, ensure_ascii=False), row['id']))


def save(doc):
    with connection() as db:
        db.execute('INSERT OR REPLACE INTO documents VALUES (?, ?)', (doc['id'], json.dumps(doc, ensure_ascii=False)))


def get(identifier):
    with connection() as db:
        row = db.execute('SELECT payload FROM documents WHERE id=?', (identifier,)).fetchone()
        return json.loads(row['payload']) if row else None


def summaries():
    with connection() as db:
        docs = [json.loads(row['payload']) for row in db.execute('SELECT payload FROM documents ORDER BY rowid DESC')]
    return [{k: d[k] for k in ('id', 'name', 'status', 'created_at')} for d in docs]


def correct(identifier, line_id, text, reviewed):
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM documents WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        doc = json.loads(row['payload'])
        for line in doc['lines']:
            if line['id'] == line_id:
                doc.setdefault('history', []).append(dict(line_id=line_id, before=line['corrected_text'], after=text,
                    previous_reviewed=line['reviewed'], reviewed=reviewed, at=datetime.now(timezone.utc).isoformat()))
                line.update(corrected_text=text, reviewed=reviewed)
                db.execute('UPDATE documents SET payload=? WHERE id=?', (json.dumps(doc, ensure_ascii=False), identifier))
                return doc
        raise KeyError(line_id)


def mutate(identifier, operation):
    """Serialize table edits with line edits; never overwrite a stale whole document."""
    with connection() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM documents WHERE id=?', (identifier,)).fetchone()
        if row is None:
            raise KeyError(identifier)
        doc = json.loads(row['payload'])
        result = operation(doc)
        db.execute('UPDATE documents SET payload=? WHERE id=?', (json.dumps(doc, ensure_ascii=False), identifier))
        return result

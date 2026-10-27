import json
from contextlib import contextmanager
from datetime import datetime, timezone

from app.config import DATA
from app.db import get_connection, initialize_all_tables, migrate_sqlite_if_needed


@contextmanager
def connection():
    with get_connection(data_dir=DATA) as db:
        yield db


def initialize():
    with connection() as db:
        initialize_all_tables(db=db)
        migrate_sqlite_if_needed(db=db, data_dir=DATA)
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

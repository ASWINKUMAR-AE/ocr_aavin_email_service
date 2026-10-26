import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.config import DATA


@contextmanager
def db_connection():
    DATA.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATA / 'studio.sqlite3', timeout=20) as db:
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys = ON')
        yield db


def initialize_reports_tables():
    """Create schema for reports, report items, and audit logs."""
    with db_connection() as db:
        db.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                document_id TEXT,
                union_code TEXT NOT NULL,
                organization_name TEXT NOT NULL,
                address TEXT NOT NULL,
                report_date TEXT NOT NULL,
                shift TEXT NOT NULL,
                abstract_no TEXT,
                milk_total_litres TEXT NOT NULL,
                milk_total_packets INTEGER NOT NULL,
                milk_total_trays TEXT NOT NULL,
                curd_buttermilk_total_litres TEXT NOT NULL,
                curd_buttermilk_total_packets INTEGER NOT NULL,
                curd_buttermilk_total_trays TEXT NOT NULL,
                grand_total_litres TEXT NOT NULL,
                grand_total_packets INTEGER NOT NULL,
                grand_total_trays TEXT NOT NULL,
                raw_ocr_text TEXT NOT NULL,
                parsed_json TEXT NOT NULL,
                validation_status TEXT NOT NULL,
                validation_warnings TEXT NOT NULL,
                ocr_created_at TEXT NOT NULL,
                report_processed_at TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                email_status TEXT NOT NULL,
                email_sent_at TEXT,
                approved_by TEXT,
                approved_at TEXT,
                CONSTRAINT uq_report_business_key UNIQUE (union_code, report_date, shift)
            )
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS report_items (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
                item_no INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity_litres TEXT NOT NULL,
                quantity_packets INTEGER NOT NULL,
                quantity_trays TEXT NOT NULL,
                row_type TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        ''')

        db.execute('''
            CREATE TABLE IF NOT EXISTS report_audit_logs (
                id TEXT PRIMARY KEY,
                report_id TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        ''')

        db.execute('CREATE INDEX IF NOT EXISTS idx_reports_date ON reports (report_date)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_reports_shift ON reports (shift)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_reports_val_status ON reports (validation_status)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_reports_email_status ON reports (email_status)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_report_items_report_id ON report_items (report_id)')
        db.execute('CREATE INDEX IF NOT EXISTS idx_report_audit_report_id ON report_audit_logs (report_id)')


def log_audit(report_id: str, action: str, details: str):
    """Record an audit trail event."""
    now_utc = datetime.now(timezone.utc).isoformat()
    log_id = str(uuid.uuid4())
    with db_connection() as db:
        db.execute(
            'INSERT INTO report_audit_logs (id, report_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)',
            (log_id, report_id, action, details, now_utc)
        )


def save_or_reconcile_report(report_data: Dict[str, Any], items: List[Dict[str, Any]], user: str = "system") -> Dict[str, Any]:
    """
    Idempotent report persistence inside an immediate SQLite transaction.
    If the business identity (union_code, report_date, shift) exists, reconcile rather than duplicate.
    Never overwrite a sent email status with pending.
    """
    now_utc = datetime.now(timezone.utc).isoformat()
    union_code = report_data['union_code']
    report_date = report_data['report_date']
    shift = report_data['shift']

    with db_connection() as db:
        db.execute('BEGIN IMMEDIATE')

        existing = db.execute(
            'SELECT * FROM reports WHERE union_code = ? AND report_date = ? AND shift = ?',
            (union_code, report_date, shift)
        ).fetchone()

        if existing:
            report_id = existing['id']
            # Preserve existing email status if already sent
            email_status = existing['email_status']
            email_sent_at = existing['email_sent_at']
            approved_by = existing['approved_by']
            approved_at = existing['approved_at']

            # If existing validation was already approved or sent, preserve approval
            validation_status = existing['validation_status']
            if validation_status != 'VALIDATED':
                validation_status = report_data.get('validation_status', 'NEEDS_REVIEW')

            db.execute('''
                UPDATE reports SET
                    document_id = COALESCE(?, document_id),
                    organization_name = ?,
                    address = ?,
                    abstract_no = ?,
                    milk_total_litres = ?,
                    milk_total_packets = ?,
                    milk_total_trays = ?,
                    curd_buttermilk_total_litres = ?,
                    curd_buttermilk_total_packets = ?,
                    curd_buttermilk_total_trays = ?,
                    grand_total_litres = ?,
                    grand_total_packets = ?,
                    grand_total_trays = ?,
                    raw_ocr_text = ?,
                    parsed_json = ?,
                    validation_status = ?,
                    validation_warnings = ?,
                    ocr_created_at = ?,
                    report_processed_at = ?,
                    updated_at = ?
                WHERE id = ?
            ''', (
                report_data.get('document_id'),
                report_data['organization_name'],
                report_data['address'],
                report_data.get('abstract_no', ''),
                str(report_data['milk_total_litres']),
                int(report_data['milk_total_packets']),
                str(report_data['milk_total_trays']),
                str(report_data['curd_buttermilk_total_litres']),
                int(report_data['curd_buttermilk_total_packets']),
                str(report_data['curd_buttermilk_total_trays']),
                str(report_data['grand_total_litres']),
                int(report_data['grand_total_packets']),
                str(report_data['grand_total_trays']),
                report_data['raw_ocr_text'],
                json.dumps(report_data, ensure_ascii=False),
                validation_status,
                json.dumps(report_data.get('validation_warnings', []), ensure_ascii=False),
                report_data.get('ocr_created_at', now_utc),
                report_data.get('report_processed_at', now_utc),
                now_utc,
                report_id
            ))

            # Replace items cleanly
            db.execute('DELETE FROM report_items WHERE report_id = ?', (report_id,))
            for itm in items:
                item_id = str(uuid.uuid4())
                db.execute('''
                    INSERT INTO report_items (id, report_id, item_no, product_name, category,
                                              quantity_litres, quantity_packets, quantity_trays, row_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item_id,
                    report_id,
                    int(itm.get('item_no', 0)),
                    str(itm['product_name']),
                    str(itm.get('category', 'OTHER')),
                    str(itm['quantity_litres']),
                    int(itm['quantity_packets']),
                    str(itm['quantity_trays']),
                    str(itm.get('row_type', 'PRODUCT')),
                    now_utc
                ))

            # Audit log reconciliation
            db.execute(
                'INSERT INTO report_audit_logs (id, report_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)',
                (str(uuid.uuid4()), report_id, 'RECONCILED', f'Re-processed report by {user}. Email status remains {email_status}.', now_utc)
            )

        else:
            report_id = str(uuid.uuid4())
            validation_status = report_data.get('validation_status', 'NEEDS_REVIEW')
            email_status = report_data.get('email_status', 'PENDING')
            if validation_status == 'NEEDS_REVIEW':
                email_status = 'NEEDS_REVIEW'

            db.execute('''
                INSERT INTO reports (
                    id, document_id, union_code, organization_name, address, report_date, shift, abstract_no,
                    milk_total_litres, milk_total_packets, milk_total_trays,
                    curd_buttermilk_total_litres, curd_buttermilk_total_packets, curd_buttermilk_total_trays,
                    grand_total_litres, grand_total_packets, grand_total_trays,
                    raw_ocr_text, parsed_json, validation_status, validation_warnings,
                    ocr_created_at, report_processed_at, created_at, updated_at,
                    email_status, email_sent_at, approved_by, approved_at
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, ?, ?, ?,
                    ?, NULL, NULL, NULL
                )
            ''', (
                report_id,
                report_data.get('document_id'),
                union_code,
                report_data['organization_name'],
                report_data['address'],
                report_date,
                shift,
                report_data.get('abstract_no', ''),
                str(report_data['milk_total_litres']),
                int(report_data['milk_total_packets']),
                str(report_data['milk_total_trays']),
                str(report_data['curd_buttermilk_total_litres']),
                int(report_data['curd_buttermilk_total_packets']),
                str(report_data['curd_buttermilk_total_trays']),
                str(report_data['grand_total_litres']),
                int(report_data['grand_total_packets']),
                str(report_data['grand_total_trays']),
                report_data['raw_ocr_text'],
                json.dumps(report_data, ensure_ascii=False),
                validation_status,
                json.dumps(report_data.get('validation_warnings', []), ensure_ascii=False),
                report_data.get('ocr_created_at', now_utc),
                report_data.get('report_processed_at', now_utc),
                now_utc,
                now_utc,
                email_status
            ))

            for itm in items:
                item_id = str(uuid.uuid4())
                db.execute('''
                    INSERT INTO report_items (id, report_id, item_no, product_name, category,
                                              quantity_litres, quantity_packets, quantity_trays, row_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item_id,
                    report_id,
                    int(itm.get('item_no', 0)),
                    str(itm['product_name']),
                    str(itm.get('category', 'OTHER')),
                    str(itm['quantity_litres']),
                    int(itm['quantity_packets']),
                    str(itm['quantity_trays']),
                    str(itm.get('row_type', 'PRODUCT')),
                    now_utc
                ))

            db.execute(
                'INSERT INTO report_audit_logs (id, report_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)',
                (str(uuid.uuid4()), report_id, 'CREATED', f'New report created via OCR by {user}. Status: {validation_status}', now_utc)
            )

    return get_report(report_id)


def get_report(report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve full report with its items and audit log."""
    with db_connection() as db:
        r_row = db.execute('SELECT * FROM reports WHERE id = ?', (report_id,)).fetchone()
        if not r_row:
            return None
        report = dict(r_row)
        report['validation_warnings'] = json.loads(report['validation_warnings'] or '[]')
        report['parsed_json'] = json.loads(report['parsed_json'] or '{}')

        i_rows = db.execute(
            'SELECT * FROM report_items WHERE report_id = ? ORDER BY item_no ASC, rowid ASC',
            (report_id,)
        ).fetchall()
        report['items'] = [dict(it) for it in i_rows]

        a_rows = db.execute(
            'SELECT * FROM report_audit_logs WHERE report_id = ? ORDER BY timestamp DESC, rowid DESC',
            (report_id,)
        ).fetchall()
        report['audit_logs'] = [dict(a) for a in a_rows]

        return report


def list_reports(
    report_date: Optional[str] = None,
    shift: Optional[str] = None,
    validation_status: Optional[str] = None,
    email_status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Query reports with optional filtering."""
    query = 'SELECT * FROM reports WHERE 1=1'
    params: List[Any] = []

    if report_date:
        query += ' AND report_date = ?'
        params.append(report_date)
    if shift:
        query += ' AND UPPER(shift) = ?'
        params.append(shift.upper())
    if validation_status:
        query += ' AND validation_status = ?'
        params.append(validation_status)
    if email_status:
        query += ' AND email_status = ?'
        params.append(email_status)

    query += ' ORDER BY report_date DESC, created_at DESC'

    with db_connection() as db:
        rows = db.execute(query, params).fetchall()
        result = []
        for r in rows:
            rep = dict(r)
            rep['validation_warnings'] = json.loads(rep['validation_warnings'] or '[]')
            result.append(rep)
        return result


def update_email_status(report_id: str, status: str, sent_at: Optional[str] = None, details: str = "") -> Optional[Dict[str, Any]]:
    """Update delivery status and timestamp for a report."""
    now_utc = datetime.now(timezone.utc).isoformat()
    with db_connection() as db:
        db.execute('''
            UPDATE reports SET
                email_status = ?,
                email_sent_at = COALESCE(?, email_sent_at),
                updated_at = ?
            WHERE id = ?
        ''', (status, sent_at, now_utc, report_id))

        db.execute(
            'INSERT INTO report_audit_logs (id, report_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)',
            (str(uuid.uuid4()), report_id, f'EMAIL_{status}', details or f'Email status set to {status}', now_utc)
        )

    return get_report(report_id)


def approve_report(report_id: str, approved_by: str = "reviewer", notes: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Mark a NEEDS_REVIEW report as VALIDATED."""
    now_utc = datetime.now(timezone.utc).isoformat()
    with db_connection() as db:
        db.execute('''
            UPDATE reports SET
                validation_status = 'VALIDATED',
                approved_by = ?,
                approved_at = ?,
                updated_at = ?
            WHERE id = ?
        ''', (approved_by, now_utc, now_utc, report_id))

        msg = f'Report approved by {approved_by}.'
        if notes:
            msg += f' Notes: {notes}'
        db.execute(
            'INSERT INTO report_audit_logs (id, report_id, action, details, timestamp) VALUES (?, ?, ?, ?, ?)',
            (str(uuid.uuid4()), report_id, 'APPROVED', msg, now_utc)
        )

    return get_report(report_id)

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.config import DATA
from app.db import get_connection, initialize_all_tables, migrate_sqlite_if_needed


@contextmanager
def db_connection():
    with get_connection(data_dir=DATA) as db:
        yield db


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Derive PBKDF2 HMAC SHA-256 hash with unique salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000).hex()
    return hashed, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify raw password against stored PBKDF2 hash using constant-time comparison."""
    hashed, _ = hash_password(password, salt)
    return hmac.compare_digest(hashed, password_hash)


def initialize_reports_tables():
    """Create schema for reports, report items, audit logs, and admin credentials."""
    with db_connection() as db:
        initialize_all_tables(db=db)
        migrate_sqlite_if_needed(db=db, data_dir=DATA)
    ensure_default_admin()


def ensure_default_admin(default_user: str = 'admin', default_pass: str = 'admin123'):
    """Ensure at least one admin user exists with initial default credentials."""
    with db_connection() as db:
        row = db.execute('SELECT id FROM admin_users LIMIT 1').fetchone()
        if not row:
            p_hash, salt = hash_password(default_pass)
            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                'INSERT INTO admin_users (id, username, password_hash, salt, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)',
                (str(uuid.uuid4()), default_user, p_hash, salt, now, now)
            )


def authenticate_admin(username: str, password: str) -> Optional[str]:
    """Verify admin credentials and issue a 24-hour session token."""
    ensure_default_admin()
    with db_connection() as db:
        row = db.execute('SELECT username, password_hash, salt FROM admin_users WHERE username = ?', (username.strip(),)).fetchone()
        if not row:
            return None
        if verify_password(password, row['password_hash'], row['salt']):
            token = secrets.token_urlsafe(32)
            now = datetime.now(timezone.utc)
            expires = (now + timedelta(hours=24)).isoformat()
            db.execute(
                'INSERT INTO admin_sessions (token, username, created_at, expires_at) VALUES (?, ?, ?, ?)',
                (token, row['username'], now.isoformat(), expires)
            )
            return token
        return None


def verify_session_token(token: str) -> Optional[str]:
    """Validate session token and return admin username if active."""
    if not token:
        return None
    now_iso = datetime.now(timezone.utc).isoformat()
    with db_connection() as db:
        row = db.execute(
            'SELECT username FROM admin_sessions WHERE token = ? AND expires_at > ?',
            (token, now_iso)
        ).fetchone()
        return row['username'] if row else None


def change_admin_password(username: str, current_password: str, new_password: str) -> bool:
    """Safely update admin password after verifying current password."""
    ensure_default_admin()
    with db_connection() as db:
        row = db.execute('SELECT username, password_hash, salt FROM admin_users WHERE username = ?', (username,)).fetchone()
        if not row or not verify_password(current_password, row['password_hash'], row['salt']):
            return False
        new_hash, new_salt = hash_password(new_password)
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            'UPDATE admin_users SET password_hash = ?, salt = ?, updated_at = ? WHERE username = ?',
            (new_hash, new_salt, now, username)
        )
        return True


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

            if report_data.get('validation_status') == 'VALIDATED':
                validation_status = 'VALIDATED'
            elif existing['validation_status'] in ('VALIDATED', 'APPROVED'):
                validation_status = existing['validation_status']
            else:
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

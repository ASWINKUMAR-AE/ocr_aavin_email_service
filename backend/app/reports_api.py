import asyncio
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from app import config, reports_store, store
from app.services.aavin_parser import AavinAbstractParser
from app.services.email_service import AavinReportEmailService

router = APIRouter(prefix='/api/reports', tags=['Aavin Reports'])


class OCRParseRequest(BaseModel):
    document_id: Optional[str] = None
    raw_text: Optional[str] = Field(None, max_length=100000)
    ocr_created_at: Optional[str] = None


class SendEmailRequest(BaseModel):
    recipients: Optional[List[Union[Dict[str, Any], str]]] = None
    force: bool = False


class ApproveRequest(BaseModel):
    approved_by: str = Field('reviewer', min_length=1, max_length=100)
    notes: Optional[str] = Field(None, max_length=2000)
    send_email: bool = True


@router.post('/ocr', status_code=201)
async def parse_and_save_ocr(payload: OCRParseRequest, background_tasks: BackgroundTasks):
    """
    Parse Aavin production abstract report from OCR text or an existing OCR document.
    Saves to database and automatically triggers email dispatch if validated and email enabled.
    """
    config.reload_env()
    raw_text = payload.raw_text
    doc_id = payload.document_id
    ocr_created_at = payload.ocr_created_at

    if not raw_text and doc_id:
        doc = store.get(doc_id)
        if not doc:
            raise HTTPException(404, 'Document not found')
        if doc['status'] != 'complete':
            raise HTTPException(409, 'Wait for document OCR to finish before parsing')
        ocr_created_at = doc.get('created_at')
        lines = doc.get('lines', [])
        # Combine text in reading order
        raw_text = " ".join(
            (line['corrected_text'] if line.get('corrected_text') is not None else line.get('raw_text', ''))
            for line in lines
        )

    if not raw_text or not raw_text.strip():
        raise HTTPException(400, 'Either raw_text or a valid completed document_id must be provided')

    report_data = AavinAbstractParser.parse_aavin_abstract(
        raw_text=raw_text,
        ocr_created_at=ocr_created_at,
        document_id=doc_id
    )

    if not report_data:
        raise HTTPException(422, 'The provided text does not match an Aavin Milk Production Abstract report structure.')

    items = report_data.pop('items')
    saved_report = reports_store.save_or_reconcile_report(report_data, items, user='api')

    # Automatic email workflow: dispatch if validated and email is enabled
    if saved_report['validation_status'] == 'VALIDATED' and config.REPORT_EMAIL_ENABLED:
        background_tasks.add_task(AavinReportEmailService.send_report_email, saved_report['id'], force=True)

    return saved_report


@router.get('')
def list_reports(
    report_date: Optional[str] = Query(None, description='Filter by report date YYYY-MM-DD'),
    shift: Optional[str] = Query(None, description='Filter by shift (e.g. MORNING, EVENING)'),
    validation_status: Optional[str] = Query(None, description='Filter by validation status (VALIDATED, NEEDS_REVIEW)'),
    email_status: Optional[str] = Query(None, description='Filter by email status (PENDING, SENT, FAILED, NEEDS_REVIEW, DISABLED)')
):
    """List stored reports with optional filters."""
    return reports_store.list_reports(
        report_date=report_date,
        shift=shift,
        validation_status=validation_status,
        email_status=email_status
    )


def get_current_admin(authorization: Optional[str] = Header(None)) -> str:
    """Verify admin bearer token from Authorization header."""
    if not authorization:
        raise HTTPException(401, "Administrator authentication required. Please log in.")
    token = authorization.replace('Bearer ', '').replace('bearer ', '').strip()
    username = reports_store.verify_session_token(token)
    if not username:
        raise HTTPException(401, "Invalid or expired administrator session. Please log in again.")
    return username


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class AdminChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=4)


class UpdateSenderRequest(BaseModel):
    smtp_host: Optional[str] = 'smtp.gmail.com'
    smtp_port: Optional[int] = 587
    smtp_user: Optional[str] = ''
    smtp_password: Optional[str] = None
    smtp_from_email: Optional[str] = None
    smtp_from_name: Optional[str] = 'Aavin OCR Reports'
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False


class RecipientPreferenceItem(BaseModel):
    role: Optional[str] = 'STAFF'
    name: Optional[str] = ''
    email: str
    send_pdf: bool = True
    send_excel: bool = False


class UpdateRecipientsRequest(BaseModel):
    recipients: List[Union[RecipientPreferenceItem, Dict[str, Any], str]] = Field(..., min_length=1)


# --- Admin Authentication Endpoints ---

@router.post('/settings/admin/login')
def admin_login(payload: AdminLoginRequest):
    """Verify administrator credentials and issue a session token."""
    token = reports_store.authenticate_admin(payload.username, payload.password)
    if not token:
        raise HTTPException(401, "Invalid administrator username or password.")
    return {
        'success': True,
        'token': token,
        'username': payload.username
    }


@router.post('/settings/admin/verify')
def admin_verify(authorization: Optional[str] = Header(None)):
    """Check if the provided admin session token is valid."""
    username = get_current_admin(authorization)
    return {'valid': True, 'username': username}


@router.post('/settings/admin/change-password')
def admin_change_password(payload: AdminChangePasswordRequest, authorization: Optional[str] = Header(None)):
    """Change the administrator password."""
    username = get_current_admin(authorization)
    ok = reports_store.change_admin_password(username, payload.current_password, payload.new_password)
    if not ok:
        raise HTTPException(400, "Current password verification failed.")
    return {'success': True, 'message': 'Admin password updated successfully.'}


# --- Mail & Sender Settings Endpoints ---

@router.get('/settings/mail')
def get_mail_settings():
    """Retrieve combined sender configuration and recipient preferences."""
    config.reload_env()
    return {
        'sender': config.safe_report_config(),
        'recipients': config.REPORT_RECIPIENT_PREFERENCES
    }


@router.put('/settings/sender')
def update_sender_settings(payload: UpdateSenderRequest, authorization: Optional[str] = Header(None)):
    """Update SMTP sender email and Google app password (admin only)."""
    get_current_admin(authorization)
    try:
        updated = config.update_sender_settings(payload.model_dump())
        return {
            'success': True,
            'sender': updated,
            'message': 'Sender SMTP settings updated successfully.'
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to update sender settings: {str(e)}")


@router.post('/settings/sender/test')
def test_sender_connection(authorization: Optional[str] = Header(None)):
    """Test SMTP connection and authentication with current sender settings (admin only)."""
    get_current_admin(authorization)
    import smtplib
    config.reload_env()
    if not config.SMTP_HOST:
        raise HTTPException(400, "SMTP host is not configured.")
    try:
        if config.SMTP_USE_SSL:
            server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10)
            if config.SMTP_USE_TLS:
                server.starttls()
        if config.SMTP_USER and config.SMTP_PASSWORD:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.quit()
        return {'success': True, 'message': f"Connected and authenticated successfully with {config.SMTP_HOST}:{config.SMTP_PORT} as {config.SMTP_USER}."}
    except Exception as e:
        return {'success': False, 'error': f"{type(e).__name__}: {str(e)}"}


# --- Recipient Settings Endpoints ---

@router.get('/settings/recipients')
def get_report_recipients():
    """Get current default email recipients and delivery preferences."""
    config.reload_env()
    return {
        'recipients': config.REPORT_RECIPIENT_PREFERENCES,
        'email_to': config.REPORT_EMAIL_TO,
        'email_enabled': config.REPORT_EMAIL_ENABLED
    }


@router.put('/settings/recipients')
def update_report_recipients(payload: UpdateRecipientsRequest, authorization: Optional[str] = Header(None)):
    """Update default report email recipients and preferences in .env and runtime config."""
    # If authorization header is provided, verify admin session
    if authorization:
        get_current_admin(authorization)

    import re
    email_regex = re.compile(r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    cleaned = []

    for r in payload.recipients:
        if isinstance(r, str):
            addr = r.strip()
            role = 'STAFF'
            name = ''
            send_pdf = True
            send_excel = False
        elif isinstance(r, dict):
            addr = str(r.get('email', '')).strip()
            role = str(r.get('role', 'STAFF')).strip().upper()
            name = str(r.get('name', '')).strip()
            send_pdf = bool(r.get('send_pdf', True))
            send_excel = bool(r.get('send_excel', False))
        elif hasattr(r, 'email'):
            addr = str(r.email).strip()
            role = str(getattr(r, 'role', 'STAFF')).strip().upper()
            name = str(getattr(r, 'name', '')).strip()
            send_pdf = bool(r.send_pdf)
            send_excel = bool(r.send_excel)
        else:
            continue

        if not addr:
            continue
        if not email_regex.match(addr):
            raise HTTPException(400, f"Invalid email format: '{addr}'")

        cleaned.append({
            'role': role or 'STAFF',
            'name': name,
            'email': addr,
            'send_pdf': send_pdf,
            'send_excel': send_excel
        })

    if not cleaned:
        raise HTTPException(400, "At least one valid recipient email is required.")

    # Deduplicate by email address, keeping the last preference set
    seen = {}
    for item in cleaned:
        seen[item['email'].lower()] = item
    unique_recipients = list(seen.values())

    try:
        updated = config.update_report_recipients(unique_recipients)
        return {
            'success': True,
            'recipients': updated,
            'message': f"Updated {len(updated)} default recipient(s)."
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to update recipients: {str(e)}")


@router.get('/{report_id}')
def get_report(report_id: str):
    """Retrieve full report details, product items, and audit log."""
    report = reports_store.get_report(report_id)
    if not report:
        raise HTTPException(404, 'Report not found')
    return report


@router.get('/{report_id}/email-preview')
def get_email_preview(report_id: str, html_only: bool = False):
    """Preview rendered email subject, plain text, and HTML table."""
    report = reports_store.get_report(report_id)
    if not report:
        raise HTTPException(404, 'Report not found')

    subject, plain_text, html_body = AavinReportEmailService.generate_email_content(report)
    if html_only:
        return HTMLResponse(content=html_body, status_code=200)

    return {
        'report_id': report_id,
        'subject': subject,
        'recipients': config.REPORT_EMAIL_TO,
        'plain_text': plain_text,
        'html': html_body
    }


@router.post('/{report_id}/send-email')
async def send_report_email(report_id: str, payload: SendEmailRequest):
    """Manually dispatch or resend an approved report email."""
    config.reload_env()
    report = reports_store.get_report(report_id)
    if not report:
        raise HTTPException(404, 'Report not found')

    res = await asyncio.to_thread(
        AavinReportEmailService.send_report_email,
        report_id=report_id,
        recipients=payload.recipients,
        force=payload.force,
        user='manual_user'
    )
    if not res.get('success'):
        raise HTTPException(400, res.get('error', 'Failed to send report email'))
    return res


@router.post('/{report_id}/approve')
async def approve_report(report_id: str, payload: ApproveRequest, background_tasks: BackgroundTasks):
    """Approve a report requiring review."""
    report = reports_store.get_report(report_id)
    if not report:
        raise HTTPException(404, 'Report not found')

    approved = reports_store.approve_report(
        report_id=report_id,
        approved_by=payload.approved_by,
        notes=payload.notes
    )

    if payload.send_email and config.REPORT_EMAIL_ENABLED and approved['email_status'] != 'SENT':
        background_tasks.add_task(AavinReportEmailService.send_report_email, report_id, user=payload.approved_by)

    return approved


@router.get('/{report_id}/email-status')
def get_email_status(report_id: str):
    """Retrieve email delivery submission status and delivery audit log."""
    report = reports_store.get_report(report_id)
    if not report:
        raise HTTPException(404, 'Report not found')

    email_logs = [log for log in report.get('audit_logs', []) if 'EMAIL' in log.get('action', '')]
    return {
        'report_id': report_id,
        'email_status': report['email_status'],
        'email_sent_at': report['email_sent_at'],
        'recipients': config.REPORT_EMAIL_TO,
        'email_enabled': config.REPORT_EMAIL_ENABLED,
        'audit_logs': email_logs
    }

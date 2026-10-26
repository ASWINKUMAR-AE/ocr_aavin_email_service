import asyncio
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
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
    recipients: Optional[List[str]] = None
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
    if saved_report['validation_status'] == 'VALIDATED' and config.REPORT_EMAIL_ENABLED and saved_report['email_status'] != 'SENT':
        background_tasks.add_task(AavinReportEmailService.send_report_email, saved_report['id'])

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

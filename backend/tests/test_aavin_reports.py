import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app import config, reports_store
from app.main import app
from app.services.aavin_parser import AavinAbstractParser
from app.services.email_service import AavinReportEmailService, format_ist_timestamp

client = TestClient(app)

SAMPLE_OCR_PROMPT_TEXT = (
    "GA13O1 THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD., "
    "SIVAGANGAI MAIN ROAD, MADURAI - 625 020 DATE 21.10.2026 SHIFT: EVENING "
    "ABSTRACT NO. TYPE OF PRODUCT QTY (LTR) QTY (PKT) TRAY "
    "1 COW MILK 500 ML 25776.5001 515531 2148.011 "
    "2 CM 200 ML 4763,6001 238181 476.181 "
    "3 AAVIN GOLD 500 ML 12321.000 246421 1026.181 "
    "4 TEA MATE PLUS-1000ML 5547.000 55471 462.031 "
    "5 TEAMATE 500 ML 533.000 1066 44.101 "
    "MILK TOTAL 48941.100 106626 4156.001 "
    "6 CURD 200 GM CUP 4.800 24 1.001 "
    "7 CURD 500 GM 107.000 214 8.221 "
    "8 CURD 145 ML 67.455 479 7.591 "
    "9 BUTTERMILK 140 ML 12.740 91 1.311 "
    "CURD & BUTTERMILK TOTAL 193.995 808 17.001 "
    "GRAND TOTAL 49135.095 107434 4173.001"
)

PERFECT_OCR_TEXT = (
    "GA1301 THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD., "
    "SIVAGANGAI MAIN ROAD, MADURAI - 625 020 DATE 22.10.2026 SHIFT: MORNING "
    "ABSTRACT NO. TYPE OF PRODUCT QTY (LTR) QTY (PKT) TRAY "
    "1 COW MILK 500 ML 25776.500 51553 2148.001 "
    "2 CM 200 ML 4763.600 23818 476.181 "
    "3 AAVIN GOLD 500 ML 12321.000 24642 1026.181 "
    "4 TEA MATE PLUS-1000ML 5547.000 5547 462.031 "
    "5 TEAMATE 500 ML 533.000 1066 44.101 "
    "MILK TOTAL 48941.100 106626 4156.001 "
    "6 CURD 200 GM CUP 4.800 24 1.001 "
    "7 CURD 500 GM 107.000 214 8.221 "
    "8 CURD 145 ML 69.455 479 7.591 "
    "9 BUTTERMILK 140 ML 12.740 91 1.311 "
    "CURD & BUTTERMILK TOTAL 193.995 808 17.001 "
    "GRAND TOTAL 49135.095 107434 4173.001"
)


@pytest.fixture(autouse=True)
def setup_db():
    reports_store.initialize_reports_tables()
    with reports_store.db_connection() as db:
        db.execute('DELETE FROM report_audit_logs')
        db.execute('DELETE FROM report_items')
        db.execute('DELETE FROM reports')



def test_extraction_date_shift_and_noise_handling():
    """Verify parsing of union code, 21.10.2026 date, shift, and conservative normalization."""
    parsed = AavinAbstractParser.parse_aavin_abstract(SAMPLE_OCR_PROMPT_TEXT)
    assert parsed is not None
    assert parsed['union_code'] == 'GA1301'  # O normalized to 0
    assert parsed['report_date'] == '2026-10-21'
    assert parsed['shift'] == 'EVENING'
    assert parsed['organization_name'] == "THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD."

    # In the prompt sample, line 8 (CURD 145 ML) had an arithmetic discrepancy:
    # 4.800 + 107.000 + 67.455 + 12.740 = 191.995 vs subtotal 193.995 (diff of 2.0L)
    # The parser must flag discrepancies rather than silently fabricating values
    assert parsed['validation_status'] == 'NEEDS_REVIEW'
    assert len(parsed['validation_warnings']) > 0
    assert any('Curd/Buttermilk Litres mismatch' in w for w in parsed['validation_warnings'])


def test_alternative_date_and_shift_formats():
    """Verify DD/MM/YYYY, DD-MM-YYYY, YYYY-MM-DD and MORNING/NIGHT shifts."""
    text_slash = SAMPLE_OCR_PROMPT_TEXT.replace('21.10.2026', '25/12/2026').replace('EVENING', 'MORNING')
    p1 = AavinAbstractParser.parse_aavin_abstract(text_slash)
    assert p1['report_date'] == '2026-12-25'
    assert p1['shift'] == 'MORNING'

    text_dash = SAMPLE_OCR_PROMPT_TEXT.replace('21.10.2026', '15-08-2026').replace('EVENING', 'NIGHT')
    p2 = AavinAbstractParser.parse_aavin_abstract(text_dash)
    assert p2['report_date'] == '2026-08-15'
    assert p2['shift'] == 'NIGHT'

    text_iso = SAMPLE_OCR_PROMPT_TEXT.replace('21.10.2026', '2026-01-05')
    p3 = AavinAbstractParser.parse_aavin_abstract(text_iso)
    assert p3['report_date'] == '2026-01-05'


def test_invalid_date_and_incomplete_text():
    """Invalid date or non-abstract text should be flagged or rejected."""
    # Invalid date: 32.13.2026
    bad_date_text = SAMPLE_OCR_PROMPT_TEXT.replace('21.10.2026', '32.13.2026')
    p = AavinAbstractParser.parse_aavin_abstract(bad_date_text)
    assert p['validation_status'] == 'NEEDS_REVIEW'
    assert any('Invalid date' in w or 'Report date could not be' in w for w in p['validation_warnings'])

    # Random non-aavin text
    assert AavinAbstractParser.is_aavin_abstract("Grocery invoice 123 banana apple") is False
    assert AavinAbstractParser.parse_aavin_abstract("Grocery invoice 123 banana apple") is None


def test_consistent_report_validation_success():
    """A report with matching math and clean fields should validate as VALIDATED."""
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    assert parsed['validation_status'] == 'VALIDATED'
    assert len(parsed['validation_warnings']) == 0
    assert parsed['milk_total_litres'] == '48941.100'
    assert parsed['grand_total_litres'] == '49135.095'


def test_product_vs_subtotal_and_grand_total_rows():
    """Verify separation of PRODUCT, SUBTOTAL, and GRAND_TOTAL row types."""
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed['items']
    products = [i for i in items if i['row_type'] == 'PRODUCT']
    subtotals = [i for i in items if i['row_type'] == 'SUBTOTAL']
    grand_totals = [i for i in items if i['row_type'] == 'GRAND_TOTAL']

    assert len(products) == 9
    assert len(subtotals) == 2  # MILK TOTAL and CURD & BUTTERMILK TOTAL
    assert len(grand_totals) == 1
    assert grand_totals[0]['product_name'] == 'GRAND TOTAL'


def test_database_persistence_and_duplicate_prevention():
    """Verify report storage, item foreign keys, and idempotency on duplicate submission."""
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed.pop('items')

    # Save first time
    rep1 = reports_store.save_or_reconcile_report(parsed, items)
    assert rep1['id'] is not None
    assert len(rep1['items']) == 12

    # Save same report second time (same union_code, report_date, shift)
    rep2 = reports_store.save_or_reconcile_report(parsed, items)
    assert rep2['id'] == rep1['id']  # Did NOT create duplicate ID

    # Query all reports
    all_reports = reports_store.list_reports(report_date=parsed['report_date'])
    assert len(all_reports) == 1


def test_timezone_conversion_to_asia_kolkata():
    """Timestamps must convert accurately to Asia/Kolkata (IST)."""
    utc_time = "2026-10-21T05:30:00+00:00"
    ist_str = format_ist_timestamp(utc_time)
    assert "IST" in ist_str
    assert "11:00:00 AM" in ist_str


def test_email_html_and_plaintext_generation():
    """Verify email formatting, right alignment, IST timestamps, and badges."""
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed.pop('items')
    saved = reports_store.save_or_reconcile_report(parsed, items)

    subject, plain_text, html_body = AavinReportEmailService.generate_email_content(saved)

    assert subject == "Aavin Production Abstract | 22-10-2026 | Morning Shift"
    assert "THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD." in plain_text
    assert "PRODUCTION ABSTRACT REPORT" in plain_text
    assert "MILK TOTAL" in plain_text
    assert "GRAND TOTAL" in plain_text

    # HTML tests
    assert "<table" in html_body
    assert "text-align: right;" in html_body  # Numeric alignment
    assert "Validated" in html_body
    assert "Consolas" in html_body
    assert "49,135.095" in html_body


def test_email_sending_mocked_smtp_success_and_duplicate_prevention():
    """Verify SMTP dispatch, updating sent timestamp, and preventing duplicate automatic sends."""
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed.pop('items')
    saved = reports_store.save_or_reconcile_report(parsed, items)

    with patch('app.config.REPORT_EMAIL_ENABLED', True), \
         patch('app.config.SMTP_HOST', 'smtp.example.com'), \
         patch('app.config.SMTP_FROM_EMAIL', 'reports@aavin.test'), \
         patch('smtplib.SMTP') as mock_smtp_class:

        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # 1. First send
        res1 = AavinReportEmailService.send_report_email(
            saved['id'],
            recipients=['officer@aavin.test']
        )
        assert res1['success'] is True
        assert res1['status'] == 'SENT'
        mock_smtp.sendmail.assert_called_once()

        # Check DB status
        updated_rep = reports_store.get_report(saved['id'])
        assert updated_rep['email_status'] == 'SENT'
        assert updated_rep['email_sent_at'] is not None

        # 2. Second send attempt without force (Idempotency)
        res2 = AavinReportEmailService.send_report_email(
            saved['id'],
            recipients=['officer@aavin.test'],
            force=False
        )
        assert res2['skipped'] is True  # Duplicate email prevented!
        assert mock_smtp.sendmail.call_count == 1  # Not sent again!


def test_email_sending_mocked_smtp_failure_handling():
    """Verify SMTP error is safely caught and logged without exposing secrets."""
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed.pop('items')
    saved = reports_store.save_or_reconcile_report(parsed, items)

    with patch('app.config.REPORT_EMAIL_ENABLED', True), \
         patch('app.config.SMTP_HOST', 'smtp.example.com'), \
         patch('app.config.SMTP_FROM_EMAIL', 'reports@aavin.test'), \
         patch('smtplib.SMTP', side_effect=Exception("Connection refused")):

        res = AavinReportEmailService.send_report_email(
            saved['id'],
            recipients=['officer@aavin.test'],
            force=True
        )
        assert res['success'] is False
        assert res['status'] == 'FAILED'
        assert "Connection refused" in res['error']

        rep = reports_store.get_report(saved['id'])
        assert rep['email_status'] == 'FAILED'


def test_needs_review_approval_workflow():
    """Reports with NEEDS_REVIEW cannot send until approved."""
    parsed = AavinAbstractParser.parse_aavin_abstract(SAMPLE_OCR_PROMPT_TEXT)
    items = parsed.pop('items')
    saved = reports_store.save_or_reconcile_report(parsed, items)

    assert saved['validation_status'] == 'NEEDS_REVIEW'

    with patch('app.config.REPORT_EMAIL_ENABLED', True):
        # Sending should be blocked because it's not approved
        res_blocked = AavinReportEmailService.send_report_email(saved['id'], recipients=['test@aavin.test'])
        assert res_blocked['success'] is False
        assert res_blocked['status'] == 'NEEDS_REVIEW'

        # Now approve report
        approved = reports_store.approve_report(saved['id'], approved_by='supervisor_tamil', notes='Discrepancy noted and cleared')
        assert approved['validation_status'] == 'VALIDATED'
        assert approved['approved_by'] == 'supervisor_tamil'

        # After approval, sending succeeds
        with patch('smtplib.SMTP') as mock_smtp_class:
            mock_smtp = MagicMock()
            mock_smtp_class.return_value = mock_smtp
            res_after = AavinReportEmailService.send_report_email(saved['id'], recipients=['test@aavin.test'])
            assert res_after['success'] is True
            assert res_after['status'] == 'SENT'


def test_reports_api_endpoints():
    """Verify all REST API endpoints for reports."""
    # 1. POST /api/reports/ocr
    resp = client.post('/api/reports/ocr', json={'raw_text': PERFECT_OCR_TEXT})
    assert resp.status_code == 201
    rep_id = resp.json()['id']

    # 2. GET /api/reports
    resp = client.get('/api/reports')
    assert resp.status_code == 200
    assert any(r['id'] == rep_id for r in resp.json())

    # 3. GET /api/reports/{id}
    resp = client.get(f'/api/reports/{rep_id}')
    assert resp.status_code == 200
    assert resp.json()['report_date'] == '2026-10-22'

    # 4. GET /api/reports/{id}/email-preview
    resp = client.get(f'/api/reports/{rep_id}/email-preview')
    assert resp.status_code == 200
    assert 'html' in resp.json()
    assert 'subject' in resp.json()

    # 5. GET /api/reports/{id}/email-preview?html_only=true
    resp = client.get(f'/api/reports/{rep_id}/email-preview?html_only=true')
    assert resp.status_code == 200
    assert resp.headers['content-type'].startswith('text/html')

    # 6. GET /api/reports/{id}/email-status
    resp = client.get(f'/api/reports/{rep_id}/email-status')
    assert resp.status_code == 200
    assert 'email_status' in resp.json()

    # 7. POST /api/reports/{id}/approve
    resp = client.post(f'/api/reports/{rep_id}/approve', json={'approved_by': 'chief_dairy_officer', 'send_email': False})
    assert resp.status_code == 200
    assert resp.json()['validation_status'] == 'VALIDATED'

    # 8. GET /api/health
    resp = client.get('/api/health')
    assert resp.status_code == 200
    assert resp.json()['reports_subsystem'] == 'ready'
    assert 'reporting' in resp.json()


def test_acceptance_two_different_live_ocr_reports_and_job_isolation():
    """
    Acceptance test: Process two different OCR reports with different dates, shifts,
    products, and quantities. Verify that each email contains ONLY the data extracted from
    its corresponding OCR execution, both reports are stored independently in the database,
    and retrying a completed job does not send another email.
    """
    report1_ocr = (
        "GA1301 THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD., "
        "SIVAGANGAI MAIN ROAD, MADURAI - 625 020 DATE 21.10.2026 SHIFT: EVENING "
        "ABSTRACT NO. TYPE OF PRODUCT QTY (LTR) QTY (PKT) TRAY "
        "1 COW MILK 500 ML 25776.500 51553 2148.001 "
        "2 CM 200 ML 4763.600 23818 476.181 "
        "3 AAVIN GOLD 500 ML 12321.000 24642 1026.181 "
        "4 TEA MATE PLUS-1000ML 5547.000 5547 462.031 "
        "5 TEAMATE 500 ML 533.000 1066 44.101 "
        "MILK TOTAL 48941.100 106626 4156.001 "
        "6 CURD 200 GM CUP 4.800 24 1.001 "
        "7 CURD 500 GM 107.000 214 8.221 "
        "8 CURD 145 ML 69.455 479 7.591 "
        "9 BUTTERMILK 140 ML 12.740 91 1.311 "
        "CURD & BUTTERMILK TOTAL 193.995 808 17.001 "
        "GRAND TOTAL 49135.095 107434 4173.001"
    )

    report2_ocr = (
        "GA1301 THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD., "
        "SIVAGANGAI MAIN ROAD, MADURAI - 625 020 DATE 24.10.2026 SHIFT: MORNING "
        "ABSTRACT NO. TYPE OF PRODUCT QTY (LTR) QTY (PKT) TRAY "
        "1 COW MILK 500 ML 1068.500 2137 89.010 "
        "2 CM 200 ML 389.000 1945 38.450 "
        "3 AAVIN GOLD 500 ML 583.000 1166 48.140 "
        "4 TEA MATE PLUS-1000ML 105.000 105 8.090 "
        "5 TEAMATE 500 ML 9.000 18 0.180 "
        "MILK TOTAL 2154.500 5371 183.870 "
        "6 CURD 500 GM 14.000 28 1.040 "
        "CURD & BUTTERMILK TOTAL 14.000 28 1.040 "
        "GRAND TOTAL 2168.500 5399 184.910"
    )

    with patch('app.config.REPORT_EMAIL_ENABLED', True), \
         patch('app.config.SMTP_HOST', 'smtp.aavin.test'), \
         patch('app.config.SMTP_FROM_EMAIL', 'reports@aavin.test'), \
         patch('smtplib.SMTP') as mock_smtp_class:

        mock_smtp = MagicMock()
        mock_smtp_class.return_value = mock_smtp

        # 1. Ingest Report 1
        resp1 = client.post('/api/reports/ocr', json={'raw_text': report1_ocr})
        assert resp1.status_code == 201
        rep1_id = resp1.json()['id']

        # 2. Ingest Report 2
        resp2 = client.post('/api/reports/ocr', json={'raw_text': report2_ocr})
        assert resp2.status_code == 201
        rep2_id = resp2.json()['id']

        # Verify independent IDs and independent database rows
        assert rep1_id != rep2_id
        db_rep1 = reports_store.get_report(rep1_id)
        db_rep2 = reports_store.get_report(rep2_id)

        assert db_rep1['report_date'] == '2026-10-21'
        assert db_rep1['shift'] == 'EVENING'
        assert db_rep1['grand_total_litres'] == '49135.095'

        assert db_rep2['report_date'] == '2026-10-24'
        assert db_rep2['shift'] == 'MORNING'
        assert db_rep2['grand_total_litres'] == '2168.500'

        # Generate emails for both
        subj1, plain1, html1 = AavinReportEmailService.generate_email_content(db_rep1)
        subj2, plain2, html2 = AavinReportEmailService.generate_email_content(db_rep2)

        # Verify Report 1 email contains only Report 1 data
        assert "21-10-2026 | Evening Shift" in subj1
        assert "49,135.095" in html1
        assert "2168.500" not in html1
        assert "24-10-2026" not in html1

        # Verify Report 2 email contains only Report 2 data
        assert "24-10-2026 | Morning Shift" in subj2
        assert "2,168.500" in html2
        assert "49135.095" not in html2
        assert "21-10-2026" not in html2

        # Verify mock email dispatch
        mock_smtp.reset_mock()
        AavinReportEmailService.send_report_email(rep1_id, recipients=['officer@aavin.test'], force=True)
        assert mock_smtp.sendmail.call_count == 1

        # Retry sending Report 1 (duplicate prevention)
        retry_res = AavinReportEmailService.send_report_email(rep1_id, recipients=['officer@aavin.test'], force=False)
        assert retry_res['skipped'] is True
        # Call count must still be 1!
        assert mock_smtp.sendmail.call_count == 1


def test_get_and_update_recipient_settings():
    """Verify retrieval and updating of default email recipients and delivery preferences."""
    # 1. GET recipients
    get_res = client.get('/api/reports/settings/recipients')
    assert get_res.status_code == 200
    data = get_res.json()
    assert 'recipients' in data
    assert isinstance(data['recipients'], list)

    # 2. PUT with valid emails and preferences (mock config.update_report_recipients)
    mock_ret = [
        {'email': 'new1@test.com', 'send_pdf': True, 'send_excel': False},
        {'email': 'new2@test.com', 'send_pdf': True, 'send_excel': True}
    ]
    with patch('app.config.update_report_recipients', return_value=mock_ret):
        put_res = client.put('/api/reports/settings/recipients', json={
            'recipients': [
                {'email': 'new1@test.com', 'send_pdf': True, 'send_excel': False},
                {'email': 'new2@test.com', 'send_pdf': True, 'send_excel': True}
            ]
        })
        assert put_res.status_code == 200
        assert put_res.json()['success'] is True
        assert len(put_res.json()['recipients']) == 2
        assert put_res.json()['recipients'][1]['send_excel'] is True

    # 3. PUT with invalid email format
    bad_res = client.put('/api/reports/settings/recipients', json={
        'recipients': ['not-an-email']
    })
    assert bad_res.status_code == 400
    assert 'Invalid email format' in bad_res.json()['detail']

    # 4. PUT with empty recipients
    empty_res = client.put('/api/reports/settings/recipients', json={
        'recipients': []
    })
    assert empty_res.status_code in (400, 422)


def test_pdf_and_excel_generation():
    """Verify that PDF and Excel files are generated cleanly without exceptions."""
    from app.services.aavin_excel import generate_aavin_excel
    from app.services.aavin_pdf import generate_aavin_pdf

    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed.pop('items')
    report = reports_store.save_or_reconcile_report(parsed, items, user='test')

    pdf_bytes = generate_aavin_pdf(report)
    excel_bytes = generate_aavin_excel(report)

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b'%PDF-')

    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 1000
    # ZIP header for xlsx
    assert excel_bytes.startswith(b'PK')


def test_individual_email_dispatch_with_attachment_selection():
    """
    Verify delivery matrix:
    - Recipient 1: send_pdf=True, send_excel=False -> Gets separate email with PDF attached.
    - Recipient 2: send_pdf=True, send_excel=True  -> Gets separate email with PDF + Excel attached.
    - Recipient 3: send_pdf=False, send_excel=False -> Muted! Skipped entirely.
    """
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed.pop('items')
    report = reports_store.save_or_reconcile_report(parsed, items, user='test')
    rep_id = report['id']

    custom_recipients = [
        {'email': 'pdf_only@test.com', 'send_pdf': True, 'send_excel': False},
        {'email': 'both@test.com', 'send_pdf': True, 'send_excel': True},
        {'email': 'muted@test.com', 'send_pdf': False, 'send_excel': False},
    ]

    mock_smtp = MagicMock()
    with patch('smtplib.SMTP', return_value=mock_smtp), \
         patch('app.config.SMTP_HOST', 'smtp.test.local'), \
         patch('app.config.SMTP_PORT', 587), \
         patch('app.config.REPORT_EMAIL_ENABLED', True):

        res = AavinReportEmailService.send_report_email(rep_id, recipients=custom_recipients, force=True)

        assert res['success'] is True
        assert res['status'] == 'SENT'
        # Two separate emails sent, muted is skipped!
        assert mock_smtp.sendmail.call_count == 2
        assert res['delivered_recipients'] == ['pdf_only@test.com', 'both@test.com']
        assert res['skipped_recipients'] == ['muted@test.com']

        # Inspect sent email arguments
        calls = mock_smtp.sendmail.call_args_list
        # Call 1: pdf_only@test.com
        assert calls[0][0][1] == ['pdf_only@test.com']
        msg_raw_1 = calls[0][0][2]
        assert 'Content-Disposition: attachment; filename="Aavin_Production_Abstract_' in msg_raw_1
        assert '.pdf"' in msg_raw_1
        assert '.xlsx"' not in msg_raw_1

        # Call 2: both@test.com
        assert calls[1][0][1] == ['both@test.com']
        msg_raw_2 = calls[1][0][2]
        assert '.pdf"' in msg_raw_2
        assert '.xlsx"' in msg_raw_2


def test_all_recipients_muted_skips_dispatch():
    """Verify that if all recipients have both options unticked, no email is sent."""
    parsed = AavinAbstractParser.parse_aavin_abstract(PERFECT_OCR_TEXT)
    items = parsed.pop('items')
    report = reports_store.save_or_reconcile_report(parsed, items, user='test')

    all_muted = [
        {'email': 'muted1@test.com', 'send_pdf': False, 'send_excel': False},
        {'email': 'muted2@test.com', 'send_pdf': False, 'send_excel': False},
    ]

    mock_smtp = MagicMock()
    with patch('smtplib.SMTP', return_value=mock_smtp), \
         patch('app.config.REPORT_EMAIL_ENABLED', True):
        res = AavinReportEmailService.send_report_email(report['id'], recipients=all_muted, force=True)
        assert res['success'] is True
        assert res['status'] == 'SKIPPED'
        assert mock_smtp.sendmail.call_count == 0


def test_admin_authentication_and_sender_settings():
    """Verify admin login, token verification, password change, and sender settings."""
    # 1. Login with bad credentials
    bad_login = client.post('/api/reports/settings/admin/login', json={'username': 'admin', 'password': 'wrongpassword'})
    assert bad_login.status_code == 401

    # 2. Login with initial default admin credentials (admin / admin123)
    login_res = client.post('/api/reports/settings/admin/login', json={'username': 'admin', 'password': 'admin123'})
    assert login_res.status_code == 200
    token = login_res.json()['token']
    assert token is not None

    headers = {'Authorization': f'Bearer {token}'}

    # 3. Verify session
    verify_res = client.post('/api/reports/settings/admin/verify', headers=headers)
    assert verify_res.status_code == 200
    assert verify_res.json()['username'] == 'admin'

    # 4. Get mail settings
    mail_res = client.get('/api/reports/settings/mail')
    assert mail_res.status_code == 200
    assert 'sender' in mail_res.json()
    assert 'recipients' in mail_res.json()

    # 5. Update sender settings with admin auth
    with patch('app.config.update_sender_settings', return_value={'smtp_user': 'new_sender@aavin.gov.in'}):
        sender_res = client.put('/api/reports/settings/sender', headers=headers, json={
            'smtp_host': 'smtp.gmail.com',
            'smtp_port': 587,
            'smtp_user': 'new_sender@aavin.gov.in',
            'smtp_password': 'secret_app_password',
            'smtp_from_email': 'new_sender@aavin.gov.in',
            'smtp_from_name': 'Official Aavin Reports',
            'smtp_use_tls': True,
            'smtp_use_ssl': False
        })
        assert sender_res.status_code == 200
        assert sender_res.json()['success'] is True

    # 6. Unauthenticated update attempt should be rejected with 401
    unauth_res = client.put('/api/reports/settings/sender', json={
        'smtp_user': 'hacker@test.com'
    })
    assert unauth_res.status_code == 401





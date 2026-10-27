import os
import uuid
import pytest
from app import store, reports_store
from app.db import get_connection, is_postgres, DBAdapter


@pytest.mark.skipif(not os.getenv('DB_HOST'), reason="PostgreSQL not configured in environment")
def test_postgres_connection_and_pool():
    """Verify active connection to PostgreSQL and query execution."""
    os.environ['USE_POSTGRES_TESTS'] = '1'
    try:
        assert is_postgres() is True
        with get_connection() as db:
            assert db.is_postgres is True
            row = db.execute("SELECT 1 AS num").fetchone()
            assert row['num'] == 1
    finally:
        os.environ.pop('USE_POSTGRES_TESTS', None)


@pytest.mark.skipif(not os.getenv('DB_HOST'), reason="PostgreSQL not configured in environment")
def test_postgres_document_store_and_fetch():
    """Verify document store, fetch, update, and summary processes on PostgreSQL."""
    os.environ['USE_POSTGRES_TESTS'] = '1'
    test_id = f"pg-test-{uuid.uuid4()}"
    try:
        doc = {
            'id': test_id,
            'name': 'test_pg_doc.png',
            'created_at': '2026-10-27T10:00:00Z',
            'status': 'complete',
            'pages': [{'index': 0, 'image': 'p0.png', 'width': 100, 'height': 100}],
            'lines': [
                {'id': '0:0', 'page_index': 0, 'reading_order': 0, 'raw_text': 'தமிழ்', 'corrected_text': None, 'confidence': 0.9, 'reviewed': False}
            ],
            'history': [],
            'completed_pages': 1,
            'error': None
        }
        # 1. Store
        store.save(doc)

        # 2. Fetch
        fetched = store.get(test_id)
        assert fetched is not None
        assert fetched['id'] == test_id
        assert fetched['name'] == 'test_pg_doc.png'
        assert len(fetched['lines']) == 1

        # 3. Correct (Update line & history)
        corrected = store.correct(test_id, '0:0', 'தமிழ் திருத்தம்', reviewed=True)
        assert corrected['lines'][0]['corrected_text'] == 'தமிழ் திருத்தம்'
        assert corrected['lines'][0]['reviewed'] is True
        assert len(corrected['history']) == 1

        # 4. Summaries
        summaries = store.summaries()
        assert any(s['id'] == test_id for s in summaries)

    finally:
        # Clean up test document
        with get_connection() as db:
            db.execute("DELETE FROM documents WHERE id = ?", (test_id,))
        os.environ.pop('USE_POSTGRES_TESTS', None)


@pytest.mark.skipif(not os.getenv('DB_HOST'), reason="PostgreSQL not configured in environment")
def test_postgres_report_store_and_fetch():
    """Verify report store, item relationship, audit log, and fetch processes on PostgreSQL."""
    os.environ['USE_POSTGRES_TESTS'] = '1'
    test_union = f"U_{uuid.uuid4().hex[:6]}"
    report_data = {
        'union_code': test_union,
        'organization_name': 'Madurai Aavin Union',
        'address': 'Madurai 625020',
        'report_date': '2026-10-27',
        'shift': 'MORNING',
        'abstract_no': 'ABS-TEST',
        'milk_total_litres': '1000.000',
        'milk_total_packets': 2000,
        'milk_total_trays': '83.333',
        'curd_buttermilk_total_litres': '100.000',
        'curd_buttermilk_total_packets': 500,
        'curd_buttermilk_total_trays': '10.000',
        'grand_total_litres': '1100.000',
        'grand_total_packets': 2500,
        'grand_total_trays': '93.333',
        'raw_ocr_text': 'RAW OCR SAMPLE',
        'validation_status': 'VALIDATED',
        'validation_warnings': [],
        'email_status': 'PENDING',
        'ocr_created_at': '2026-10-27T10:00:00Z',
        'report_processed_at': '2026-10-27T10:01:00Z'
    }
    items = [
        {
            'item_no': 1,
            'product_name': 'COW MILK 500 ML',
            'category': 'MILK',
            'quantity_litres': '1000.000',
            'quantity_packets': 2000,
            'quantity_trays': '83.333',
            'row_type': 'PRODUCT'
        }
    ]
    try:
        # 1. Store report
        saved = reports_store.save_or_reconcile_report(report_data, items, user='test_runner')
        rep_id = saved['id']
        assert saved['union_code'] == test_union
        assert saved['validation_status'] == 'VALIDATED'

        # 2. Fetch report with items & audit logs
        fetched = reports_store.get_report(rep_id)
        assert fetched is not None
        assert fetched['id'] == rep_id
        assert len(fetched['items']) == 1
        assert fetched['items'][0]['product_name'] == 'COW MILK 500 ML'
        assert len(fetched['audit_logs']) >= 1

        # 3. List reports with filter
        listed = reports_store.list_reports(report_date='2026-10-27', shift='MORNING')
        assert any(r['id'] == rep_id for r in listed)

        # 4. Update status & approve
        updated = reports_store.update_email_status(rep_id, 'SENT', sent_at='2026-10-27T10:05:00Z')
        assert updated['email_status'] == 'SENT'

        approved = reports_store.approve_report(rep_id, approved_by='admin', notes='Verified ok')
        assert approved['validation_status'] == 'VALIDATED'
        assert approved['approved_by'] == 'admin'

    finally:
        # Clean up test report
        with get_connection() as db:
            db.execute("DELETE FROM reports WHERE union_code = ?", (test_union,))
        os.environ.pop('USE_POSTGRES_TESTS', None)

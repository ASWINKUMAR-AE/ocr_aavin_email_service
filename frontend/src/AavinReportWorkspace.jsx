import { useEffect, useState } from 'react';
import { Mail, CheckCircle2, AlertTriangle, RefreshCw, Send, ShieldCheck, Eye, EyeOff, FileSpreadsheet } from 'lucide-react';
import { request } from './api';

export default function AavinReportWorkspace({ doc, onBack }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [approving, setApproving] = useState(false);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    loadReport();
  }, [doc?.id]);

  async function loadReport() {
    setLoading(true);
    setError('');
    setActionMsg('');
    try {
      // 1. Try to find report by document_id or matching list
      const list = await request('/reports');
      const matching = list.find(r => r.document_id === doc.id);
      if (matching) {
        const full = await request(`/reports/${matching.id}`);
        setReport(full);
      } else {
        // Try parsing from this document's text
        try {
          const parsed = await request('/reports/ocr', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ document_id: doc.id })
          });
          const full = await request(`/reports/${parsed.id}`);
          setReport(full);
        } catch {
          // Document might not be an Aavin abstract report
          setReport(null);
        }
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  async function handleApprove() {
    if (!report) return;
    setApproving(true);
    try {
      const res = await request(`/reports/${report.id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ approved_by: 'supervisor_user', notes: 'Manually verified in OCR Studio' })
      });
      setReport(res);
      setActionMsg('Report successfully approved! Validation status is now VALIDATED.');
    } catch (e) {
      setError(`Approval failed: ${e.message}`);
    } finally {
      setApproving(false);
    }
  }

  async function handleSendEmail(force = false) {
    if (!report) return;
    setSending(true);
    setError('');
    setActionMsg('');
    try {
      const res = await request(`/reports/${report.id}/send-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force })
      });
      if (res.skipped) {
        setActionMsg(`Email dispatch skipped: ${res.message}`);
      } else if (res.dry_run) {
        setActionMsg(`Dry-run simulation: ${res.message}`);
      } else {
        setActionMsg(`Email successfully sent to ${res.recipients?.join(', ')}!`);
      }
      // Refresh report
      const updated = await request(`/reports/${report.id}`);
      setReport(updated);
    } catch (e) {
      setError(`Email send error: ${e.message}`);
    } finally {
      setSending(false);
    }
  }

  async function toggleEmailPreview() {
    if (previewOpen) {
      setPreviewOpen(false);
      return;
    }
    if (!report) return;
    try {
      const prev = await request(`/reports/${report.id}/email-preview`);
      setPreviewHtml(prev.html);
      setPreviewOpen(true);
    } catch (e) {
      setError(`Cannot load email preview: ${e.message}`);
    }
  }

  if (loading) {
    return (
      <div className="table-workspace-card" style={{ padding: '3rem', textAlign: 'center' }}>
        <p className="muted">Analyzing and loading Aavin production report data…</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="table-workspace-card" style={{ padding: '2.5rem', textAlign: 'center' }}>
        <FileSpreadsheet size={40} style={{ opacity: 0.6, marginBottom: '1rem', color: '#0284c7' }} />
        <h3>No Aavin Abstract Detected</h3>
        <p className="muted" style={{ maxWidth: '480px', margin: '0 auto 1.5rem auto' }}>
          This page does not appear to be an official Aavin Milk Production Abstract report, or the OCR text did not contain abstract keywords.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
          <button className="primary" onClick={loadReport}><RefreshCw size={15} /> Retry extraction</button>
          <button onClick={onBack}>Back to lines</button>
        </div>
      </div>
    );
  }

  const items = report.items || [];
  const isValid = report.validation_status === 'VALIDATED';

  return (
    <div className="aavin-workspace" style={{ background: 'var(--card, #ffffff)', borderRadius: '12px', padding: '1.75rem', border: '1px solid var(--border, #e2e8f0)', marginTop: '1rem' }}>
      
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', borderBottom: '1px solid var(--border, #e2e8f0)', paddingBottom: '1.25rem', marginBottom: '1.25rem' }}>
        <div>
          <span style={{ fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#0284c7' }}>
            Aavin Production Abstract &bull; Union Code {report.union_code}
          </span>
          <h2 style={{ margin: '0.25rem 0', fontSize: '1.25rem', fontWeight: 700 }}>
            {report.organization_name}
          </h2>
          <p className="muted" style={{ margin: 0, fontSize: '0.85rem' }}>
            {report.address} &bull; <strong>Date:</strong> {report.report_date} &bull; <strong>Shift:</strong> {report.shift}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span className={`pill ${isValid ? 'pill-success' : 'pill-warning'}`} style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.8rem', fontWeight: 600, background: isValid ? '#dcfce7' : '#fef3c7', color: isValid ? '#166534' : '#9a3412', border: `1px solid ${isValid ? '#bbf7d0' : '#fed7aa'}` }}>
            {isValid ? <><CheckCircle2 size={13} style={{ display: 'inline', marginRight: 4 }} /> Validated</> : <><AlertTriangle size={13} style={{ display: 'inline', marginRight: 4 }} /> Needs Review</>}
          </span>
          <span className="pill" style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.8rem', fontWeight: 600, background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}>
            Email: {report.email_status}
          </span>
        </div>
      </div>

      {/* Notifications */}
      {error && <div className="error-banner" role="alert" style={{ marginBottom: '1rem' }}>{error}</div>}
      {actionMsg && <div className="notice" style={{ marginBottom: '1rem', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0' }}>{actionMsg}</div>}

      {/* Validation Warnings */}
      {report.validation_warnings?.length > 0 && (
        <div style={{ background: '#fffbeb', border: '1px solid #fde68a', borderRadius: '8px', padding: '1rem', marginBottom: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600, color: '#92400e', marginBottom: '0.5rem' }}>
            <AlertTriangle size={16} /> Discrepancies & Audit Warnings
          </div>
          <ul style={{ margin: 0, paddingLeft: '1.25rem', color: '#b45309', fontSize: '0.85rem' }}>
            {report.validation_warnings.map((w, idx) => (
              <li key={idx} style={{ marginBottom: '0.25rem' }}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Action Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          {!isValid && (
            <button className="primary" disabled={approving} onClick={handleApprove}>
              <ShieldCheck size={16} /> {approving ? 'Approving…' : 'Approve Report'}
            </button>
          )}
          <button className="primary" disabled={sending} onClick={() => handleSendEmail(false)}>
            <Send size={16} /> {sending ? 'Sending…' : report.email_status === 'SENT' ? 'Resend Email' : 'Send Email Report'}
          </button>
          {report.email_status === 'SENT' && (
            <button disabled={sending} onClick={() => handleSendEmail(true)}>
              Force Resend
            </button>
          )}
          <button onClick={toggleEmailPreview}>
            {previewOpen ? <><EyeOff size={16} /> Close Preview</> : <><Eye size={16} /> Preview Email</>}
          </button>
        </div>
        <button onClick={onBack}>Back to workspace</button>
      </div>

      {/* Email HTML Preview Drawer */}
      {previewOpen && (
        <div style={{ border: '1px solid #cbd5e1', borderRadius: '8px', marginBottom: '1.5rem', background: '#f8fafc', overflow: 'hidden' }}>
          <div style={{ background: '#0b3c68', color: '#ffffff', padding: '0.75rem 1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600 }}>Live Responsive HTML Email Preview</span>
            <button style={{ color: '#bae6fd', background: 'transparent', border: 'none', cursor: 'pointer', fontSize: '0.85rem' }} onClick={() => setPreviewOpen(false)}>Close</button>
          </div>
          <iframe
            title="Email Preview"
            srcDoc={previewHtml}
            style={{ width: '100%', height: '540px', border: 'none', background: '#f8fafc' }}
          />
        </div>
      )}

      {/* Production Abstract Report Table */}
      <div style={{ overflowX: 'auto', border: '1px solid var(--border, #e2e8f0)', borderRadius: '8px' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.9rem' }}>
          <thead>
            <tr style={{ background: '#0b3c68', color: '#ffffff' }}>
              <th style={{ padding: '10px 14px', width: '6%', textAlign: 'center' }}>No.</th>
              <th style={{ padding: '10px 14px', width: '38%' }}>Type of Product</th>
              <th style={{ padding: '10px 14px', width: '20%', textAlign: 'right' }}>Qty (Ltr)</th>
              <th style={{ padding: '10px 14px', width: '18%', textAlign: 'right' }}>Qty (Pkt)</th>
              <th style={{ padding: '10px 14px', width: '18%', textAlign: 'right' }}>Tray</th>
            </tr>
          </thead>
          <tbody>
            {items.map((row, idx) => {
              const isGrand = row.row_type === 'GRAND_TOTAL';
              const isSub = row.row_type === 'SUBTOTAL';
              const bg = isGrand ? '#e0f2fe' : isSub ? '#f1f5f9' : (idx % 2 === 0 ? 'var(--bg, #ffffff)' : 'var(--bg-alt, #fbfcfe)');
              const fw = (isGrand || isSub) ? 700 : 400;
              const color = isGrand ? '#0369a1' : isSub ? '#0f172a' : 'inherit';

              return (
                <tr key={row.id || idx} style={{ background: bg, fontWeight: fw, color: color, borderBottom: '1px solid var(--border, #e2e8f0)' }}>
                  <td style={{ padding: '9px 14px', textAlign: 'center' }}>{isSub || isGrand ? '' : row.item_no}</td>
                  <td style={{ padding: '9px 14px' }}>{row.product_name}</td>
                  <td style={{ padding: '9px 14px', textAlign: 'right', fontFamily: 'monospace' }}>{row.quantity_litres}</td>
                  <td style={{ padding: '9px 14px', textAlign: 'right', fontFamily: 'monospace' }}>{row.quantity_packets}</td>
                  <td style={{ padding: '9px 14px', textAlign: 'right', fontFamily: 'monospace' }}>{row.quantity_trays}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Footer Info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem', fontSize: '0.8rem', color: '#64748b' }}>
        <span>Report ID: <code style={{ color: '#0284c7' }}>{report.id}</code></span>
        <span>Processed: {new Date(report.report_processed_at || report.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST</span>
      </div>

    </div>
  );
}

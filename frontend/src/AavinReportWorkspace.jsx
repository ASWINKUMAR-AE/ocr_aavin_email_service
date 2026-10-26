import { useEffect, useState } from 'react';
import { ArrowLeft, Mail, CheckCircle2, AlertTriangle, RefreshCw, Send, ShieldCheck, Eye, EyeOff, FileSpreadsheet, XCircle, Settings, BarChart3, Table } from 'lucide-react';
import { request } from './api';
import RecipientSettingsModal, { INITIAL_DEFAULT_EMAILS } from './RecipientSettingsModal';
import AavinReportAnalytics from './AavinReportAnalytics';

const DEFAULT_SESSION_EMAILS = [
  'aswinkumarta2006@gmail.com',
  'heiwinganesh15@gmail.com'
];

function getStoredSessionEmails() {
  try {
    const raw = sessionStorage.getItem('aavin_session_emails');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed) && parsed.length > 0) {
        return Array.from(new Set([...DEFAULT_SESSION_EMAILS, ...parsed.map(e => e.trim()).filter(Boolean)]));
      }
    }
  } catch {}
  return DEFAULT_SESSION_EMAILS;
}

function addSessionEmail(email) {
  const trimmed = email?.trim();
  if (!trimmed) return;
  try {
    const current = getStoredSessionEmails();
    if (!current.includes(trimmed)) {
      const updated = [...current, trimmed];
      sessionStorage.setItem('aavin_session_emails', JSON.stringify(updated));
    }
  } catch {}
}

export default function AavinReportWorkspace({ doc, onBack }) {
  const [report, setReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [actionMsg, setActionMsg] = useState('');
  const [emailAlert, setEmailAlert] = useState(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewHtml, setPreviewHtml] = useState('');
  const [approving, setApproving] = useState(false);
  const [sending, setSending] = useState(false);
  const [sessionEmails, setSessionEmails] = useState(getStoredSessionEmails);
  const [customEmail, setCustomEmail] = useState('');
  const [sendingCustom, setSendingCustom] = useState(false);
  const [recipientModalOpen, setRecipientModalOpen] = useState(false);
  const [defaultRecipients, setDefaultRecipients] = useState(DEFAULT_SESSION_EMAILS);
  const [viewMode, setViewMode] = useState('table'); // 'table' | 'analytics'

  useEffect(() => {
    request('/reports/settings/recipients')
      .then(res => {
        if (res?.recipients?.length) {
          setDefaultRecipients(res.recipients);
          res.recipients.forEach(r => {
            const addr = typeof r === 'string' ? r : r.email;
            if (addr) addSessionEmail(addr);
          });
          setSessionEmails(getStoredSessionEmails());
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadReport();
  }, [doc?.id]);

  async function loadReport() {
    setLoading(true);
    setError('');
    setActionMsg('');
    setEmailAlert(null);
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
    setEmailAlert(null);
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

  async function handleSendEmail(force = true) {
    if (!report) return;
    setSending(true);
    setEmailAlert(null);
    setError('');
    setActionMsg('');
    try {
      const res = await request(`/reports/${report.id}/send-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ force: force ?? true })
      });
      if (res && res.success && !res.skipped) {
        setEmailAlert({
          type: 'success',
          message: 'The mail is sent successfully.'
        });
      } else {
        setEmailAlert({
          type: 'error',
          message: 'The mail could not be sent. Please try again.'
        });
      }
      // Refresh report
      try {
        const updated = await request(`/reports/${report.id}`);
        setReport(updated);
      } catch {
        // keep current report if refresh fails
      }
    } catch (e) {
      setEmailAlert({
        type: 'error',
        message: 'The mail could not be sent. Please try again.'
      });
    } finally {
      setSending(false);
    }
  }

  async function handleSendCustomEmail() {
    const trimmed = customEmail.trim();
    if (!trimmed) {
      setEmailAlert({
        type: 'error',
        message: 'Please enter or select an email address to send.'
      });
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setEmailAlert({
        type: 'error',
        message: 'Please enter a valid email address.'
      });
      return;
    }

    setSendingCustom(true);
    setEmailAlert(null);
    setError('');
    setActionMsg('');

    try {
      const res = await request(`/reports/${report.id}/send-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          recipients: [trimmed],
          force: true
        })
      });

      if (res && res.success && !res.skipped) {
        addSessionEmail(trimmed);
        setSessionEmails(getStoredSessionEmails());
        setEmailAlert({
          type: 'success',
          message: 'The mail is sent successfully.'
        });
      } else {
        setEmailAlert({
          type: 'error',
          message: res?.error || 'The mail could not be sent. Please try again.'
        });
      }

      // Refresh report
      try {
        const updated = await request(`/reports/${report.id}`);
        setReport(updated);
      } catch {
        // keep current report if refresh fails
      }
    } catch (e) {
      setEmailAlert({
        type: 'error',
        message: 'The mail could not be sent. Please try again.'
      });
    } finally {
      setSendingCustom(false);
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
      <div className="table-workspace-card" style={{ padding: '2rem', textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '1.5rem' }}>
          <button className="back-btn" onClick={onBack} aria-label="Back to OCR review">
            <ArrowLeft size={16} /> Back to OCR review
          </button>
        </div>
        <p className="muted">Analyzing and loading Aavin production report data…</p>
      </div>
    );
  }

  if (!report) {
    return (
      <div className="table-workspace-card" style={{ padding: '2.5rem', textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'flex-start', marginBottom: '1rem' }}>
          <button className="back-btn" onClick={onBack} aria-label="Back to OCR review">
            <ArrowLeft size={16} /> Back to OCR review
          </button>
        </div>
        <FileSpreadsheet size={40} style={{ opacity: 0.6, marginBottom: '1rem', color: '#0284c7' }} />
        <h3>No Aavin Abstract Detected</h3>
        <p className="muted" style={{ maxWidth: '480px', margin: '0 auto 1.5rem auto' }}>
          This page does not appear to be an official Aavin Milk Production Abstract report, or the OCR text did not contain abstract keywords.
        </p>
        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'center' }}>
          <button className="primary" onClick={loadReport}><RefreshCw size={15} /> Retry extraction</button>
          <button className="back-btn" onClick={onBack}><ArrowLeft size={16} /> Back to OCR review</button>
        </div>
      </div>
    );
  }

  const items = report.items || [];
  const isValid = report.validation_status === 'VALIDATED';

  return (
    <div className="aavin-workspace" style={{ background: 'var(--card, #ffffff)', borderRadius: '12px', padding: '1.75rem', border: '1px solid var(--border, #e2e8f0)', marginTop: '1rem' }}>
      
      {/* Top Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid var(--border, #e2e8f0)', paddingBottom: '1.25rem', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <button className="back-btn" onClick={onBack} aria-label="Back to OCR review">
            <ArrowLeft size={16} /> Back to OCR review
          </button>
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
        </div>
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            className="back-btn"
            onClick={() => setRecipientModalOpen(true)}
            data-testid="recipient-settings-btn"
            style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '6px' }}
            title="Configure sender SMTP & recipient mail settings"
          >
            <Settings size={15} /> Mail Settings
          </button>
          <span className={`pill ${isValid ? 'pill-success' : 'pill-warning'}`} style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.8rem', fontWeight: 600, background: isValid ? '#dcfce7' : '#fef3c7', color: isValid ? '#166534' : '#9a3412', border: `1px solid ${isValid ? '#bbf7d0' : '#fed7aa'}` }}>
            {isValid ? <><CheckCircle2 size={13} style={{ display: 'inline', marginRight: 4 }} /> Validated</> : <><AlertTriangle size={13} style={{ display: 'inline', marginRight: 4 }} /> Needs Review</>}
          </span>
          <span className="pill" style={{ padding: '4px 12px', borderRadius: '16px', fontSize: '0.8rem', fontWeight: 600, background: '#f1f5f9', color: '#475569', border: '1px solid #cbd5e1' }}>
            Email: {report.email_status}
          </span>
        </div>
      </div>

      {/* Notifications */}
      {emailAlert && (
        <div
          role="alert"
          data-testid="email-status-alert"
          className={`email-alert email-alert-${emailAlert.type}`}
        >
          {emailAlert.type === 'success' ? (
            <CheckCircle2 size={18} className="email-alert-icon" aria-hidden="true" />
          ) : (
            <XCircle size={18} className="email-alert-icon" aria-hidden="true" />
          )}
          <span>{emailAlert.message}</span>
        </div>
      )}
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
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
          {!isValid && (
            <button className="primary" disabled={approving} onClick={handleApprove}>
              <ShieldCheck size={16} /> {approving ? 'Approving…' : 'Approve Report'}
            </button>
          )}
          <button className="primary" disabled={sending || sendingCustom} onClick={() => handleSendEmail(true)}>
            <Send size={16} /> {sending ? 'Sending…' : report.email_status === 'SENT' ? 'Resend Email' : 'Send Email Report'}
          </button>
          {report.email_status === 'SENT' && (
            <button disabled={sending || sendingCustom} onClick={() => handleSendEmail(true)}>
              Force Resend
            </button>
          )}
          <button onClick={toggleEmailPreview}>
            {previewOpen ? <><EyeOff size={16} /> Close Preview</> : <><Eye size={16} /> Preview Email</>}
          </button>

          {/* Email dispatch bar with session dropdown */}
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', background: 'var(--soft, #f1f5f9)', padding: '3px 6px', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)' }}>
            <select
              aria-label="Session email recipients"
              data-testid="session-email-select"
              value={sessionEmails.includes(customEmail) ? customEmail : ''}
              onChange={(e) => { if (e.target.value) setCustomEmail(e.target.value); }}
              style={{ fontSize: '0.8rem', padding: '5px 6px', borderRadius: '4px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)', color: 'var(--text, #1e293b)', maxWidth: '170px' }}
            >
              <option value="">Session recipients…</option>
              {sessionEmails.map((email) => (
                <option key={email} value={email}>
                  {email}
                </option>
              ))}
            </select>
            <input
              type="email"
              aria-label="Custom email recipient"
              data-testid="custom-email-input"
              placeholder="Or enter email to send…"
              value={customEmail}
              onChange={(e) => setCustomEmail(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handleSendCustomEmail(); } }}
              style={{ fontSize: '0.8rem', padding: '5px 8px', borderRadius: '4px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)', color: 'var(--text, #1e293b)', minWidth: '190px' }}
            />
            <button
              className="primary"
              disabled={sendingCustom || sending || !customEmail.trim()}
              data-testid="custom-email-send-btn"
              onClick={handleSendCustomEmail}
              style={{ fontSize: '0.8rem', padding: '5px 10px' }}
              title="Send report to this email address"
            >
              <Send size={13} /> {sendingCustom ? 'Sending…' : 'Send'}
            </button>
          </div>
        </div>
        <button className="back-btn" onClick={onBack} aria-label="Back to OCR review">
          <ArrowLeft size={16} /> Back to OCR review
        </button>
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

      {/* View Switcher: Report Table vs Visual Analytics */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div style={{ display: 'inline-flex', background: 'var(--soft, #f1f5f9)', borderRadius: '8px', padding: '3px', border: '1px solid var(--border, #cbd5e1)' }}>
          <button
            data-testid="view-table-btn"
            onClick={() => setViewMode('table')}
            style={{
              background: viewMode === 'table' ? 'var(--surface, #ffffff)' : 'transparent',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '0.84rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: viewMode === 'table' ? '#0284c7' : 'var(--muted, #64748b)',
              boxShadow: viewMode === 'table' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
            }}
          >
            <Table size={15} /> Booking & Production Table
          </button>
          <button
            data-testid="view-analytics-btn"
            onClick={() => setViewMode('analytics')}
            style={{
              background: viewMode === 'analytics' ? 'var(--surface, #ffffff)' : 'transparent',
              border: 'none',
              borderRadius: '6px',
              padding: '6px 14px',
              fontSize: '0.84rem',
              fontWeight: 600,
              cursor: 'pointer',
              display: 'inline-flex',
              alignItems: 'center',
              gap: '6px',
              color: viewMode === 'analytics' ? '#0284c7' : 'var(--muted, #64748b)',
              boxShadow: viewMode === 'analytics' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none'
            }}
          >
            <BarChart3 size={15} /> Visual Analytics & Charts
          </button>
        </div>
      </div>

      {viewMode === 'analytics' ? (
        <AavinReportAnalytics report={report} />
      ) : (
        /* Production Abstract Report Table */
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
      )}

      {/* Footer Info */}
      <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '1rem', fontSize: '0.8rem', color: '#64748b' }}>
        <span>Report ID: <code style={{ color: '#0284c7' }}>{report.id}</code></span>
        <span>Processed: {new Date(report.report_processed_at || report.created_at).toLocaleString('en-IN', { timeZone: 'Asia/Kolkata' })} IST</span>
      </div>

      <RecipientSettingsModal
        isOpen={recipientModalOpen}
        onClose={() => setRecipientModalOpen(false)}
        onSaved={(newRecipients) => {
          setDefaultRecipients(newRecipients);
          const emailList = newRecipients.map(r => typeof r === 'string' ? r : r.email);
          emailList.forEach(addSessionEmail);
          setSessionEmails(getStoredSessionEmails());
          setActionMsg(`Recipient settings updated (${newRecipients.length} configured).`);
        }}
      />
    </div>
  );
}

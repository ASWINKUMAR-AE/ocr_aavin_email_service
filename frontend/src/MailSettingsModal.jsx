import { useState, useEffect } from 'react';
import { 
  Mail, Send, Lock, Key, Shield, User, Eye, EyeOff, CheckCircle2, 
  AlertTriangle, RotateCcw, X, Plus, Trash2, Server, FileText, FileSpreadsheet, Activity
} from 'lucide-react';
import { request } from './api';

export const INITIAL_DEFAULT_RECIPIENTS = [
  { role: 'GM', name: 'General Manager', email: 'aswinkumarta2006@gmail.com', send_pdf: true, send_excel: false },
  { role: 'AGM', name: 'Asst. General Manager', email: 'heiwinganesh15@gmail.com', send_pdf: true, send_excel: true },
  { role: 'AA', name: 'Administrative Assistant / Accounts', email: 'aa.aavin@gmail.com', send_pdf: true, send_excel: false }
];

export const INITIAL_DEFAULT_EMAILS = [
  'aswinkumarta2006@gmail.com',
  'heiwinganesh15@gmail.com',
  'aa.aavin@gmail.com'
];

export default function MailSettingsModal({ isOpen, onClose, onSaved }) {
  // Admin Authentication State
  const [adminToken, setAdminToken] = useState(() => sessionStorage.getItem('aavin_admin_token') || '');
  const [adminUser, setAdminUser] = useState(() => sessionStorage.getItem('aavin_admin_user') || '');
  const [loginUsername, setLoginUsername] = useState('admin');
  const [loginPassword, setLoginPassword] = useState('');
  const [loggingIn, setLoggingIn] = useState(false);
  const [loginError, setLoginError] = useState('');

  // Active Tab: 'sender' | 'recipients' | 'security'
  const [activeTab, setActiveTab] = useState('sender');

  // Sender Settings State
  const [smtpHost, setSmtpHost] = useState('smtp.gmail.com');
  const [smtpPort, setSmtpPort] = useState(587);
  const [smtpUser, setSmtpUser] = useState('');
  const [smtpPassword, setSmtpPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [smtpFromName, setSmtpFromName] = useState('Aavin OCR Reports');
  const [smtpFromEmail, setSmtpFromEmail] = useState('');
  const [smtpUseTls, setSmtpUseTls] = useState(true);
  const [smtpUseSsl, setSmtpUseSsl] = useState(false);
  const [testingConnection, setTestingConnection] = useState(false);
  const [testResult, setTestResult] = useState(null);

  // Recipient Settings State
  const [recipients, setRecipients] = useState([]);
  const [newRole, setNewRole] = useState('GM');
  const [newEmail, setNewEmail] = useState('');
  const [newSendPdf, setNewSendPdf] = useState(true);
  const [newSendExcel, setNewSendExcel] = useState(false);

  // Password Change State
  const [currentPass, setCurrentPass] = useState('');
  const [newPass, setNewPass] = useState('');
  const [confirmPass, setConfirmPass] = useState('');
  const [changingPass, setChangingPass] = useState(false);

  // General Modal State
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [successMsg, setSuccessMsg] = useState('');

  useEffect(() => {
    if (isOpen) {
      if (adminToken) {
        verifyTokenAndLoad();
      }
    }
  }, [isOpen]);

  async function verifyTokenAndLoad() {
    setLoading(true);
    setError('');
    try {
      const res = await request('/reports/settings/admin/verify', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${adminToken}` }
      });
      if (res && res.valid) {
        setAdminUser(res.username);
        loadMailSettings();
      } else {
        handleLogout();
      }
    } catch {
      handleLogout();
    } finally {
      setLoading(false);
    }
  }

  async function loadMailSettings() {
    try {
      const res = await request('/reports/settings/mail');
      if (res) {
        if (res.sender) {
          setSmtpHost(res.sender.smtp_host || 'smtp.gmail.com');
          setSmtpPort(res.sender.smtp_port || 587);
          setSmtpUser(res.sender.smtp_user || '');
          setSmtpFromEmail(res.sender.smtp_from_email || '');
          setSmtpFromName(res.sender.smtp_from_name || 'Aavin OCR Reports');
          setSmtpUseTls(res.sender.smtp_use_tls ?? true);
          setSmtpUseSsl(res.sender.smtp_use_ssl ?? false);
        }
        if (Array.isArray(res.recipients) && res.recipients.length > 0) {
          setRecipients(normalizeRecipients(res.recipients));
        } else {
          setRecipients(INITIAL_DEFAULT_RECIPIENTS);
        }
      }
    } catch (e) {
      setError('Failed to load mail settings: ' + e.message);
    }
  }

  function normalizeRecipients(list) {
    if (!Array.isArray(list)) return INITIAL_DEFAULT_RECIPIENTS;
    return list.map((item, idx) => {
      if (typeof item === 'string') {
        const defaultRoles = ['GM', 'AGM', 'AA'];
        return {
          role: defaultRoles[idx] || 'STAFF',
          name: '',
          email: item.trim(),
          send_pdf: true,
          send_excel: false
        };
      }
      return {
        role: item.role || 'STAFF',
        name: item.name || '',
        email: (item.email || '').trim(),
        send_pdf: item.send_pdf ?? true,
        send_excel: item.send_excel ?? false
      };
    }).filter(r => r.email);
  }

  // --- Admin Login Action ---
  async function handleAdminLogin(e) {
    if (e) e.preventDefault();
    setLoginError('');
    setLoggingIn(true);
    try {
      const res = await request('/reports/settings/admin/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          username: loginUsername.trim(),
          password: loginPassword
        })
      });

      if (res && res.success && res.token) {
        sessionStorage.setItem('aavin_admin_token', res.token);
        sessionStorage.setItem('aavin_admin_user', res.username);
        setAdminToken(res.token);
        setAdminUser(res.username);
        setLoginPassword('');
        loadMailSettings();
      } else {
        setLoginError('Invalid administrator username or password.');
      }
    } catch (err) {
      setLoginError(err.message || 'Login failed. Please check credentials.');
    } finally {
      setLoggingIn(false);
    }
  }

  function handleLogout() {
    sessionStorage.removeItem('aavin_admin_token');
    sessionStorage.removeItem('aavin_admin_user');
    setAdminToken('');
    setAdminUser('');
    setTestResult(null);
    setSuccessMsg('');
    setError('');
  }

  // --- Sender Settings Actions ---
  async function handleTestSender() {
    setTestingConnection(true);
    setTestResult(null);
    setError('');
    try {
      const res = await request('/reports/settings/sender/test', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${adminToken}` }
      });
      setTestResult(res);
    } catch (err) {
      setTestResult({ success: false, error: err.message });
    } finally {
      setTestingConnection(false);
    }
  }

  async function handleSaveSender() {
    setError('');
    setSuccessMsg('');
    setSaving(true);
    try {
      const res = await request('/reports/settings/sender', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminToken}`
        },
        body: JSON.stringify({
          smtp_host: smtpHost.trim(),
          smtp_port: parseInt(smtpPort, 10) || 587,
          smtp_user: smtpUser.trim(),
          smtp_password: smtpPassword.trim() || undefined,
          smtp_from_email: (smtpFromEmail || smtpUser).trim(),
          smtp_from_name: smtpFromName.trim(),
          smtp_use_tls: smtpUseTls,
          smtp_use_ssl: smtpUseSsl
        })
      });

      if (res && res.success) {
        setSuccessMsg('Sender settings updated successfully!');
        setSmtpPassword('');
      } else {
        setError(res?.error || 'Failed to save sender settings.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  // --- Recipient Settings Actions ---
  function handleAddRecipient() {
    const trimmed = newEmail.trim();
    setError('');
    setSuccessMsg('');
    if (!trimmed) return;

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) {
      setError(`"${trimmed}" is not a valid email address.`);
      return;
    }

    if (recipients.map(r => r.email.toLowerCase()).includes(trimmed.toLowerCase())) {
      setError(`"${trimmed}" is already in the recipient list.`);
      return;
    }

    setRecipients(prev => [
      ...prev,
      {
        role: newRole,
        name: newRole === 'GM' ? 'General Manager' : newRole === 'AGM' ? 'Asst. General Manager' : newRole === 'AA' ? 'Administrative Assistant' : 'Staff',
        email: trimmed,
        send_pdf: newSendPdf,
        send_excel: newSendExcel
      }
    ]);
    setNewEmail('');
    setNewSendPdf(true);
    setNewSendExcel(false);
  }

  function handleTogglePdf(idx) {
    setRecipients(prev => prev.map((r, i) => i === idx ? { ...r, send_pdf: !r.send_pdf } : r));
  }

  function handleToggleExcel(idx) {
    setRecipients(prev => prev.map((r, i) => i === idx ? { ...r, send_excel: !r.send_excel } : r));
  }

  function handleRemoveRecipient(idx) {
    if (recipients.length <= 1) {
      setError('At least one recipient must remain configured.');
      return;
    }
    setRecipients(prev => prev.filter((_, i) => i !== idx));
  }

  function handleResetToDefaults() {
    setRecipients(INITIAL_DEFAULT_RECIPIENTS);
    setError('');
    setSuccessMsg('Reset to GM, AGM, and AA defaults. Click "Save Recipients" to apply.');
  }

  async function handleSaveRecipients() {
    setError('');
    setSuccessMsg('');
    if (recipients.length === 0) {
      setError('At least one recipient email is required.');
      return;
    }

    setSaving(true);
    try {
      const res = await request('/reports/settings/recipients', {
        method: 'PUT',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminToken}`
        },
        body: JSON.stringify({ recipients })
      });

      if (res && res.success) {
        setSuccessMsg('Recipient list & designated roles updated successfully!');
        if (onSaved) {
          onSaved(res.recipients);
        }
      } else {
        setError(res?.error || 'Failed to update recipients.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  // --- Password Change Action ---
  async function handleChangePassword(e) {
    if (e) e.preventDefault();
    setError('');
    setSuccessMsg('');
    if (newPass.length < 4) {
      setError('New password must be at least 4 characters long.');
      return;
    }
    if (newPass !== confirmPass) {
      setError('New password and confirmation do not match.');
      return;
    }

    setChangingPass(true);
    try {
      const res = await request('/reports/settings/admin/change-password', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${adminToken}`
        },
        body: JSON.stringify({
          current_password: currentPass,
          new_password: newPass
        })
      });

      if (res && res.success) {
        setSuccessMsg('Admin password changed successfully!');
        setCurrentPass('');
        setNewPass('');
        setConfirmPass('');
      } else {
        setError(res?.error || 'Failed to change password.');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setChangingPass(false);
    }
  }

  function getRoleBadge(role) {
    switch ((role || '').toUpperCase()) {
      case 'GM':
        return { label: 'GM', title: 'General Manager', bg: '#dbeafe', color: '#1e40af', border: '#bfdbfe' };
      case 'AGM':
        return { label: 'AGM', title: 'Asst. General Manager', bg: '#f3e8ff', color: '#6b21a8', border: '#e9d5ff' };
      case 'AA':
        return { label: 'AA', title: 'Administrative Assistant / Accounts', bg: '#fef3c7', color: '#92400e', border: '#fde68a' };
      default:
        return { label: 'STAFF', title: 'Staff Recipient', bg: '#f1f5f9', color: '#475569', border: '#cbd5e1' };
    }
  }

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="mail-settings-title"
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 9999,
        background: 'rgba(15, 23, 42, 0.65)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          background: 'var(--card, #ffffff)',
          color: 'var(--text, #1e293b)',
          borderRadius: '14px',
          width: '100%',
          maxWidth: '620px',
          border: '1px solid var(--border, #cbd5e1)',
          boxShadow: '0 25px 30px -5px rgba(0, 0, 0, 0.25), 0 10px 15px -5px rgba(0, 0, 0, 0.1)',
          overflow: 'hidden'
        }}
      >
        {/* Modal Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1.25rem 1.5rem',
            borderBottom: '1px solid var(--border, #e2e8f0)',
            background: 'var(--soft, #f8fafc)'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.65rem' }}>
            <div style={{ background: '#e0f2fe', color: '#0284c7', padding: '6px', borderRadius: '8px' }}>
              <Mail size={20} />
            </div>
            <div>
              <h3 id="mail-settings-title" style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                Mail & Dispatch Settings
              </h3>
              <p className="muted" style={{ margin: 0, fontSize: '0.78rem' }}>
                Sender SMTP credentials, official designated recipients & access control
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            aria-label="Close dialog"
            style={{
              background: 'transparent',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--muted, #64748b)',
              padding: '6px',
              borderRadius: '6px'
            }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '1.5rem' }}>
          {/* Notifications */}
          {error && (
            <div className="error-banner" role="alert" style={{ marginBottom: '1rem', padding: '10px 14px', fontSize: '0.85rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <AlertTriangle size={15} />
                <span>{error}</span>
              </div>
            </div>
          )}

          {successMsg && (
            <div className="notice" style={{ marginBottom: '1rem', background: '#ecfdf5', color: '#065f46', border: '1px solid #a7f3d0', padding: '10px 14px', fontSize: '0.85rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <CheckCircle2 size={16} />
              <span>{successMsg}</span>
            </div>
          )}

          {/* 1. If not logged in as Admin, show Admin Gate */}
          {!adminToken ? (
            <div style={{ textAlign: 'center', padding: '1rem 0' }}>
              <div style={{ background: '#fef3c7', color: '#b45309', width: '56px', height: '56px', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 1rem auto' }}>
                <Shield size={28} />
              </div>
              <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '1.05rem', fontWeight: 600 }}>
                Administrator Authentication Required
              </h4>
              <p className="muted" style={{ fontSize: '0.85rem', maxWidth: '420px', margin: '0 auto 1.5rem auto' }}>
                Modifying sender credentials (app password) and official recipient addresses requires verified administrator login.
              </p>

              {loginError && (
                <div className="error-banner" style={{ maxWidth: '380px', margin: '0 auto 1rem auto', padding: '8px 12px', fontSize: '0.82rem' }}>
                  {loginError}
                </div>
              )}

              <form onSubmit={handleAdminLogin} style={{ maxWidth: '360px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '4px' }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>Admin Username</label>
                  <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface, #ffffff)', border: '1px solid var(--border, #cbd5e1)', borderRadius: '6px', padding: '0 10px' }}>
                    <User size={15} style={{ color: 'var(--muted, #94a3b8)' }} />
                    <input
                      type="text"
                      data-testid="admin-username-input"
                      value={loginUsername}
                      onChange={e => setLoginUsername(e.target.value)}
                      required
                      placeholder="e.g. admin"
                      style={{ border: 'none', background: 'transparent', padding: '8px 8px', fontSize: '0.88rem', flex: 1, outline: 'none' }}
                    />
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', textAlign: 'left', gap: '4px' }}>
                  <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>Admin Password</label>
                  <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface, #ffffff)', border: '1px solid var(--border, #cbd5e1)', borderRadius: '6px', padding: '0 10px' }}>
                    <Key size={15} style={{ color: 'var(--muted, #94a3b8)' }} />
                    <input
                      type="password"
                      data-testid="admin-password-input"
                      value={loginPassword}
                      onChange={e => setLoginPassword(e.target.value)}
                      required
                      placeholder="••••••••"
                      style={{ border: 'none', background: 'transparent', padding: '8px 8px', fontSize: '0.88rem', flex: 1, outline: 'none' }}
                    />
                  </div>
                </div>

                <button
                  type="submit"
                  className="primary"
                  data-testid="admin-login-btn"
                  disabled={loggingIn || !loginUsername.trim() || !loginPassword}
                  style={{ marginTop: '0.5rem', padding: '9px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                >
                  <Lock size={15} /> {loggingIn ? 'Authenticating…' : 'Unlock Mail Settings'}
                </button>

                <small style={{ fontSize: '0.75rem', color: 'var(--muted, #94a3b8)', marginTop: '4px' }}>
                  Default initial admin credentials: <code>admin</code> / <code>admin123</code>
                </small>
              </form>
            </div>
          ) : (
            /* 2. Admin is Authenticated: Show Full Settings */
            <div>
              {/* Admin status ribbon */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#ecfdf5', border: '1px solid #a7f3d0', borderRadius: '8px', padding: '6px 12px', marginBottom: '1.25rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.82rem', color: '#065f46', fontWeight: 600 }}>
                  <Shield size={14} /> Logged in as: <strong>{adminUser}</strong>
                </div>
                <button
                  onClick={handleLogout}
                  data-testid="admin-logout-btn"
                  style={{ background: 'transparent', border: 'none', color: '#047857', cursor: 'pointer', fontSize: '0.78rem', textDecoration: 'underline' }}
                >
                  Logout Admin
                </button>
              </div>

              {/* Navigation Tabs */}
              <div style={{ display: 'flex', borderBottom: '1px solid var(--border, #e2e8f0)', marginBottom: '1.25rem', gap: '0.5rem' }}>
                <button
                  onClick={() => { setActiveTab('sender'); setError(''); setSuccessMsg(''); setTestResult(null); }}
                  data-testid="tab-sender-settings"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    borderBottom: activeTab === 'sender' ? '2px solid #0284c7' : '2px solid transparent',
                    color: activeTab === 'sender' ? '#0284c7' : 'var(--muted, #64748b)',
                    fontWeight: activeTab === 'sender' ? 600 : 500,
                    padding: '8px 12px',
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Send size={15} /> Sender Settings
                </button>
                <button
                  onClick={() => { setActiveTab('recipients'); setError(''); setSuccessMsg(''); }}
                  data-testid="tab-recipient-settings"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    borderBottom: activeTab === 'recipients' ? '2px solid #0284c7' : '2px solid transparent',
                    color: activeTab === 'recipients' ? '#0284c7' : 'var(--muted, #64748b)',
                    fontWeight: activeTab === 'recipients' ? 600 : 500,
                    padding: '8px 12px',
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Mail size={15} /> Recipients (GM, AGM, AA)
                </button>
                <button
                  onClick={() => { setActiveTab('security'); setError(''); setSuccessMsg(''); }}
                  data-testid="tab-security-settings"
                  style={{
                    background: 'transparent',
                    border: 'none',
                    borderBottom: activeTab === 'security' ? '2px solid #0284c7' : '2px solid transparent',
                    color: activeTab === 'security' ? '#0284c7' : 'var(--muted, #64748b)',
                    fontWeight: activeTab === 'security' ? 600 : 500,
                    padding: '8px 12px',
                    fontSize: '0.88rem',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px'
                  }}
                >
                  <Lock size={15} /> Admin Password
                </button>
              </div>

              {/* TAB 1: SENDER SETTINGS */}
              {activeTab === 'sender' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <p className="muted" style={{ fontSize: '0.83rem', margin: 0 }}>
                    Configure the sender mailbox used to dispatch automated Aavin PDF and Excel production reports.
                  </p>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>Sender Email (Gmail)</label>
                      <input
                        type="email"
                        data-testid="sender-email-input"
                        placeholder="e.g. sender@gmail.com"
                        value={smtpUser}
                        onChange={e => {
                          setSmtpUser(e.target.value);
                          if (!smtpFromEmail || smtpFromEmail === smtpUser) {
                            setSmtpFromEmail(e.target.value);
                          }
                        }}
                        style={{ padding: '7px 10px', fontSize: '0.86rem', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)' }}
                      />
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>
                        Google App Password (16-char)
                      </label>
                      <div style={{ display: 'flex', alignItems: 'center', background: 'var(--surface, #ffffff)', border: '1px solid var(--border, #cbd5e1)', borderRadius: '6px', padding: '0 8px' }}>
                        <input
                          type={showPassword ? 'text' : 'password'}
                          data-testid="sender-app-password-input"
                          placeholder="••••••••••••••••"
                          value={smtpPassword}
                          onChange={e => setSmtpPassword(e.target.value)}
                          style={{ border: 'none', background: 'transparent', padding: '7px 0', fontSize: '0.86rem', flex: 1, outline: 'none' }}
                        />
                        <button
                          type="button"
                          onClick={() => setShowPassword(!showPassword)}
                          aria-label="Toggle password visibility"
                          style={{ background: 'transparent', border: 'none', cursor: 'pointer', color: 'var(--muted, #64748b)', padding: '2px' }}
                        >
                          {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '0.75rem' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>Sender Display Name</label>
                      <input
                        type="text"
                        data-testid="sender-name-input"
                        placeholder="Aavin OCR Reports"
                        value={smtpFromName}
                        onChange={e => setSmtpFromName(e.target.value)}
                        style={{ padding: '7px 10px', fontSize: '0.86rem', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)' }}
                      />
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>SMTP Host & Port</label>
                      <div style={{ display: 'flex', gap: '4px' }}>
                        <input
                          type="text"
                          value={smtpHost}
                          onChange={e => setSmtpHost(e.target.value)}
                          style={{ flex: 1, padding: '7px 8px', fontSize: '0.86rem', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)' }}
                        />
                        <input
                          type="number"
                          value={smtpPort}
                          onChange={e => setSmtpPort(e.target.value)}
                          style={{ width: '65px', padding: '7px 6px', fontSize: '0.86rem', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)' }}
                        />
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', alignItems: 'center', fontSize: '0.82rem', padding: '4px 0' }}>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={smtpUseTls}
                        onChange={e => setSmtpUseTls(e.target.checked)}
                      />
                      Use TLS (Recommended for port 587)
                    </label>
                    <label style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={smtpUseSsl}
                        onChange={e => setSmtpUseSsl(e.target.checked)}
                      />
                      Use SSL (Port 465)
                    </label>
                  </div>

                  {/* Test Connection Output */}
                  {testResult && (
                    <div
                      style={{
                        padding: '8px 12px',
                        borderRadius: '6px',
                        fontSize: '0.82rem',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: testResult.success ? '#ecfdf5' : '#fef2f2',
                        color: testResult.success ? '#065f46' : '#991b1b',
                        border: `1px solid ${testResult.success ? '#a7f3d0' : '#fecaca'}`
                      }}
                    >
                      {testResult.success ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
                      <span>{testResult.message || testResult.error}</span>
                    </div>
                  )}

                  {/* Sender Action Buttons */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.75rem', borderTop: '1px solid var(--border, #e2e8f0)' }}>
                    <button
                      type="button"
                      data-testid="test-connection-btn"
                      onClick={handleTestSender}
                      disabled={testingConnection || !smtpUser}
                      style={{
                        background: 'transparent',
                        border: '1px solid var(--border, #cbd5e1)',
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontSize: '0.82rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        color: 'var(--text, #334155)'
                      }}
                    >
                      <Activity size={14} /> {testingConnection ? 'Testing SMTP…' : 'Test Connection'}
                    </button>

                    <button
                      type="button"
                      className="primary"
                      data-testid="save-sender-btn"
                      onClick={handleSaveSender}
                      disabled={saving || !smtpUser}
                      style={{ padding: '7px 16px', fontSize: '0.85rem' }}
                    >
                      {saving ? 'Saving…' : 'Save Sender Settings'}
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 2: RECIPIENT SETTINGS (GM, AGM, AA) */}
              {activeTab === 'recipients' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <p className="muted" style={{ fontSize: '0.83rem', margin: 0 }}>
                    Designate recipients for General Manager (GM), Asst. General Manager (AGM), and Accounts/Audit (AA).
                  </p>

                  {/* Add Recipient Form */}
                  <div style={{ background: 'var(--soft, #f8fafc)', border: '1px solid var(--border, #e2e8f0)', borderRadius: '8px', padding: '10px 12px' }}>
                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '8px' }}>
                      <select
                        value={newRole}
                        onChange={e => setNewRole(e.target.value)}
                        data-testid="new-recipient-role-select"
                        style={{
                          width: '90px',
                          padding: '7px 6px',
                          fontSize: '0.85rem',
                          fontWeight: 600,
                          borderRadius: '6px',
                          border: '1px solid var(--border, #cbd5e1)',
                          background: 'var(--surface, #ffffff)'
                        }}
                      >
                        <option value="GM">GM</option>
                        <option value="AGM">AGM</option>
                        <option value="AA">AA</option>
                        <option value="STAFF">Staff</option>
                      </select>

                      <input
                        type="email"
                        aria-label="New recipient email address"
                        data-testid="settings-new-email-input"
                        placeholder="e.g. gm.aavin@gov.in"
                        value={newEmail}
                        onChange={(e) => setNewEmail(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAddRecipient();
                          }
                        }}
                        style={{
                          flex: 1,
                          padding: '7px 10px',
                          fontSize: '0.88rem',
                          borderRadius: '6px',
                          border: '1px solid var(--border, #cbd5e1)',
                          background: 'var(--surface, #ffffff)',
                          color: 'var(--text, #1e293b)'
                        }}
                      />
                      <button
                        className="primary"
                        data-testid="settings-add-email-btn"
                        onClick={handleAddRecipient}
                        disabled={!newEmail.trim()}
                        style={{ padding: '7px 12px', fontSize: '0.82rem' }}
                      >
                        <Plus size={15} /> Add
                      </button>
                    </div>

                    <div style={{ display: 'flex', gap: '1.25rem', alignItems: 'center', fontSize: '0.8rem', color: 'var(--text, #334155)' }}>
                      <span style={{ fontWeight: 600, color: 'var(--muted, #64748b)' }}>Attachments:</span>
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          data-testid="new-recipient-pdf-check"
                          checked={newSendPdf}
                          onChange={(e) => setNewSendPdf(e.target.checked)}
                        />
                        <FileText size={13} style={{ color: '#0284c7' }} /> PDF + Message
                      </label>
                      <label style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          data-testid="new-recipient-excel-check"
                          checked={newSendExcel}
                          onChange={(e) => setNewSendExcel(e.target.checked)}
                        />
                        <FileSpreadsheet size={13} style={{ color: '#16a34a' }} /> Excel (.xlsx)
                      </label>
                    </div>
                  </div>

                  {/* Recipient List */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '200px', overflowY: 'auto' }}>
                    {recipients.map((r, idx) => {
                      const badge = getRoleBadge(r.role);
                      return (
                        <div
                          key={r.email}
                          data-testid={`recipient-item-${idx}`}
                          style={{
                            padding: '8px 12px',
                            background: 'var(--soft, #f8fafc)',
                            borderRadius: '8px',
                            border: '1px solid var(--border, #e2e8f0)',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            gap: '0.5rem'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: 0 }}>
                            <span
                              title={badge.title}
                              style={{
                                fontSize: '0.72rem',
                                fontWeight: 700,
                                padding: '2px 6px',
                                borderRadius: '4px',
                                background: badge.bg,
                                color: badge.color,
                                border: `1px solid ${badge.border}`
                              }}
                            >
                              {badge.label}
                            </span>
                            <strong style={{ fontSize: '0.86rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                              {r.email}
                            </strong>
                          </div>

                          <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontSize: '0.78rem' }}>
                              <input
                                type="checkbox"
                                data-testid={`toggle-pdf-${idx}`}
                                checked={Boolean(r.send_pdf)}
                                onChange={() => handleTogglePdf(idx)}
                              />
                              PDF
                            </label>
                            <label style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', cursor: 'pointer', fontSize: '0.78rem' }}>
                              <input
                                type="checkbox"
                                data-testid={`toggle-excel-${idx}`}
                                checked={Boolean(r.send_excel)}
                                onChange={() => handleToggleExcel(idx)}
                              />
                              Excel
                            </label>
                            <button
                              onClick={() => handleRemoveRecipient(idx)}
                              data-testid={`remove-recipient-${idx}`}
                              aria-label={`Remove ${r.email}`}
                              style={{ background: 'transparent', border: 'none', color: '#ef4444', cursor: 'pointer', padding: '4px' }}
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Recipient Footer */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', paddingTop: '0.75rem', borderTop: '1px solid var(--border, #e2e8f0)' }}>
                    <button
                      onClick={handleResetToDefaults}
                      data-testid="reset-defaults-btn"
                      style={{
                        background: 'transparent',
                        border: '1px solid var(--border, #cbd5e1)',
                        padding: '6px 12px',
                        borderRadius: '6px',
                        fontSize: '0.8rem',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        color: 'var(--muted, #64748b)'
                      }}
                    >
                      <RotateCcw size={13} /> Reset GM/AGM/AA Defaults
                    </button>
                    <button
                      className="primary"
                      data-testid="save-recipients-btn"
                      onClick={handleSaveRecipients}
                      disabled={saving || recipients.length === 0}
                      style={{ padding: '7px 16px', fontSize: '0.85rem' }}
                    >
                      {saving ? 'Saving…' : 'Save Recipient Settings'}
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 3: ADMIN SECURITY (Change Password) */}
              {activeTab === 'security' && (
                <form onSubmit={handleChangePassword} style={{ maxWidth: '380px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                  <p className="muted" style={{ fontSize: '0.83rem', margin: 0 }}>
                    Change administrator password used to unlock mail and dispatch configuration.
                  </p>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>Current Password</label>
                    <input
                      type="password"
                      data-testid="current-admin-pass-input"
                      value={currentPass}
                      onChange={e => setCurrentPass(e.target.value)}
                      required
                      placeholder="••••••••"
                      style={{ padding: '7px 10px', fontSize: '0.86rem', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)' }}
                    />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>New Password</label>
                    <input
                      type="password"
                      data-testid="new-admin-pass-input"
                      value={newPass}
                      onChange={e => setNewPass(e.target.value)}
                      required
                      placeholder="Min 4 characters"
                      style={{ padding: '7px 10px', fontSize: '0.86rem', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)' }}
                    />
                  </div>

                  <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                    <label style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--muted, #64748b)' }}>Confirm New Password</label>
                    <input
                      type="password"
                      data-testid="confirm-admin-pass-input"
                      value={confirmPass}
                      onChange={e => setConfirmPass(e.target.value)}
                      required
                      placeholder="Repeat new password"
                      style={{ padding: '7px 10px', fontSize: '0.86rem', borderRadius: '6px', border: '1px solid var(--border, #cbd5e1)', background: 'var(--surface, #ffffff)' }}
                    />
                  </div>

                  <button
                    type="submit"
                    className="primary"
                    data-testid="update-admin-pass-btn"
                    disabled={changingPass || !currentPass || !newPass}
                    style={{ marginTop: '0.5rem', padding: '8px 16px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}
                  >
                    <Key size={14} /> {changingPass ? 'Updating Password…' : 'Update Admin Password'}
                  </button>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

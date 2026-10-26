import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import MailSettingsModal from './MailSettingsModal';

describe('MailSettingsModal', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    sessionStorage.clear();
  });

  it('displays the Admin Authentication Gate when not logged in', async () => {
    render(<MailSettingsModal isOpen={true} onClose={() => {}} onSaved={() => {}} />);

    expect(screen.getByText('Administrator Authentication Required')).toBeInTheDocument();
    expect(screen.getByTestId('admin-username-input')).toBeInTheDocument();
    expect(screen.getByTestId('admin-password-input')).toBeInTheDocument();
    expect(screen.getByTestId('admin-login-btn')).toBeInTheDocument();
  });

  it('allows administrator to log in and unlock Mail Settings', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url, opts) => {
      if (url.includes('/reports/settings/admin/login')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            success: true,
            token: 'mock_admin_token_123',
            username: 'admin'
          })
        });
      }
      if (url.includes('/reports/settings/mail')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            sender: {
              smtp_host: 'smtp.gmail.com',
              smtp_port: 587,
              smtp_user: 'official@aavin.test',
              smtp_from_name: 'Aavin OCR Reports',
              smtp_use_tls: true,
              smtp_use_ssl: false
            },
            recipients: [
              { role: 'GM', name: 'General Manager', email: 'gm@aavin.test', send_pdf: true, send_excel: false },
              { role: 'AGM', name: 'Asst. General Manager', email: 'agm@aavin.test', send_pdf: true, send_excel: true },
              { role: 'AA', name: 'Administrative Assistant', email: 'aa@aavin.test', send_pdf: true, send_excel: false }
            ]
          })
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<MailSettingsModal isOpen={true} onClose={() => {}} onSaved={() => {}} />);

    // Enter credentials
    fireEvent.change(screen.getByTestId('admin-username-input'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByTestId('admin-password-input'), { target: { value: 'admin123' } });
    fireEvent.click(screen.getByTestId('admin-login-btn'));

    await waitFor(() => {
      expect(screen.getByText('Mail & Dispatch Settings')).toBeInTheDocument();
      expect(screen.getByText('Sender Settings')).toBeInTheDocument();
      expect(screen.getByText('Recipients (GM, AGM, AA)')).toBeInTheDocument();
    });

    expect(sessionStorage.getItem('aavin_admin_token')).toBe('mock_admin_token_123');
  });

  it('allows managing sender settings and testing connection', async () => {
    sessionStorage.setItem('aavin_admin_token', 'valid_token');
    sessionStorage.setItem('aavin_admin_user', 'admin');

    let senderPayload = null;

    vi.stubGlobal('fetch', vi.fn().mockImplementation((url, opts) => {
      if (url.includes('/reports/settings/admin/verify')) {
        return Promise.resolve({ ok: true, json: async () => ({ valid: true, username: 'admin' }) });
      }
      if (url.includes('/reports/settings/mail')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            sender: {
              smtp_host: 'smtp.gmail.com',
              smtp_port: 587,
              smtp_user: 'current@aavin.test',
              smtp_from_name: 'Aavin OCR Reports',
              smtp_use_tls: true,
              smtp_use_ssl: false
            },
            recipients: []
          })
        });
      }
      if (url.includes('/reports/settings/sender/test')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            success: true,
            message: 'Connected and authenticated successfully with smtp.gmail.com:587'
          })
        });
      }
      if (opts?.method === 'PUT' && url.includes('/reports/settings/sender')) {
        senderPayload = JSON.parse(opts.body);
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true })
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<MailSettingsModal isOpen={true} onClose={() => {}} onSaved={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId('sender-email-input')).toBeInTheDocument();
    });

    // Update email and app password
    fireEvent.change(screen.getByTestId('sender-email-input'), { target: { value: 'new_sender@gmail.com' } });
    fireEvent.change(screen.getByTestId('sender-app-password-input'), { target: { value: 'abcd1234efgh5678' } });

    // Click Test Connection
    fireEvent.click(screen.getByTestId('test-connection-btn'));
    await waitFor(() => {
      expect(screen.getByText(/Connected and authenticated successfully/i)).toBeInTheDocument();
    });

    // Click Save Sender Settings
    fireEvent.click(screen.getByTestId('save-sender-btn'));
    await waitFor(() => {
      expect(senderPayload).toEqual(expect.objectContaining({
        smtp_user: 'new_sender@gmail.com',
        smtp_password: 'abcd1234efgh5678'
      }));
      expect(screen.getByText('Sender settings updated successfully!')).toBeInTheDocument();
    });
  });

  it('allows managing GM, AGM, and AA role recipients', async () => {
    sessionStorage.setItem('aavin_admin_token', 'valid_token');
    sessionStorage.setItem('aavin_admin_user', 'admin');

    let recipientPayload = null;

    vi.stubGlobal('fetch', vi.fn().mockImplementation((url, opts) => {
      if (url.includes('/reports/settings/admin/verify')) {
        return Promise.resolve({ ok: true, json: async () => ({ valid: true, username: 'admin' }) });
      }
      if (url.includes('/reports/settings/mail')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({
            sender: {},
            recipients: [
              { role: 'GM', name: 'General Manager', email: 'gm@aavin.test', send_pdf: true, send_excel: false },
              { role: 'AGM', name: 'Asst. General Manager', email: 'agm@aavin.test', send_pdf: true, send_excel: true },
              { role: 'AA', name: 'Administrative Assistant', email: 'aa@aavin.test', send_pdf: true, send_excel: false }
            ]
          })
        });
      }
      if (opts?.method === 'PUT' && url.includes('/reports/settings/recipients')) {
        recipientPayload = JSON.parse(opts.body);
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, recipients: recipientPayload.recipients })
        });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<MailSettingsModal isOpen={true} onClose={() => {}} onSaved={() => {}} />);

    // Switch to Recipients Tab
    await waitFor(() => {
      expect(screen.getByTestId('tab-recipient-settings')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId('tab-recipient-settings'));

    await waitFor(() => {
      expect(screen.getByText('gm@aavin.test')).toBeInTheDocument();
      expect(screen.getByText('agm@aavin.test')).toBeInTheDocument();
      expect(screen.getByText('aa@aavin.test')).toBeInTheDocument();
    });

    // Toggle options for GM
    fireEvent.click(screen.getByTestId('toggle-excel-0'));

    // Save recipients
    fireEvent.click(screen.getByTestId('save-recipients-btn'));

    await waitFor(() => {
      expect(recipientPayload).not.toBeNull();
      expect(recipientPayload.recipients[0].send_excel).toBe(true);
      expect(screen.getByText('Recipient list & designated roles updated successfully!')).toBeInTheDocument();
    });
  });
});

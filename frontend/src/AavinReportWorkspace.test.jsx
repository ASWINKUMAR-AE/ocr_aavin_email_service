import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import AavinReportWorkspace from './AavinReportWorkspace';

describe('AavinReportWorkspace', () => {
  const mockReport = {
    id: 'rep-123',
    document_id: 'doc-1',
    union_code: 'GA1301',
    organization_name: "THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD.",
    address: 'SIVAGANGAI MAIN ROAD, MADURAI - 625 020',
    report_date: '2026-10-21',
    shift: 'EVENING',
    validation_status: 'VALIDATED',
    validation_warnings: [],
    email_status: 'PENDING',
    items: [
      { id: '1', item_no: 1, product_name: 'COW MILK 500 ML', quantity_litres: '25776.500', quantity_packets: 51553, quantity_trays: '2148.001', row_type: 'PRODUCT' },
      { id: '2', item_no: 901, product_name: 'MILK TOTAL', quantity_litres: '48941.100', quantity_packets: 106626, quantity_trays: '4156.001', row_type: 'SUBTOTAL' },
      { id: '3', item_no: 999, product_name: 'GRAND TOTAL', quantity_litres: '49135.095', quantity_packets: 107434, quantity_trays: '4173.001', row_type: 'GRAND_TOTAL' },
    ],
    audit_logs: []
  };

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders report details, product rows and validation badge', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
      if (url.includes('/reports/rep-123')) {
        return Promise.resolve({ ok: true, json: async () => mockReport });
      }
      if (url.endsWith('/reports')) {
        return Promise.resolve({ ok: true, json: async () => [mockReport] });
      }
      return Promise.resolve({ ok: true, json: async () => mockReport });
    }));

    render(<AavinReportWorkspace doc={{ id: 'doc-1' }} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText("THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD.")).toBeInTheDocument();
    });

    expect(screen.getByText(/Union Code GA1301/)).toBeInTheDocument();
    expect(screen.getByText('COW MILK 500 ML')).toBeInTheDocument();
    expect(screen.getByText('MILK TOTAL')).toBeInTheDocument();
    expect(screen.getByText('GRAND TOTAL')).toBeInTheDocument();
    expect(screen.getByText('Validated')).toBeInTheDocument();
  });

  it('displays theme-matched green success alert with exact text when email is sent successfully', async () => {
    let resolveSend;
    const sendPromise = new Promise((resolve) => {
      resolveSend = resolve;
    });

    vi.stubGlobal('fetch', vi.fn().mockImplementation((url, opts) => {
      if (url.includes('/send-email')) {
        return sendPromise.then(() => ({
          ok: true,
          json: async () => ({ success: true, status: 'SENT', recipients: ['test@example.com'] })
        }));
      }
      if (url.includes('/reports/rep-123')) {
        return Promise.resolve({ ok: true, json: async () => mockReport });
      }
      if (url.endsWith('/reports')) {
        return Promise.resolve({ ok: true, json: async () => [mockReport] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<AavinReportWorkspace doc={{ id: 'doc-1' }} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Send Email Report')).toBeInTheDocument();
    });

    const sendBtn = screen.getByText('Send Email Report');
    fireEvent.click(sendBtn);

    // While sending: loading indicator shown and no alert prematurely displayed
    expect(screen.getByText('Sending…')).toBeInTheDocument();
    expect(screen.queryByTestId('email-status-alert')).not.toBeInTheDocument();

    // Resolve successful email send
    resolveSend();

    await waitFor(() => {
      expect(screen.getByTestId('email-status-alert')).toBeInTheDocument();
    });

    const alert = screen.getByTestId('email-status-alert');
    expect(alert).toHaveClass('email-alert-success');
    expect(alert).toHaveTextContent('The mail is sent successfully.');
  });

  it('displays theme-matched red failure alert with exact text when email sending fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
      if (url.includes('/send-email')) {
        return Promise.resolve({
          ok: false,
          status: 400,
          json: async () => ({ detail: 'Failed to send report email' })
        });
      }
      if (url.includes('/reports/rep-123')) {
        return Promise.resolve({ ok: true, json: async () => mockReport });
      }
      if (url.endsWith('/reports')) {
        return Promise.resolve({ ok: true, json: async () => [mockReport] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<AavinReportWorkspace doc={{ id: 'doc-1' }} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Send Email Report')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Send Email Report'));

    await waitFor(() => {
      expect(screen.getByTestId('email-status-alert')).toBeInTheDocument();
    });

    const alert = screen.getByTestId('email-status-alert');
    expect(alert).toHaveClass('email-alert-error');
    expect(alert).toHaveTextContent('The mail could not be sent. Please try again.');
    expect(screen.queryByText('The mail is sent successfully.')).not.toBeInTheDocument();
  });

  it('clears previous status alert when a new email-sending attempt starts', async () => {
    let callCount = 0;
    let resolveSecondSend;
    const secondSendPromise = new Promise((resolve) => {
      resolveSecondSend = resolve;
    });

    vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
      if (url.includes('/send-email')) {
        callCount++;
        if (callCount === 1) {
          // First call fails
          return Promise.resolve({
            ok: false,
            status: 400,
            json: async () => ({ detail: 'SMTP error' })
          });
        }
        // Second call is in flight
        return secondSendPromise.then(() => ({
          ok: true,
          json: async () => ({ success: true, status: 'SENT' })
        }));
      }
      if (url.includes('/reports/rep-123')) {
        return Promise.resolve({ ok: true, json: async () => mockReport });
      }
      if (url.endsWith('/reports')) {
        return Promise.resolve({ ok: true, json: async () => [mockReport] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<AavinReportWorkspace doc={{ id: 'doc-1' }} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Send Email Report')).toBeInTheDocument();
    });

    // 1st attempt: triggers failure
    fireEvent.click(screen.getByText('Send Email Report'));
    await waitFor(() => {
      expect(screen.getByText('The mail could not be sent. Please try again.')).toBeInTheDocument();
    });

    // 2nd attempt: click send again while in flight
    fireEvent.click(screen.getByText('Send Email Report'));

    // The previous failure alert must be immediately cleared
    expect(screen.queryByTestId('email-status-alert')).not.toBeInTheDocument();
    expect(screen.getByText('Sending…')).toBeInTheDocument();

    // Now resolve second attempt
    resolveSecondSend();
    await waitFor(() => {
      expect(screen.getByText('The mail is sent successfully.')).toBeInTheDocument();
    });
    const alert = screen.getByTestId('email-status-alert');
    expect(alert).toHaveClass('email-alert-success');
    expect(screen.queryByText('The mail could not be sent. Please try again.')).not.toBeInTheDocument();
  });

  it('displays red failure alert when email dispatch is skipped', async () => {
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
      if (url.includes('/send-email')) {
        return Promise.resolve({
          ok: true,
          json: async () => ({ success: true, skipped: true, message: 'Already emailed' })
        });
      }
      if (url.includes('/reports/rep-123')) {
        return Promise.resolve({ ok: true, json: async () => mockReport });
      }
      if (url.endsWith('/reports')) {
        return Promise.resolve({ ok: true, json: async () => [mockReport] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<AavinReportWorkspace doc={{ id: 'doc-1' }} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText('Send Email Report')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('Send Email Report'));

    await waitFor(() => {
      expect(screen.getByTestId('email-status-alert')).toBeInTheDocument();
    });

    const alert = screen.getByTestId('email-status-alert');
    expect(alert).toHaveClass('email-alert-error');
    expect(alert).toHaveTextContent('The mail could not be sent. Please try again.');
    expect(screen.queryByText('The mail is sent successfully.')).not.toBeInTheDocument();
  });

  it('calls onBack callback when the back button is clicked', async () => {
    const handleBack = vi.fn();
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url) => {
      if (url.includes('/reports/rep-123')) {
        return Promise.resolve({ ok: true, json: async () => mockReport });
      }
      if (url.endsWith('/reports')) {
        return Promise.resolve({ ok: true, json: async () => [mockReport] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<AavinReportWorkspace doc={{ id: 'doc-1' }} onBack={handleBack} />);

    await waitFor(() => {
      expect(screen.getAllByText('Back to OCR review').length).toBeGreaterThan(0);
    });

    const backButtons = screen.getAllByText('Back to OCR review');
    fireEvent.click(backButtons[0]);
    expect(handleBack).toHaveBeenCalledTimes(1);
  });

  it('allows entering a custom email in the bar and sending to it', async () => {
    let capturedBody = null;
    vi.stubGlobal('fetch', vi.fn().mockImplementation((url, opts) => {
      if (url.includes('/send-email')) {
        capturedBody = JSON.parse(opts.body);
        return Promise.resolve({
          ok: true,
          json: async () => ({
            success: true,
            status: 'SENT',
            recipients: capturedBody.recipients
          })
        });
      }
      if (url.includes('/reports/rep-123')) {
        return Promise.resolve({ ok: true, json: async () => mockReport });
      }
      if (url.endsWith('/reports')) {
        return Promise.resolve({ ok: true, json: async () => [mockReport] });
      }
      return Promise.resolve({ ok: true, json: async () => ({}) });
    }));

    render(<AavinReportWorkspace doc={{ id: 'doc-1' }} onBack={() => {}} />);

    await waitFor(() => {
      expect(screen.getByTestId('custom-email-input')).toBeInTheDocument();
    });

    const emailInput = screen.getByTestId('custom-email-input');
    const sendBtn = screen.getByTestId('custom-email-send-btn');
    const select = screen.getByTestId('session-email-select');

    // Verify default session emails are in the dropdown
    expect(select).toHaveTextContent('aswinkumarta2006@gmail.com');
    expect(select).toHaveTextContent('heiwinganesh15@gmail.com');

    // Type new custom email
    fireEvent.change(emailInput, { target: { value: 'manager@aavin.test' } });
    fireEvent.click(sendBtn);

    await waitFor(() => {
      expect(capturedBody).toEqual({
        recipients: ['manager@aavin.test'],
        force: true
      });
      expect(screen.getByTestId('email-status-alert')).toHaveClass('email-alert-success');
    });

    // Verify it is now added to session dropdown
    expect(select).toHaveTextContent('manager@aavin.test');
  });
});



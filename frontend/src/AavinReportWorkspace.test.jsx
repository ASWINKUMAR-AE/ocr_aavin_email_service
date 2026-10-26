import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import AavinReportWorkspace from './AavinReportWorkspace';

describe('AavinReportWorkspace', () => {
  it('renders report details, product rows and validation badge', async () => {
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

    vi.unstubAllGlobals();
  });
});

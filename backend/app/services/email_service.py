import logging
import smtplib
from datetime import datetime, timezone
from decimal import Decimal
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app import config, reports_store
from app.services.aavin_excel import generate_aavin_excel
from app.services.aavin_pdf import generate_aavin_pdf

logger = logging.getLogger(__name__)


def format_ist_timestamp(iso_str: Optional[str]) -> str:
    """Convert ISO UTC string to formatted Asia/Kolkata timestamp."""
    if not iso_str:
        return "N/A"
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        tz = ZoneInfo(config.REPORT_TIMEZONE)
        ist_dt = dt.astimezone(tz)
        return ist_dt.strftime('%d-%b-%Y %I:%M:%S %p %Z')
    except Exception:
        return iso_str


def format_report_date_display(date_str: str) -> str:
    """Convert YYYY-MM-DD to '21 October 2026'."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%d %B %Y')
    except Exception:
        return date_str


def format_report_date_subject(date_str: str) -> str:
    """Convert YYYY-MM-DD to '21-10-2026'."""
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        return dt.strftime('%d-%m-%Y')
    except Exception:
        return date_str


class AavinReportEmailService:
    """
    Renders official HTML & Plain-text Aavin production abstract email reports,
    and manages safe SMTP delivery with duplicate prevention and audit tracking.
    """

    @classmethod
    def generate_email_content(cls, report: Dict[str, Any]) -> Tuple[str, str, str]:
        """
        Builds Subject, Plain-text body, and HTML body from a live database report.
        """
        # Subject format: Aavin Production Abstract | 21-10-2026 | Evening Shift
        subj_date = format_report_date_subject(report['report_date'])
        shift_title = report['shift'].capitalize() if report['shift'] else 'Unknown'
        subject = f"Aavin Production Abstract | {subj_date} | {shift_title} Shift"

        display_date = format_report_date_display(report['report_date'])
        processed_at_ist = format_ist_timestamp(report.get('report_processed_at') or report.get('created_at'))
        status_label = "Validated" if report['validation_status'] == 'VALIDATED' else "Needs Review"

        items = report.get('items', [])
        product_items = [i for i in items if i.get('row_type') == 'PRODUCT']
        milk_subtotal = next((i for i in items if i.get('product_name') == 'MILK TOTAL'), None)
        curd_subtotal = next((i for i in items if i.get('product_name') == 'CURD & BUTTERMILK TOTAL'), None)
        grand_total = next((i for i in items if i.get('product_name') == 'GRAND TOTAL'), None)

        milk_products = [i for i in product_items if i.get('category') == 'MILK']
        curd_products = [i for i in product_items if i.get('category') == 'CURD_BUTTERMILK']

        # 1. Plain Text Alternative
        text_lines = [
            report['organization_name'],
            report['address'],
            "PRODUCTION ABSTRACT REPORT",
            "=" * 70,
            f"Union Code         : {report['union_code']}",
            f"Report Date        : {display_date}",
            f"Shift              : {shift_title}",
            f"Report Processed At: {processed_at_ist}",
            f"Validation Status  : {status_label}",
        ]

        warnings = report.get('validation_warnings', [])
        if warnings:
            text_lines.append("\nAUDIT WARNINGS:")
            for w in warnings:
                text_lines.append(f" - {w}")

        text_lines.append("\n" + "-" * 70)
        text_lines.append(f"{'No.':<4} {'Type of Product':<26} {'Qty (Ltr)':>13} {'Qty (Pkt)':>11} {'Tray':>12}")
        text_lines.append("-" * 70)

        for p in milk_products:
            text_lines.append(f"{p['item_no']:<4} {p['product_name']:<26} {Decimal(p['quantity_litres']):>13.3f} {p['quantity_packets']:>11} {Decimal(p['quantity_trays']):>12.2f}")

        if milk_subtotal:
            text_lines.append("-" * 70)
            text_lines.append(f"{'':<4} {'MILK TOTAL':<26} {Decimal(milk_subtotal['quantity_litres']):>13.3f} {milk_subtotal['quantity_packets']:>11} {Decimal(milk_subtotal['quantity_trays']):>12.2f}")
            text_lines.append("-" * 70)

        for p in curd_products:
            text_lines.append(f"{p['item_no']:<4} {p['product_name']:<26} {Decimal(p['quantity_litres']):>13.3f} {p['quantity_packets']:>11} {Decimal(p['quantity_trays']):>12.2f}")

        if curd_subtotal:
            text_lines.append("-" * 70)
            text_lines.append(f"{'':<4} {'CURD & BUTTERMILK TOTAL':<26} {Decimal(curd_subtotal['quantity_litres']):>13.3f} {curd_subtotal['quantity_packets']:>11} {Decimal(curd_subtotal['quantity_trays']):>12.2f}")
            text_lines.append("-" * 70)

        if grand_total:
            text_lines.append("=" * 70)
            text_lines.append(f"{'':<4} {'GRAND TOTAL':<26} {Decimal(grand_total['quantity_litres']):>13.3f} {grand_total['quantity_packets']:>11} {Decimal(grand_total['quantity_trays']):>12.2f}")
            text_lines.append("=" * 70)

        text_lines.extend([
            "\n" + "-" * 70,
            f"Report ID: {report['id']}",
            "Generated automatically from live Aavin OCR extraction.",
            "Confidential & Official Co-operative Milk Producers' Union Report.",
        ])

        plain_text = "\n".join(text_lines)

        # 2. HTML Table Email
        # Build Table Rows
        def render_row(item, is_subtotal=False, is_grand_total=False):
            if is_grand_total:
                bg = "#e0f2fe"
                weight = "bold"
                color = "#0369a1"
                border_top = "2px solid #0284c7"
                border_bottom = "2px solid #0284c7"
            elif is_subtotal:
                bg = "#f1f5f9"
                weight = "bold"
                color = "#0f172a"
                border_top = "1px solid #94a3b8"
                border_bottom = "1px solid #94a3b8"
            else:
                bg = "#ffffff"
                weight = "normal"
                color = "#334155"
                border_top = "1px solid #e2e8f0"
                border_bottom = "1px solid #e2e8f0"

            item_no_str = str(item['item_no']) if not is_subtotal and not is_grand_total else ""
            ltr_str = f"{Decimal(item['quantity_litres']):,.3f}"
            pkt_str = f"{int(item['quantity_packets']):,}"
            tray_str = f"{Decimal(item['quantity_trays']):,.2f}"

            return f"""
            <tr style="background-color: {bg}; font-weight: {weight}; color: {color};">
              <td style="padding: 9px 12px; border-top: {border_top}; border-bottom: {border_bottom}; text-align: center; font-size: 13px;">{item_no_str}</td>
              <td style="padding: 9px 12px; border-top: {border_top}; border-bottom: {border_bottom}; text-align: left; font-size: 13px;">{item['product_name']}</td>
              <td style="padding: 9px 12px; border-top: {border_top}; border-bottom: {border_bottom}; text-align: right; font-family: Consolas, monospace; font-size: 13px;">{ltr_str}</td>
              <td style="padding: 9px 12px; border-top: {border_top}; border-bottom: {border_bottom}; text-align: right; font-family: Consolas, monospace; font-size: 13px;">{pkt_str}</td>
              <td style="padding: 9px 12px; border-top: {border_top}; border-bottom: {border_bottom}; text-align: right; font-family: Consolas, monospace; font-size: 13px;">{tray_str}</td>
            </tr>
            """

        rows_html = []
        for p in milk_products:
            rows_html.append(render_row(p))
        if milk_subtotal:
            rows_html.append(render_row(milk_subtotal, is_subtotal=True))

        for p in curd_products:
            rows_html.append(render_row(p))
        if curd_subtotal:
            rows_html.append(render_row(curd_subtotal, is_subtotal=True))

        if grand_total:
            rows_html.append(render_row(grand_total, is_grand_total=True))

        status_badge = (
            '<span style="background-color: #dcfce7; color: #15803d; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; border: 1px solid #86efac;">Validated</span>'
            if report['validation_status'] == 'VALIDATED' else
            '<span style="background-color: #fef3c7; color: #b45309; padding: 4px 10px; border-radius: 12px; font-weight: bold; font-size: 12px; border: 1px solid #fde68a;">Needs Review</span>'
        )

        warnings_box = ""
        if warnings:
            w_items = "".join(f"<li style='margin-bottom: 4px;'>{w}</li>" for w in warnings)
            warnings_box = f"""
            <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; margin: 16px 0; border-radius: 4px;">
              <strong style="color: #b45309; font-size: 13px;">Audit Warnings & Flagged Discrepancies:</strong>
              <ul style="margin: 6px 0 0 16px; padding: 0; color: #92400e; font-size: 12px; line-height: 1.4;">
                {w_items}
              </ul>
            </div>
            """

        html_body = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{subject}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; background-color: #f8fafc; margin: 0; padding: 24px 12px; line-height: 1.5;">
  <div style="max-width: 760px; margin: 0 auto; background: #ffffff; border-radius: 8px; border: 1px solid #cbd5e1; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); overflow: hidden;">
    
    <!-- Official Header Banner -->
    <div style="background: linear-gradient(135deg, #0b3c68 0%, #1e40af 100%); color: #ffffff; padding: 24px; text-align: left;">
      <div style="font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #bae6fd; margin-bottom: 4px; font-weight: 600;">TAMIL NADU CO-OPERATIVE MILK PRODUCERS' FEDERATION</div>
      <h1 style="margin: 0; font-size: 19px; line-height: 1.3; font-weight: 700; letter-spacing: 0.3px;">{report['organization_name']}</h1>
      <p style="margin: 4px 0 0 0; font-size: 13px; color: #e2e8f0;">{report['address']}</p>
      <div style="margin-top: 14px; padding-top: 12px; border-top: 1px solid rgba(255, 255, 255, 0.2); display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <span style="font-size: 15px; font-weight: 700; letter-spacing: 0.5px; color: #ffffff;">PRODUCTION ABSTRACT REPORT</span>
        <span style="font-size: 13px; color: #93c5fd;">Union Code: <strong style="color: #ffffff;">{report['union_code']}</strong></span>
      </div>
    </div>

    <!-- Metadata Details Card -->
    <div style="padding: 20px 24px 12px 24px;">
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 13px;">
        <tr>
          <td style="padding: 6px 0; color: #64748b; width: 25%;">Report Date:</td>
          <td style="padding: 6px 0; color: #0f172a; font-weight: 600; width: 25%;">{display_date}</td>
          <td style="padding: 6px 0; color: #64748b; width: 25%;">Shift:</td>
          <td style="padding: 6px 0; color: #0f172a; font-weight: 600; width: 25%;">{shift_title}</td>
        </tr>
        <tr>
          <td style="padding: 6px 0; color: #64748b;">Report Processed At:</td>
          <td style="padding: 6px 0; color: #0f172a; font-weight: 600;">{processed_at_ist}</td>
          <td style="padding: 6px 0; color: #64748b;">Validation Status:</td>
          <td style="padding: 6px 0;">{status_badge}</td>
        </tr>
      </table>

      {warnings_box}

      <!-- Production Data Table -->
      <div style="margin: 16px 0; overflow-x: auto;">
        <table style="width: 100%; border-collapse: collapse; text-align: left; font-size: 13px;">
          <thead>
            <tr style="background-color: #0b3c68; color: #ffffff;">
              <th style="padding: 10px 12px; width: 5%; text-align: center; font-size: 12px; text-transform: uppercase;">No.</th>
              <th style="padding: 10px 12px; width: 40%; text-align: left; font-size: 12px; text-transform: uppercase;">Type of Product</th>
              <th style="padding: 10px 12px; width: 20%; text-align: right; font-size: 12px; text-transform: uppercase;">Qty (Ltr)</th>
              <th style="padding: 10px 12px; width: 17%; text-align: right; font-size: 12px; text-transform: uppercase;">Qty (Pkt)</th>
              <th style="padding: 10px 12px; width: 18%; text-align: right; font-size: 12px; text-transform: uppercase;">Tray</th>
            </tr>
          </thead>
          <tbody>
            {"".join(rows_html)}
          </tbody>
        </table>
      </div>

    </div>

    <!-- Official Footer -->
    <div style="background-color: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px 24px; font-size: 12px; color: #64748b;">
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
        <span>Report ID: <code style="font-family: Consolas, monospace; color: #0284c7;">{report['id']}</code></span>
        <span>Generated via Live Aavin OCR Studio</span>
      </div>
      <p style="margin: 6px 0 0 0; font-size: 11px; color: #94a3b8;">
        Notice: Quantities and categories above were extracted from official dairy production abstract sheets. Discrepancies are flagged automatically for auditing.
      </p>
    </div>

  </div>
</body>
</html>"""

        return subject, plain_text, html_body

    @classmethod
    def send_report_email(
        cls,
        report_id: str,
        recipients: Optional[List[str]] = None,
        force: bool = False,
        user: str = "system"
    ) -> Dict[str, Any]:
        """
        Sends the verified HTML report email.
        Enforces idempotency, validation checks, and records delivery status.
        """
        report = reports_store.get_report(report_id)
        if not report:
            raise ValueError(f"Report {report_id} not found.")

        # Idempotency check: don't resend if already sent unless forced
        if report['email_status'] == 'SENT' and not force:
            logger.info("Report %s already sent at %s. Skipping duplicate send.", report_id, report['email_sent_at'])
            return {
                'success': True,
                'skipped': True,
                'status': 'SENT',
                'message': f"Report was already emailed at {report['email_sent_at']}. Use force=True to resend.",
                'sent_at': report['email_sent_at'],
                'report_id': report_id
            }

        # Verification check: do not send if NEEDS_REVIEW unless approved or forced
        if report['validation_status'] == 'NEEDS_REVIEW' and not force and not report.get('approved_by'):
            logger.warning("Report %s has validation_status=NEEDS_REVIEW and is not approved. Cannot email.", report_id)
            reports_store.update_email_status(report_id, 'NEEDS_REVIEW', details="Blocked email send: report requires human review.")
            return {
                'success': False,
                'status': 'NEEDS_REVIEW',
                'error': "Report requires review before sending. Approve the report or provide force=True.",
                'report_id': report_id,
                'validation_warnings': report['validation_warnings']
            }

        # Resolve target recipients and preferences
        config.reload_env()
        target_recipients: List[Dict[str, Any]] = []

        if recipients:
            pref_map = {p['email'].lower(): p for p in config.REPORT_RECIPIENT_PREFERENCES}
            for r in recipients:
                if isinstance(r, str):
                    addr = r.strip()
                    if not addr:
                        continue
                    if addr.lower() in pref_map:
                        target_recipients.append(pref_map[addr.lower()])
                    else:
                        target_recipients.append({'email': addr, 'send_pdf': True, 'send_excel': False})
                elif isinstance(r, dict):
                    addr = str(r.get('email', '')).strip()
                    if not addr:
                        continue
                    target_recipients.append({
                        'email': addr,
                        'send_pdf': bool(r.get('send_pdf', True)),
                        'send_excel': bool(r.get('send_excel', False)),
                    })
        else:
            target_recipients = list(config.REPORT_RECIPIENT_PREFERENCES)

        if not target_recipients:
            msg = "No recipient email configured (REPORT_EMAIL_TO is empty)."
            reports_store.update_email_status(report_id, 'FAILED', details=msg)
            return {'success': False, 'status': 'FAILED', 'error': msg, 'report_id': report_id}

        # Filter active recipients vs muted recipients (both unchecked = no email sent)
        active_recipients = [
            r for r in target_recipients
            if r.get('email') and (r.get('send_pdf') or r.get('send_excel'))
        ]
        skipped_recipients = [
            r for r in target_recipients
            if r.get('email') and not (r.get('send_pdf') or r.get('send_excel'))
        ]

        if not active_recipients:
            msg = f"All configured recipients ({', '.join(r['email'] for r in skipped_recipients)}) have both PDF and Excel unselected (muted). No email was sent."
            logger.info("Report %s skipped email delivery: %s", report_id, msg)
            reports_store.update_email_status(report_id, 'SKIPPED', details=msg)
            return {
                'success': True,
                'status': 'SKIPPED',
                'message': msg,
                'report_id': report_id,
                'skipped_recipients': [r['email'] for r in skipped_recipients]
            }

        subject, plain_body, html_body = cls.generate_email_content(report)
        date_str = format_report_date_subject(report['report_date'])
        shift_str = (report.get('shift') or 'shift').lower()
        pdf_filename = f"Aavin_Production_Abstract_{date_str}_{shift_str}.pdf"
        excel_filename = f"Aavin_Production_Abstract_{date_str}_{shift_str}.xlsx"

        # Generate required attachments
        needs_pdf = any(r.get('send_pdf') for r in active_recipients)
        needs_excel = any(r.get('send_excel') for r in active_recipients)

        pdf_bytes = generate_aavin_pdf(report) if needs_pdf else None
        excel_bytes = generate_aavin_excel(report) if needs_excel else None

        # Check if email sending is enabled (dry-run mode)
        if not config.REPORT_EMAIL_ENABLED:
            logger.info("REPORT_EMAIL_ENABLED is false. Simulating dry-run email for report %s", report_id)
            desc_list = []
            for r in active_recipients:
                atts = []
                if r.get('send_pdf'):
                    atts.append('PDF Report')
                if r.get('send_excel'):
                    atts.append('Excel Sheet')
                desc_list.append(f"{r['email']} ({' + '.join(atts)})")

            details_msg = f"Dry-run mode (REPORT_EMAIL_ENABLED=false). Prepared separate emails for: {'; '.join(desc_list)} with subject: '{subject}'"
            if skipped_recipients:
                details_msg += f". Skipped muted: {', '.join(r['email'] for r in skipped_recipients)}"

            reports_store.update_email_status(
                report_id,
                'DISABLED',
                details=details_msg
            )
            return {
                'success': True,
                'dry_run': True,
                'status': 'DISABLED',
                'active_recipients': active_recipients,
                'skipped_recipients': [r['email'] for r in skipped_recipients],
                'subject': subject,
                'message': "Email service is running in dry-run mode (REPORT_EMAIL_ENABLED=false). To send live emails, set REPORT_EMAIL_ENABLED=true and configure SMTP in .env.",
                'report_id': report_id
            }

        from_header = f"{config.SMTP_FROM_NAME} <{config.SMTP_FROM_EMAIL}>" if config.SMTP_FROM_NAME else config.SMTP_FROM_EMAIL
        delivered_recipients: List[str] = []
        delivery_errors: List[str] = []

        try:
            if config.SMTP_USE_SSL:
                server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
            else:
                server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=20)
                if config.SMTP_USE_TLS:
                    server.starttls()

            if config.SMTP_USER and config.SMTP_PASSWORD:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)

            # Send individual separate email to each recipient
            for target in active_recipients:
                target_email = target['email']
                msg = MIMEMultipart('mixed')
                msg['Subject'] = subject
                msg['From'] = from_header
                msg['To'] = target_email
                msg['Date'] = formatdate(localtime=True)
                msg['Message-ID'] = make_msgid(domain='aavin.local')

                # Body alternative container
                alt_part = MIMEMultipart('alternative')
                alt_part.attach(MIMEText(plain_body, 'plain', 'utf-8'))
                alt_part.attach(MIMEText(html_body, 'html', 'utf-8'))
                msg.attach(alt_part)

                # Attach PDF if selected for this recipient
                if target.get('send_pdf') and pdf_bytes:
                    part_pdf = MIMEApplication(pdf_bytes, _subtype='pdf')
                    part_pdf.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
                    msg.attach(part_pdf)

                # Attach Excel if selected for this recipient
                if target.get('send_excel') and excel_bytes:
                    part_excel = MIMEApplication(excel_bytes, _subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    part_excel.add_header('Content-Disposition', 'attachment', filename=excel_filename)
                    msg.attach(part_excel)

                server.sendmail(config.SMTP_FROM_EMAIL, [target_email], msg.as_string())
                delivered_recipients.append(target_email)

            server.quit()

            now_utc = datetime.now(timezone.utc).isoformat()
            audit_msg = f"Successfully delivered individual emails to {', '.join(delivered_recipients)}."
            if skipped_recipients:
                audit_msg += f" (Muted/Skipped: {', '.join(r['email'] for r in skipped_recipients)})"

            reports_store.update_email_status(
                report_id,
                'SENT',
                sent_at=now_utc,
                details=audit_msg
            )

            return {
                'success': True,
                'status': 'SENT',
                'sent_at': now_utc,
                'delivered_recipients': delivered_recipients,
                'skipped_recipients': [r['email'] for r in skipped_recipients],
                'subject': subject,
                'report_id': report_id
            }

        except Exception as e:
            clean_error = f"{type(e).__name__}: {str(e)}"
            logger.error("Failed to deliver Aavin report email for %s: %s", report_id, clean_error)
            reports_store.update_email_status(
                report_id,
                'FAILED',
                details=f"Email delivery error: {clean_error}"
            )
            return {
                'success': False,
                'status': 'FAILED',
                'error': clean_error,
                'report_id': report_id
            }

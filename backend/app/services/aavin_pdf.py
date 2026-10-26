import io
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def fmt_dec(val: Any) -> str:
    try:
        return f"{Decimal(str(val)):,.3f}"
    except Exception:
        return "0.000"


def fmt_int(val: Any) -> str:
    try:
        return f"{int(val):,}"
    except Exception:
        return "0"


def generate_aavin_pdf(report: Dict[str, Any]) -> bytes:
    """
    Renders an official, beautifully styled Choice A printable PDF report
    for an Aavin Milk Production Abstract.
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=36,
        rightMargin=36,
        topMargin=36,
        bottomMargin=36,
        title=f"Aavin Production Abstract - {report.get('report_date', '')}",
        author="Aavin OCR System"
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'AavinTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=HexColor('#1A365D'),
        alignment=1,  # Center
    )

    address_style = ParagraphStyle(
        'AavinAddress',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=HexColor('#4A5568'),
        alignment=1,
    )

    subtitle_style = ParagraphStyle(
        'AavinSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=HexColor('#2B6CB0'),
        alignment=1,
    )

    cell_style_left = ParagraphStyle(
        'CellLeft',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=HexColor('#1A202C'),
    )

    cell_style_center = ParagraphStyle(
        'CellCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=HexColor('#1A202C'),
        alignment=1,
    )

    cell_style_right = ParagraphStyle(
        'CellRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=HexColor('#1A202C'),
        alignment=2,
    )

    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=HexColor('#FFFFFF'),
        alignment=1,
    )

    header_style_right = ParagraphStyle(
        'HeaderCellRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=HexColor('#FFFFFF'),
        alignment=2,
    )

    header_style_left = ParagraphStyle(
        'HeaderCellLeft',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=HexColor('#FFFFFF'),
        alignment=0,
    )

    bold_cell_left = ParagraphStyle(
        'BoldCellLeft',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=HexColor('#1A202C'),
    )

    bold_cell_right = ParagraphStyle(
        'BoldCellRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=HexColor('#1A202C'),
        alignment=2,
    )

    grand_cell_left = ParagraphStyle(
        'GrandCellLeft',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=HexColor('#1A365D'),
    )

    grand_cell_right = ParagraphStyle(
        'GrandCellRight',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=12,
        textColor=HexColor('#1A365D'),
        alignment=2,
    )

    story = []

    # 1. Header Section
    story.append(Paragraph(report.get("organization_name", "Madurai District Co-operative Milk Producers' Union Ltd."), title_style))
    story.append(Spacer(1, 2))
    story.append(Paragraph(report.get("address", "Sathamangalam, Madurai - 625 020"), address_style))
    story.append(Spacer(1, 4))
    story.append(Paragraph("MILK & CURD PRODUCTION ABSTRACT REPORT", subtitle_style))
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1.5, color=HexColor('#2B6CB0'), spaceBefore=2, spaceAfter=8))

    # 2. Metadata Grid
    shift_label = report.get("shift", "").capitalize() if report.get("shift") else "Unknown"
    date_val = report.get("report_date", "")
    status_label = "Validated" if report.get("validation_status") == "VALIDATED" else "Needs Review"

    meta_data = [
        [
            Paragraph("<b>Union Code:</b>", cell_style_left),
            Paragraph(str(report.get("union_code", "N/A")), cell_style_left),
            Paragraph("<b>Report Date:</b>", cell_style_left),
            Paragraph(date_val, cell_style_left),
        ],
        [
            Paragraph("<b>Shift:</b>", cell_style_left),
            Paragraph(f"{shift_label} Shift", cell_style_left),
            Paragraph("<b>Status:</b>", cell_style_left),
            Paragraph(status_label, cell_style_left),
        ]
    ]

    meta_table = Table(meta_data, colWidths=[80, 180, 80, 180])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
    ]))
    story.append(meta_table)
    story.append(Spacer(1, 10))

    # 3. Main Data Table
    table_rows = []
    # Header row
    table_rows.append([
        Paragraph("Sl No", header_style),
        Paragraph("Type of Product", header_style_left),
        Paragraph("Qty (Litres)", header_style_right),
        Paragraph("Qty (Packets)", header_style_right),
        Paragraph("Tray Count", header_style_right),
    ])

    items = report.get("items", [])
    product_items = [i for i in items if i.get("row_type") == "PRODUCT"]
    milk_products = [i for i in product_items if i.get("category") == "MILK"]
    curd_products = [i for i in product_items if i.get("category") == "CURD_BUTTERMILK"]

    milk_subtotal = next((i for i in items if i.get("product_name") == "MILK TOTAL"), None)
    curd_subtotal = next((i for i in items if i.get("product_name") == "CURD & BUTTERMILK TOTAL"), None)
    grand_total = next((i for i in items if i.get("product_name") == "GRAND TOTAL"), None)

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), HexColor('#1A365D')),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CBD5E0')),
    ]

    row_idx = 1

    def append_section(title: str, prods: List[Dict[str, Any]], subtotal: Dict[str, Any] = None):
        nonlocal row_idx
        # Section title row
        table_rows.append([
            "",
            Paragraph(f"<b>{title}</b>", ParagraphStyle('SecHeader', parent=cell_style_left, fontName='Helvetica-Bold', textColor=HexColor('#2D3748'))),
            "", "", ""
        ])
        table_styles.extend([
            ('SPAN', (1, row_idx), (4, row_idx)),
            ('BACKGROUND', (0, row_idx), (-1, row_idx), HexColor('#E2E8F0')),
            ('TOPPADDING', (0, row_idx), (-1, row_idx), 3),
            ('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 3),
        ])
        row_idx += 1

        # Products
        for p in prods:
            table_rows.append([
                Paragraph(str(p.get("item_no", "")), cell_style_center),
                Paragraph(p.get("product_name", ""), cell_style_left),
                Paragraph(fmt_dec(p.get("quantity_litres", 0)), cell_style_right),
                Paragraph(fmt_int(p.get("quantity_packets", 0)), cell_style_right),
                Paragraph(fmt_dec(p.get("quantity_trays", 0)), cell_style_right),
            ])
            # Alternating light row fill
            if row_idx % 2 == 0:
                table_styles.append(('BACKGROUND', (0, row_idx), (-1, row_idx), HexColor('#F7FAFC')))
            row_idx += 1

        # Subtotal
        if subtotal:
            table_rows.append([
                "",
                Paragraph(f"<b>{subtotal.get('product_name', 'SUBTOTAL')}</b>", bold_cell_left),
                Paragraph(f"<b>{fmt_dec(subtotal.get('quantity_litres', 0))}</b>", bold_cell_right),
                Paragraph(f"<b>{fmt_int(subtotal.get('quantity_packets', 0))}</b>", bold_cell_right),
                Paragraph(f"<b>{fmt_dec(subtotal.get('quantity_trays', 0))}</b>", bold_cell_right),
            ])
            table_styles.extend([
                ('BACKGROUND', (0, row_idx), (-1, row_idx), HexColor('#EDF2F7')),
                ('LINEABOVE', (0, row_idx), (-1, row_idx), 1.0, HexColor('#2D3748')),
                ('LINEBELOW', (0, row_idx), (-1, row_idx), 1.0, HexColor('#2D3748')),
            ])
            row_idx += 1

    # Milk section
    append_section("MILK PRODUCTS", milk_products, milk_subtotal)

    # Curd section
    append_section("CURD & BUTTERMILK PRODUCTS", curd_products, curd_subtotal)

    # Grand total
    if grand_total:
        table_rows.append([
            "",
            Paragraph(f"<b>{grand_total.get('product_name', 'GRAND TOTAL')}</b>", grand_cell_left),
            Paragraph(f"<b>{fmt_dec(grand_total.get('quantity_litres', 0))}</b>", grand_cell_right),
            Paragraph(f"<b>{fmt_int(grand_total.get('quantity_packets', 0))}</b>", grand_cell_right),
            Paragraph(f"<b>{fmt_dec(grand_total.get('quantity_trays', 0))}</b>", grand_cell_right),
        ])
        table_styles.extend([
            ('BACKGROUND', (0, row_idx), (-1, row_idx), HexColor('#CBD5E0')),
            ('LINEABOVE', (0, row_idx), (-1, row_idx), 1.2, HexColor('#1A365D')),
            ('LINEBELOW', (0, row_idx), (-1, row_idx), 2.0, HexColor('#1A365D')),
            ('TOPPADDING', (0, row_idx), (-1, row_idx), 5),
            ('BOTTOMPADDING', (0, row_idx), (-1, row_idx), 5),
        ])
        row_idx += 1

    # Column widths summing to 520 pt
    col_widths = [35, 215, 90, 90, 90]
    report_table = Table(table_rows, colWidths=col_widths, repeatRows=1)
    report_table.setStyle(TableStyle(table_styles))
    story.append(report_table)

    # 4. Warnings if any
    warnings = report.get("validation_warnings", [])
    if warnings:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Audit Warnings:</b>", ParagraphStyle('WarnHead', parent=cell_style_left, fontName='Helvetica-Bold', textColor=HexColor('#C53030'))))
        for w in warnings:
            story.append(Paragraph(f"• {w}", ParagraphStyle('WarnItem', parent=cell_style_left, fontSize=8, textColor=HexColor('#9B2C2C'))))

    # 5. Footer info
    story.append(Spacer(1, 15))
    footer_text = f"Generated by Aavin OCR Production Monitoring System on {datetime.now().strftime('%d-%b-%Y at %I:%M %p')}"
    story.append(Paragraph(footer_text, ParagraphStyle('FooterStyle', parent=styles['Normal'], fontName='Helvetica-Oblique', fontSize=8, textColor=HexColor('#718096'), alignment=1)))

    doc.build(story)
    return buf.getvalue()

import io
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def format_decimal(val: Any) -> float:
    try:
        return float(Decimal(str(val)))
    except Exception:
        return 0.0


def format_int(val: Any) -> int:
    try:
        return int(val)
    except Exception:
        return 0


def generate_aavin_excel(report: Dict[str, Any]) -> bytes:
    """
    Generates a professionally formatted Excel spreadsheet (.xlsx) for an
    Aavin Milk Production Abstract report.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Production Abstract"
    ws.views.sheetView[0].showGridLines = True

    # Color definitions
    navy_fill = PatternFill(start_color="1A365D", end_color="1A365D", fill_type="solid")
    section_fill = PatternFill(start_color="E2E8F0", end_color="E2E8F0", fill_type="solid")
    subtotal_fill = PatternFill(start_color="EDF2F7", end_color="EDF2F7", fill_type="solid")
    grand_total_fill = PatternFill(start_color="CBD5E0", end_color="CBD5E0", fill_type="solid")

    # Font definitions
    title_font = Font(name="Calibri", size=14, bold=True, color="1A365D")
    sub_title_font = Font(name="Calibri", size=10, italic=True, color="4A5568")
    meta_bold = Font(name="Calibri", size=10, bold=True, color="2D3748")
    meta_regular = Font(name="Calibri", size=10, color="2D3748")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    section_font = Font(name="Calibri", size=10, bold=True, color="2D3748")
    data_font = Font(name="Calibri", size=10, color="1A202C")
    total_font = Font(name="Calibri", size=11, bold=True, color="1A202C")
    grand_font = Font(name="Calibri", size=11, bold=True, color="1A365D")

    # Borders
    thin_line = Side(border_style="thin", color="CBD5E0")
    double_bottom = Side(border_style="double", color="1A202C")
    thick_top = Side(border_style="thin", color="1A202C")

    cell_border = Border(left=thin_line, right=thin_line, top=thin_line, bottom=thin_line)
    subtotal_border = Border(top=thick_top, bottom=thick_top, left=thin_line, right=thin_line)
    grand_border = Border(top=thick_top, bottom=double_bottom, left=thin_line, right=thin_line)

    # 1. Title Block
    ws.merge_cells("A1:E1")
    ws["A1"] = report.get("organization_name", "Madurai District Co-operative Milk Producers' Union Ltd.")
    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A2:E2")
    ws["A2"] = report.get("address", "Sathamangalam, Madurai - 625 020")
    ws["A2"].font = sub_title_font
    ws["A2"].alignment = Alignment(horizontal="center", vertical="center")

    ws.merge_cells("A3:E3")
    ws["A3"] = "MILK & CURD PRODUCTION ABSTRACT REPORT"
    ws["A3"].font = Font(name="Calibri", size=12, bold=True, color="2B6CB0")
    ws["A3"].alignment = Alignment(horizontal="center", vertical="center")

    # 2. Metadata Block
    shift_label = report.get("shift", "").capitalize() if report.get("shift") else "Unknown"
    date_val = report.get("report_date", "")

    meta_rows = [
        ("Union Code:", report.get("union_code", "N/A"), "Report Date:", date_val),
        ("Shift:", f"{shift_label} Shift", "Status:", report.get("validation_status", "VALIDATED")),
    ]

    curr_row = 5
    for m in meta_rows:
        ws.cell(row=curr_row, column=1, value=m[0]).font = meta_bold
        ws.cell(row=curr_row, column=2, value=m[1]).font = meta_regular
        ws.cell(row=curr_row, column=4, value=m[2]).font = meta_bold
        ws.cell(row=curr_row, column=5, value=m[3]).font = meta_regular
        curr_row += 1

    curr_row += 1  # blank line

    # 3. Table Header
    headers = ["Sl No", "Type of Product", "Qty (Litres)", "Qty (Packets)", "Tray Count"]
    for col_idx, h_text in enumerate(headers, start=1):
        c = ws.cell(row=curr_row, column=col_idx, value=h_text)
        c.fill = navy_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center" if col_idx in (1, 4) else "right" if col_idx in (3, 5) else "left", vertical="center")
        c.border = cell_border
    ws.row_dimensions[curr_row].height = 24
    curr_row += 1

    items = report.get("items", [])
    product_items = [i for i in items if i.get("row_type") == "PRODUCT"]
    milk_products = [i for i in product_items if i.get("category") == "MILK"]
    curd_products = [i for i in product_items if i.get("category") == "CURD_BUTTERMILK"]

    milk_subtotal = next((i for i in items if i.get("product_name") == "MILK TOTAL"), None)
    curd_subtotal = next((i for i in items if i.get("product_name") == "CURD & BUTTERMILK TOTAL"), None)
    grand_total = next((i for i in items if i.get("product_name") == "GRAND TOTAL"), None)

    # Helper: write product section
    def write_section(title: str, prods: List[Dict[str, Any]], subtotal: Dict[str, Any] = None):
        nonlocal curr_row
        # Section header
        ws.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=5)
        sec_cell = ws.cell(row=curr_row, column=1, value=title)
        sec_cell.fill = section_fill
        sec_cell.font = section_font
        sec_cell.alignment = Alignment(horizontal="left", vertical="center")
        for col_idx in range(1, 6):
            ws.cell(row=curr_row, column=col_idx).border = cell_border
        curr_row += 1

        # Product rows
        for p in prods:
            c1 = ws.cell(row=curr_row, column=1, value=p.get("item_no", ""))
            c2 = ws.cell(row=curr_row, column=2, value=p.get("product_name", ""))
            c3 = ws.cell(row=curr_row, column=3, value=format_decimal(p.get("quantity_litres", 0)))
            c4 = ws.cell(row=curr_row, column=4, value=format_int(p.get("quantity_packets", 0)))
            c5 = ws.cell(row=curr_row, column=5, value=format_decimal(p.get("quantity_trays", 0)))

            c1.alignment = Alignment(horizontal="center")
            c2.alignment = Alignment(horizontal="left")
            c3.alignment = Alignment(horizontal="right")
            c4.alignment = Alignment(horizontal="right")
            c5.alignment = Alignment(horizontal="right")

            c3.number_format = "#,##0.000"
            c4.number_format = "#,##0"
            c5.number_format = "#,##0.000"

            for cell in (c1, c2, c3, c4, c5):
                cell.font = data_font
                cell.border = cell_border
            curr_row += 1

        # Subtotal row
        if subtotal:
            ws.cell(row=curr_row, column=1, value="")
            c2 = ws.cell(row=curr_row, column=2, value=subtotal.get("product_name", "SUBTOTAL"))
            c3 = ws.cell(row=curr_row, column=3, value=format_decimal(subtotal.get("quantity_litres", 0)))
            c4 = ws.cell(row=curr_row, column=4, value=format_int(subtotal.get("quantity_packets", 0)))
            c5 = ws.cell(row=curr_row, column=5, value=format_decimal(subtotal.get("quantity_trays", 0)))

            c2.alignment = Alignment(horizontal="left")
            c3.alignment = Alignment(horizontal="right")
            c4.alignment = Alignment(horizontal="right")
            c5.alignment = Alignment(horizontal="right")

            c3.number_format = "#,##0.000"
            c4.number_format = "#,##0"
            c5.number_format = "#,##0.000"

            for col_idx in range(1, 6):
                cell = ws.cell(row=curr_row, column=col_idx)
                cell.font = total_font
                cell.fill = subtotal_fill
                cell.border = subtotal_border
            curr_row += 1

    # Write Milk Section
    write_section("MILK PRODUCTS", milk_products, milk_subtotal)

    # Write Curd Section
    write_section("CURD & BUTTERMILK PRODUCTS", curd_products, curd_subtotal)

    # Write Grand Total
    if grand_total:
        ws.cell(row=curr_row, column=1, value="")
        c2 = ws.cell(row=curr_row, column=2, value=grand_total.get("product_name", "GRAND TOTAL"))
        c3 = ws.cell(row=curr_row, column=3, value=format_decimal(grand_total.get("quantity_litres", 0)))
        c4 = ws.cell(row=curr_row, column=4, value=format_int(grand_total.get("quantity_packets", 0)))
        c5 = ws.cell(row=curr_row, column=5, value=format_decimal(grand_total.get("quantity_trays", 0)))

        c2.alignment = Alignment(horizontal="left")
        c3.alignment = Alignment(horizontal="right")
        c4.alignment = Alignment(horizontal="right")
        c5.alignment = Alignment(horizontal="right")

        c3.number_format = "#,##0.000"
        c4.number_format = "#,##0"
        c5.number_format = "#,##0.000"

        for col_idx in range(1, 6):
            cell = ws.cell(row=curr_row, column=col_idx)
            cell.font = grand_font
            cell.fill = grand_total_fill
            cell.border = grand_border
        curr_row += 1

    # Warnings / Notes if any
    warnings = report.get("validation_warnings", [])
    if warnings:
        curr_row += 1
        ws.cell(row=curr_row, column=1, value="Audit Warnings:").font = Font(bold=True, color="C53030")
        curr_row += 1
        for w in warnings:
            ws.cell(row=curr_row, column=2, value=f"• {w}").font = Font(italic=True, color="742A2A")
            curr_row += 1

    # Auto-fit column widths
    col_widths = {1: 10, 2: 34, 3: 18, 4: 16, 5: 16}
    for col_idx, width in col_widths.items():
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()

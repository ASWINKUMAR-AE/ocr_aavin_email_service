import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple


def sanitize_decimal_str(val: Any) -> str:
    """Sanitize decimal string, handling commas, spaces, and OCR noise."""
    if val is None:
        return "0.000"
    s = str(val).strip().replace(' ', '')
    # If comma is followed by 3 or 4 digits and preceded by digits, treat as decimal point
    if re.search(r'\d+,\d{3,4}$', s):
        s = s.replace(',', '.')
    else:
        s = s.replace(',', '')
    # Strip any trailing non-numeric except digits and dot
    s = re.sub(r'[^\d.]', '', s)
    if not s or s == '.':
        return "0.000"
    try:
        d = Decimal(s)
        return f"{d:.3f}"
    except (InvalidOperation, ValueError):
        return "0.000"


def sanitize_int(val: Any) -> int:
    """Sanitize integer, converting floats or strings safely."""
    if val is None:
        return 0
    if isinstance(val, int):
        return val
    s = str(val).strip().replace(',', '').replace(' ', '')
    s = re.sub(r'[^\d]', '', s)
    if not s:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def extract_unit_size_litres(product_name: str) -> Optional[Decimal]:
    """Determine nominal package unit size in litres from product description."""
    upper = product_name.upper()
    if '500 ML' in upper or '500ML' in upper:
        return Decimal('0.5')
    if '200 ML' in upper or '200ML' in upper:
        return Decimal('0.2')
    if '1000 ML' in upper or '1000ML' in upper or '1 LTR' in upper:
        return Decimal('1.0')
    if '500 GM' in upper or '500GM' in upper:
        return Decimal('0.5')
    if '200 GM' in upper or '200GM' in upper:
        return Decimal('0.2')
    if '145 ML' in upper or '145ML' in upper:
        return Decimal('0.145')
    if '140 ML' in upper or '140ML' in upper:
        return Decimal('0.140')
    return None


class AavinAbstractParser:
    """
    Parser for Aavin Milk Production Abstract reports.
    Extracts headers, product rows, subtotals, grand totals,
    performs conservative numeric normalization and cross-validation.
    """

    @classmethod
    def is_aavin_abstract(cls, text: str) -> bool:
        """Check if OCR text matches an Aavin abstract report."""
        if not text:
            return False
        upper = text.upper()
        matches = [
            'MADURAI' in upper,
            'CO-OPERATIVE MILK' in upper or 'PRODUCERS' in upper or 'AAVIN' in upper,
            'ABSTRACT' in upper,
            'COW MILK' in upper or 'MILK TOTAL' in upper or 'GRAND TOTAL' in upper or 'CURD' in upper
        ]
        return sum(matches) >= 2

    @classmethod
    def parse_header(cls, text: str) -> Tuple[Dict[str, Any], List[str]]:
        """Extract organization, union code, date, shift, address."""
        warnings: List[str] = []
        header: Dict[str, Any] = {
            'union_code': 'GA1301',
            'organization_name': "THE MADURAI DISTRICT CO-OPERATIVE MILK PRODUCERS' UNION LTD.",
            'address': "SIVAGANGAI MAIN ROAD, MADURAI - 625 020",
            'report_date': '',
            'shift': '',
            'abstract_no': '',
        }

        # Union Code
        m_code = re.search(r'\b(GA\s*[0-9OIl]{3,5})\b', text, re.IGNORECASE)
        if m_code:
            code_raw = m_code.group(1).replace(' ', '').upper()
            # Normalize common OCR digit confusions: 'O' -> '0', 'I'/'L' -> '1'
            normalized_code = 'GA' + code_raw[2:].replace('O', '0').replace('I', '1').replace('L', '1')
            header['union_code'] = normalized_code
        else:
            warnings.append("Union code not clearly found; defaulted to GA1301.")

        # Date extraction: DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY, or YYYY-MM-DD
        m_date = re.search(r'(?:DATE|DT|DATED)[:\s]*(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', text, re.IGNORECASE)
        if not m_date:
            m_date = re.search(r'\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b', text)

        if m_date:
            day, month, year = int(m_date.group(1)), int(m_date.group(2)), int(m_date.group(3))
            try:
                dt = datetime(year, month, day)
                header['report_date'] = dt.strftime('%Y-%m-%d')
            except ValueError:
                warnings.append(f"Invalid date values: {day}.{month}.{year}")
        else:
            # Check ISO format
            m_iso = re.search(r'\b(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})\b', text)
            if m_iso:
                year, month, day = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
                try:
                    dt = datetime(year, month, day)
                    header['report_date'] = dt.strftime('%Y-%m-%d')
                except ValueError:
                    warnings.append(f"Invalid ISO date values: {year}-{month}-{day}")

        if not header['report_date']:
            warnings.append("Report date could not be trustworthy extracted from OCR text.")

        # Shift extraction
        m_shift = re.search(r'\bSHIFT[:\s]*([A-Za-z]+)', text, re.IGNORECASE)
        if m_shift:
            s_val = m_shift.group(1).strip().upper()
            if s_val in ('MORNING', 'EVENING', 'NIGHT'):
                header['shift'] = s_val
            elif 'MORN' in s_val:
                header['shift'] = 'MORNING'
            elif 'EVEN' in s_val:
                header['shift'] = 'EVENING'
            else:
                header['shift'] = s_val
        else:
            if 'EVENING' in text.upper():
                header['shift'] = 'EVENING'
            elif 'MORNING' in text.upper():
                header['shift'] = 'MORNING'

        if not header['shift']:
            warnings.append("Shift could not be extracted from OCR text.")

        # Abstract No
        m_abs = re.search(r'ABSTRACT\s*NO\.?[:\s]*([A-Za-z0-9\-]*)', text, re.IGNORECASE)
        if m_abs:
            header['abstract_no'] = m_abs.group(1).strip()

        return header, warnings

    @classmethod
    def parse_rows(cls, text: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any], List[str]]:
        """
        Extract line items, subtotal rows, and grand totals from OCR text.
        Conservative normalization is applied when column borders attach digits.
        """
        warnings: List[str] = []
        items: List[Dict[str, Any]] = []

        subtotals: Dict[str, Any] = {
            'milk_total_litres': Decimal('0.000'),
            'milk_total_packets': 0,
            'milk_total_trays': Decimal('0.000'),
            'curd_buttermilk_total_litres': Decimal('0.000'),
            'curd_buttermilk_total_packets': 0,
            'curd_buttermilk_total_trays': Decimal('0.000'),
            'grand_total_litres': Decimal('0.000'),
            'grand_total_packets': 0,
            'grand_total_trays': Decimal('0.000'),
        }

        # Normalize line breaks and spaces for regex token extraction
        cleaned_text = re.sub(r'[\r\n]+', ' ', text)
        cleaned_text = re.sub(r'\s+', ' ', cleaned_text)

        # 1. Look for subtotals and grand total
        # Milk Total
        m_milk_tot = re.search(
            r'MILK\s+TOTAL\s+([0-9.,|I]+)\s+([0-9.,|I]+)\s+([0-9.,|I]+)',
            cleaned_text, re.IGNORECASE
        )
        if m_milk_tot:
            subtotals['milk_total_litres'] = Decimal(sanitize_decimal_str(m_milk_tot.group(1)))
            subtotals['milk_total_packets'] = sanitize_int(m_milk_tot.group(2))
            subtotals['milk_total_trays'] = Decimal(sanitize_decimal_str(m_milk_tot.group(3)))
        else:
            warnings.append("Subtotal MILK TOTAL was not explicitly identified in OCR text.")

        # Curd & Buttermilk Total
        m_curd_tot = re.search(
            r'CURD\s*&\s*BUTTERMILK\s+TOTAL\s+([0-9.,|I]+)\s+([0-9.,|I]+)\s+([0-9.,|I]+)',
            cleaned_text, re.IGNORECASE
        )
        if m_curd_tot:
            subtotals['curd_buttermilk_total_litres'] = Decimal(sanitize_decimal_str(m_curd_tot.group(1)))
            subtotals['curd_buttermilk_total_packets'] = sanitize_int(m_curd_tot.group(2))
            subtotals['curd_buttermilk_total_trays'] = Decimal(sanitize_decimal_str(m_curd_tot.group(3)))
        else:
            warnings.append("Subtotal CURD & BUTTERMILK TOTAL was not explicitly identified in OCR text.")

        # Grand Total
        m_grand_tot = re.search(
            r'GRAND\s+TOTAL\s+([0-9.,|I]+)\s+([0-9.,|I]+)\s+([0-9.,|I]+)',
            cleaned_text, re.IGNORECASE
        )
        if m_grand_tot:
            subtotals['grand_total_litres'] = Decimal(sanitize_decimal_str(m_grand_tot.group(1)))
            subtotals['grand_total_packets'] = sanitize_int(m_grand_tot.group(2))
            subtotals['grand_total_trays'] = Decimal(sanitize_decimal_str(m_grand_tot.group(3)))
        else:
            warnings.append("GRAND TOTAL row was not explicitly identified in OCR text.")

        # 2. Extract numbered product rows
        # Pattern: item_no (1-99), Product Name (text), Qty Ltr, Qty Pkt, Tray
        # We search for lines starting with digit followed by product text
        item_pattern = re.compile(
            r'(?:(?<=\s)|^)(\d{1,2})\s+([A-Za-z0-9\s\-+]+?)\s+([0-9.,|I]+)\s+([0-9.,|I]+)\s+([0-9.,|I]+)(?=\s+(?:\d{1,2}\s+[A-Za-z]|MILK|CURD|GRAND|\Z))',
            re.IGNORECASE
        )

        matches = list(item_pattern.finditer(cleaned_text))
        for m in matches:
            item_no = int(m.group(1))
            raw_pname = m.group(2).strip()
            raw_ltr = m.group(3).strip()
            raw_pkt = m.group(4).strip()
            raw_tray = m.group(5).strip()

            # Ignore if product name is or starts with header terms
            if any(term in raw_pname.upper() for term in ('TYPE OF PRODUCT', 'ABSTRACT NO')):
                continue

            # Determine category: Curd & Buttermilk vs Milk
            upper_name = raw_pname.upper()
            if 'CURD' in upper_name or 'BUTTERMILK' in upper_name:
                category = 'CURD_BUTTERMILK'
            else:
                category = 'MILK'

            # Parse numeric values conservatively
            nom_unit = extract_unit_size_litres(raw_pname)

            parsed_pkt = sanitize_int(raw_pkt)
            parsed_ltr = Decimal(sanitize_decimal_str(raw_ltr))
            parsed_tray = Decimal(sanitize_decimal_str(raw_tray))

            # Conservative normalization check:
            # In tabular dot-matrix OCR, a trailing '1' or '|' from vertical column border
            # can attach to packets and litres.
            # E.g. raw_pkt = 515531 (should be 51553), raw_ltr = 25776.5001 (should be 25776.500)
            if nom_unit is not None:
                # Check if raw_pkt has trailing 1 artifact:
                if str(parsed_pkt).endswith('1') and parsed_pkt > 10:
                    cand_pkt = int(str(parsed_pkt)[:-1])
                    if cand_pkt * nom_unit == (parsed_ltr - Decimal('0.001')) or cand_pkt * nom_unit == (parsed_ltr - Decimal('0.0001')) or cand_pkt * nom_unit == Decimal(f"{parsed_ltr:.2f}"):
                        parsed_pkt = cand_pkt
                        parsed_ltr = cand_pkt * nom_unit
                    elif cand_pkt * nom_unit == Decimal(f"{cand_pkt * nom_unit:.3f}") and abs((cand_pkt * nom_unit) - parsed_ltr) < Decimal('1.0'):
                        parsed_pkt = cand_pkt
                        parsed_ltr = cand_pkt * nom_unit

                # Check if litres string had comma or trailing 1
                if raw_ltr.endswith('1') and len(raw_ltr) > 5 and '.' in sanitize_decimal_str(raw_ltr):
                    # Check if removing trailing 1 matches pkt * nom_unit
                    cand_ltr_str = raw_ltr[:-1]
                    cand_ltr = Decimal(sanitize_decimal_str(cand_ltr_str))
                    if parsed_pkt * nom_unit == cand_ltr:
                        parsed_ltr = cand_ltr

                # Check if calculated pkt * unit matches litres
                calc_ltr = parsed_pkt * nom_unit
                if abs(calc_ltr - parsed_ltr) > Decimal('0.05'):
                    warnings.append(
                        f"Line #{item_no} ({raw_pname}): packets({parsed_pkt}) * unit({nom_unit}L) = {calc_ltr}L, but extracted is {parsed_ltr}L."
                    )

            # Tray check: if raw_tray has trailing 1 artifact (e.g. 2148.011 instead of 2148.001)
            # We preserve extracted tray but sanitize decimals
            items.append({
                'item_no': item_no,
                'product_name': raw_pname,
                'category': category,
                'quantity_litres': f"{parsed_ltr:.3f}",
                'quantity_packets': parsed_pkt,
                'quantity_trays': f"{parsed_tray:.3f}",
                'row_type': 'PRODUCT',
                'raw_tokens': {
                    'litres': raw_ltr,
                    'packets': raw_pkt,
                    'trays': raw_tray,
                }
            })

        # Sort items by item_no
        items.sort(key=lambda x: x['item_no'])

        if not items:
            warnings.append("No individual product rows could be recognized from OCR text.")

        return items, subtotals, warnings

    @classmethod
    def validate_totals(
        cls,
        items: List[Dict[str, Any]],
        subtotals: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """
        Cross-validate line items against subtotals and grand total.
        Flags any arithmetic discrepancies.
        """
        warnings: List[str] = []

        milk_items = [i for i in items if i['category'] == 'MILK']
        curd_items = [i for i in items if i['category'] == 'CURD_BUTTERMILK']

        # Milk sums
        calc_milk_ltr = sum((Decimal(i['quantity_litres']) for i in milk_items), Decimal('0.000'))
        calc_milk_pkt = sum(i['quantity_packets'] for i in milk_items)

        # Curd & Buttermilk sums
        calc_curd_ltr = sum((Decimal(i['quantity_litres']) for i in curd_items), Decimal('0.000'))
        calc_curd_pkt = sum(i['quantity_packets'] for i in curd_items)

        # Check Milk Totals
        ext_milk_ltr = subtotals['milk_total_litres']
        ext_milk_pkt = subtotals['milk_total_packets']
        if ext_milk_ltr > Decimal('0.000'):
            if abs(calc_milk_ltr - ext_milk_ltr) > Decimal('0.005'):
                warnings.append(
                    f"Milk Litres mismatch: sum of items is {calc_milk_ltr:.3f} L, but extracted subtotal is {ext_milk_ltr:.3f} L."
                )
        else:
            subtotals['milk_total_litres'] = calc_milk_ltr

        if ext_milk_pkt > 0:
            if calc_milk_pkt != ext_milk_pkt:
                warnings.append(
                    f"Milk Packets mismatch: sum of items is {calc_milk_pkt}, but extracted subtotal is {ext_milk_pkt}."
                )
        else:
            subtotals['milk_total_packets'] = calc_milk_pkt

        # Check Curd & Buttermilk Totals
        ext_curd_ltr = subtotals['curd_buttermilk_total_litres']
        ext_curd_pkt = subtotals['curd_buttermilk_total_packets']
        if ext_curd_ltr > Decimal('0.000'):
            if abs(calc_curd_ltr - ext_curd_ltr) > Decimal('0.005'):
                warnings.append(
                    f"Curd/Buttermilk Litres mismatch: sum of items is {calc_curd_ltr:.3f} L, but extracted subtotal is {ext_curd_ltr:.3f} L."
                )
        else:
            subtotals['curd_buttermilk_total_litres'] = calc_curd_ltr

        if ext_curd_pkt > 0:
            if calc_curd_pkt != ext_curd_pkt:
                warnings.append(
                    f"Curd/Buttermilk Packets mismatch: sum of items is {calc_curd_pkt}, but extracted subtotal is {ext_curd_pkt}."
                )
        else:
            subtotals['curd_buttermilk_total_packets'] = calc_curd_pkt

        # Check Grand Totals
        calc_grand_ltr = calc_milk_ltr + calc_curd_ltr
        calc_grand_pkt = calc_milk_pkt + calc_curd_pkt

        ext_grand_ltr = subtotals['grand_total_litres']
        ext_grand_pkt = subtotals['grand_total_packets']

        if ext_grand_ltr > Decimal('0.000'):
            if abs(calc_grand_ltr - ext_grand_ltr) > Decimal('0.005'):
                warnings.append(
                    f"Grand Total Litres mismatch: calculated {calc_grand_ltr:.3f} L, but extracted grand total is {ext_grand_ltr:.3f} L."
                )
        else:
            subtotals['grand_total_litres'] = calc_grand_ltr

        if ext_grand_pkt > 0:
            if calc_grand_pkt != ext_grand_pkt:
                warnings.append(
                    f"Grand Total Packets mismatch: calculated {calc_grand_pkt}, but extracted grand total is {ext_grand_pkt}."
                )
        else:
            subtotals['grand_total_packets'] = calc_grand_pkt

        is_valid = (len(warnings) == 0)
        return is_valid, warnings

    @classmethod
    def parse_aavin_abstract(
        cls,
        raw_text: str,
        ocr_created_at: Optional[str] = None,
        document_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Main entry point for parsing and validating an Aavin production abstract report.
        Returns report dictionary structure ready for database persistence.
        """
        if not cls.is_aavin_abstract(raw_text):
            return None

        now_utc = datetime.now(timezone.utc).isoformat()
        ocr_timestamp = ocr_created_at or now_utc

        header, h_warnings = cls.parse_header(raw_text)
        items, subtotals, r_warnings = cls.parse_rows(raw_text)
        is_valid_totals, v_warnings = cls.validate_totals(items, subtotals)

        all_warnings = h_warnings + r_warnings + v_warnings

        # A report needs review if date is missing, shift is missing, items are missing, or arithmetic fails
        needs_review = (
            not header['report_date'] or
            not header['shift'] or
            len(items) == 0 or
            not is_valid_totals
        )

        validation_status = 'NEEDS_REVIEW' if needs_review else 'VALIDATED'

        # Also create summary row items for report_items table
        final_items: List[Dict[str, Any]] = []
        for itm in items:
            final_items.append({
                'item_no': itm['item_no'],
                'product_name': itm['product_name'],
                'category': itm['category'],
                'quantity_litres': itm['quantity_litres'],
                'quantity_packets': itm['quantity_packets'],
                'quantity_trays': itm['quantity_trays'],
                'row_type': 'PRODUCT'
            })

        # Add Milk Subtotal item
        final_items.append({
            'item_no': 901,
            'product_name': 'MILK TOTAL',
            'category': 'MILK',
            'quantity_litres': f"{subtotals['milk_total_litres']:.3f}",
            'quantity_packets': subtotals['milk_total_packets'],
            'quantity_trays': f"{subtotals['milk_total_trays']:.3f}",
            'row_type': 'SUBTOTAL'
        })

        # Add Curd & Buttermilk Subtotal item
        final_items.append({
            'item_no': 902,
            'product_name': 'CURD & BUTTERMILK TOTAL',
            'category': 'CURD_BUTTERMILK',
            'quantity_litres': f"{subtotals['curd_buttermilk_total_litres']:.3f}",
            'quantity_packets': subtotals['curd_buttermilk_total_packets'],
            'quantity_trays': f"{subtotals['curd_buttermilk_total_trays']:.3f}",
            'row_type': 'SUBTOTAL'
        })

        # Add Grand Total item
        final_items.append({
            'item_no': 999,
            'product_name': 'GRAND TOTAL',
            'category': 'TOTAL',
            'quantity_litres': f"{subtotals['grand_total_litres']:.3f}",
            'quantity_packets': subtotals['grand_total_packets'],
            'quantity_trays': f"{subtotals['grand_total_trays']:.3f}",
            'row_type': 'GRAND_TOTAL'
        })

        report_data = {
            'document_id': document_id,
            'union_code': header['union_code'],
            'organization_name': header['organization_name'],
            'address': header['address'],
            'report_date': header['report_date'],
            'shift': header['shift'],
            'abstract_no': header['abstract_no'],
            'milk_total_litres': f"{subtotals['milk_total_litres']:.3f}",
            'milk_total_packets': subtotals['milk_total_packets'],
            'milk_total_trays': f"{subtotals['milk_total_trays']:.3f}",
            'curd_buttermilk_total_litres': f"{subtotals['curd_buttermilk_total_litres']:.3f}",
            'curd_buttermilk_total_packets': subtotals['curd_buttermilk_total_packets'],
            'curd_buttermilk_total_trays': f"{subtotals['curd_buttermilk_total_trays']:.3f}",
            'grand_total_litres': f"{subtotals['grand_total_litres']:.3f}",
            'grand_total_packets': subtotals['grand_total_packets'],
            'grand_total_trays': f"{subtotals['grand_total_trays']:.3f}",
            'raw_ocr_text': raw_text,
            'validation_status': validation_status,
            'validation_warnings': all_warnings,
            'ocr_created_at': ocr_timestamp,
            'report_processed_at': now_utc,
            'email_status': 'NEEDS_REVIEW' if needs_review else 'PENDING',
            'items': final_items
        }

        return report_data

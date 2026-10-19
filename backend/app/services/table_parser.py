"""User-adjustable grid suggestion and provenance-preserving cell assignment."""
import bisect
import re
from statistics import median

import cv2
import numpy as np

from app.services.layout import bounds, visual_rows

FARMER_COLUMNS = [
    {'name': 'S.No.', 'kind': 'text'}, {'name': 'Farmer Name', 'kind': 'text'},
    {'name': 'Farmer Aadhaar No.', 'kind': 'aadhaar'}, {'name': 'Share No.', 'kind': 'text'},
    {'name': 'Share Aadhaar No.', 'kind': 'aadhaar'}, {'name': 'Relationship', 'kind': 'text'},
    {'name': 'Address', 'kind': 'text'}, {'name': 'Phone No.', 'kind': 'phone'},
]


def cluster(values, tolerance):
    groups = []
    for value in sorted(values):
        if groups and value - median(groups[-1]) < tolerance:
            groups[-1].append(value)
        else:
            groups.append([value])
    return [float(median(g)) for g in groups]


def suggest_layout(path, page, lines):
    image = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError('Cannot read source page')
    # Limit CV memory/work independently of original page resolution.
    scale = min(1, 1600 / max(image.shape[:2]))
    if scale < 1:
        image = cv2.resize(image, None, fx=scale, fy=scale)
    h, w = image.shape[:2]
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    colored = cv2.inRange(hsv, np.array([90, 45, 25]), np.array([175, 255, 230]))
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12)

    def vertical_rules(mask):
        segments = cv2.HoughLinesP(mask, 1, np.pi / 180, threshold=max(30, round(h * .08)),
            minLineLength=max(20, h * .26), maxLineGap=max(10, h * .025))
        candidates = []
        for x1, y1, x2, y2 in ([] if segments is None else segments[:, 0]):
            if abs(y2 - y1) > abs(x2 - x1) * 8:
                x = x1 + (h / 2 - y1) * (x2 - x1) / (y2 - y1)
                candidates.append((x, min(y1, y2), max(y1, y2)))
        positions = cluster([c[0] for c in candidates], w * .012)
        result = []
        for x in positions:
            ranges = sorted((a, b) for cx, a, b in candidates if abs(cx - x) < w * .012)
            end, coverage = -1, 0
            for a, b in ranges:
                coverage += max(0, b - max(a, end))
                end = max(end, b)
            if coverage >= h * .50 and 0 < x < w:
                result.append(x / scale)
        return result

    edges = vertical_rules(colored)
    rule_mask = colored
    if len(edges) < 3:
        edges = vertical_rules(binary)
        rule_mask = binary
    width, height = page['width'], page['height']
    centers = [(bounds(l)[0] + bounds(l)[2]) / 2 for l in lines]
    if not edges:
        edges = [0, width]
    else:
        if not centers or min(centers) < edges[0]:
            edges.insert(0, 0)
        if not centers or max(centers) > edges[-1]:
            edges.append(width)
    edges = [round(e, 2) for e in edges][:31]
    if len(edges) < 2:
        edges = [0, width]
    horizontal = cv2.morphologyEx(rule_mask, cv2.MORPH_OPEN,
                                  cv2.getStructuringElement(cv2.MORPH_RECT, (max(10, round(w * .16)), 1)))
    contours, _ = cv2.findContours(horizontal, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    rules = cluster([(y + bh / 2) / scale for c in contours for x, y, bw, bh in [cv2.boundingRect(c)]
                     if bw > w * .24], height * .012)
    # A header between two early long rules is a suggestion, exposed for correction.
    early = [y for y in rules if y < height * .28]
    top = early[1] if len(early) >= 2 else 0
    columns = [dict(c) for c in FARMER_COLUMNS] if len(edges) == 9 else [
        {'name': f'Column {i + 1}', 'kind': 'text'} for i in range(len(edges) - 1)]
    buckets = [[] for _ in columns]
    for line in lines:
        x0, y0, x1, y1 = bounds(line)
        col = bisect.bisect_right(edges, (x0 + x1) / 2) - 1
        if 0 <= col < len(buckets) and (y0 + y1) / 2 > top:
            buckets[col].append(line)
    # Prefer a densely populated single-line column. Multiline addresses otherwise
    # create spurious rows. Numeric/relationship columns make useful anchors.
    anchor = max(range(len(buckets)), key=lambda i: (
        sum(bool(re.fullmatch(r'[0-9\s]{8,}', l['raw_text'])) for l in buckets[i]), len(buckets[i])))
    groups = visual_rows(buckets[anchor])
    ys = [median((bounds(l)[1] + bounds(l)[3]) / 2 for l in group) for group in groups]
    if not ys:
        ys = [median((bounds(l)[1] + bounds(l)[3]) / 2 for l in g)
              for g in visual_rows([l for l in lines if (bounds(l)[1] + bounds(l)[3]) / 2 > top])]
    row_edges = [top] + [(a + b) / 2 for a, b in zip(ys, ys[1:])] + [height]
    return dict(page_index=page['index'], x_edges=edges, y_edges=[round(y, 2) for y in row_edges][:301],
                columns=columns, revision=0, overrides={}, history=[],
                suggestion='Detected rules and a populated column. Check every boundary; blank and ditto cells are not filled automatically.')


def validate_value(value, kind):
    if not value.strip():
        return 'Missing value' if kind != 'text' else None
    stripped = value.strip()
    if len(stripped) <= 4 and (re.fullmatch(r'["\u201c\u201d\u2033\u3003\u0027\s]+', stripped)
                              or re.fullmatch(r'(?:[|!1lI]\s*){2,}', stripped)):
        return 'Possible ditto mark: verify from the source; not filled automatically'
    count = {'phone': 10, 'aadhaar': 12, 'pashu_aadhaar': 12}.get(kind)
    if count and not re.fullmatch(rf'[0-9]{{{count}}}', re.sub(r'\s', '', value)):
        return f'Expected {count} digits (spaces allowed). Value left unchanged.'
    return None


def materialize(table, lines):
    xs, ys = table['x_edges'], table['y_edges']
    buckets = [[[] for _ in table['columns']] for _ in range(len(ys) - 1)]
    unassigned = []
    for line in lines:
        if line['page_index'] != table['page_index']:
            continue
        x0, y0, x1, y1 = bounds(line)
        c = bisect.bisect_right(xs, (x0 + x1) / 2) - 1
        r = bisect.bisect_right(ys, (y0 + y1) / 2) - 1
        if 0 <= r < len(buckets) and 0 <= c < len(table['columns']):
            buckets[r][c].append(line)
        else:
            unassigned.append(line['id'])
    rows = []
    for r, row in enumerate(buckets):
        cells = []
        for c, source in enumerate(row):
            source = [l for g in visual_rows(source) for l in g]
            raw = '\n'.join(l['raw_text'] for l in source)
            current = '\n'.join(l['corrected_text'] if l['corrected_text'] is not None else l['raw_text'] for l in source)
            override = table.get('overrides', {}).get(f'{r}:{c}', {})
            text = override.get('text', current)
            warnings = []
            validation = validate_value(text, table['columns'][c]['kind'])
            if validation:
                warnings.append(validation)
            if any(l['confidence'] < .8 for l in source):
                warnings.append('Low OCR confidence')
            if any((max(0, min(bounds(l)[2], xs[c + 1]) - max(bounds(l)[0], xs[c])) /
                    max(1, bounds(l)[2] - bounds(l)[0])) < .65 for l in source):
                warnings.append('Text crosses a column boundary; check mapping')
            if any(min(abs((bounds(l)[1] + bounds(l)[3]) / 2 - ys[r]),
                           abs(ys[r + 1] - (bounds(l)[1] + bounds(l)[3]) / 2)) <
                   (bounds(l)[3] - bounds(l)[1]) * .25 for l in source):
                warnings.append('Text is near a row boundary; check mapping')
            cells.append(dict(row=r, column=c, text=text, raw_text=raw,
                corrected_text=override.get('text'), reviewed=override.get('reviewed', False),
                source_ids=[l['id'] for l in source], confidence=min((l['confidence'] for l in source), default=None),
                polygon=[[xs[c], ys[r]], [xs[c + 1], ys[r]], [xs[c + 1], ys[r + 1]], [xs[c], ys[r + 1]]],
                warnings=warnings))
        rows.append(cells)
    return {**table, 'rows': rows, 'unassigned_ids': unassigned}

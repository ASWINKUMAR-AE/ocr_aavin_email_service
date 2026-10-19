"""Group text by visual baseline without changing OCR text or stable region IDs."""
from statistics import median


def bounds(line):
    points = line['polygon']
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def visual_rows(lines):
    if not lines:
        return []
    height = median(max(1, bounds(line)[3] - bounds(line)[1]) for line in lines)
    groups = []
    for line in sorted(lines, key=lambda l: (sum(p[1] for p in l['polygon']) / 4, bounds(l)[0])):
        y = sum(p[1] for p in line['polygon']) / 4
        if groups and abs(y - median(sum(p[1] for p in item['polygon']) / 4 for item in groups[-1])) <= height * .55:
            groups[-1].append(line)
        else:
            groups.append([line])
    return [sorted(group, key=lambda l: bounds(l)[0]) for group in groups]


def order_document(doc):
    ordered = []
    for page in doc.get('pages', []):
        order = 0
        for row_index, group in enumerate(visual_rows([l for l in doc['lines'] if l['page_index'] == page['index']])):
            for line in group:
                line.update(reading_order=order, row_index=row_index)
                ordered.append(line)
                order += 1
    doc['lines'] = ordered
    return doc


def text_for_page(lines):
    return '\n'.join('\t'.join(l['corrected_text'] if l['corrected_text'] is not None else l['raw_text']
                               for l in group) for group in visual_rows(lines))

export async function request(path, options) {
  const response = await fetch(`/api${path}`, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(typeof body.detail === 'string' ? body.detail : `Request failed (${response.status})`);
  }
  return response.json();
}
export const effectiveText = line => line.corrected_text ?? line.raw_text;

export function rowText(lines) {
  const rows = new Map();
  lines.forEach(line => {
    const key = line.row_index ?? line.reading_order;
    if (!rows.has(key)) rows.set(key, []);
    rows.get(key).push(effectiveText(line));
  });
  return [...rows.values()].map(row => row.join('\t')).join('\n');
}


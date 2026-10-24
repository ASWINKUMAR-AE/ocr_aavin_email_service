import { useEffect, useRef, useState } from 'react';
import { ArrowLeft, Check, Download, FileSpreadsheet, LoaderCircle, Table2, ZoomIn, ZoomOut, Columns, Eye, SplitSquareVertical } from 'lucide-react';
import { request } from './api';

const farmerColumns = [
  ['S.No.', 'text'], ['Farmer Name', 'text'], ['Farmer Aadhaar No.', 'aadhaar'], ['Share No.', 'text'],
  ['Share Aadhaar No.', 'aadhaar'], ['Relationship', 'text'], ['Address', 'text'], ['Phone No.', 'phone'],
].map(([name, kind]) => ({name, kind}));

export const parseEdges = value => value.split(',').map(s => s.trim()).filter(Boolean).map(Number);
const increasing = values => values.length >= 2 && values.every((v, i) => Number.isFinite(v) && v >= 0 && (!i || v - values[i - 1] >= 1));

export const getColLetter = i => {
  let letter = '';
  let temp = i + 1;
  while (temp > 0) {
    let mod = (temp - 1) % 26;
    letter = String.fromCharCode(65 + mod) + letter;
    temp = Math.floor((temp - mod) / 26);
  }
  return letter;
};

export function CellEditor({cell, column, history, busy, onSave, onDirty}) {
  const [text, setText] = useState(cell.text);
  const [reviewed, setReviewed] = useState(cell.reviewed);
  const dirty = text !== cell.text || reviewed !== cell.reviewed;
  useEffect(() => { setText(cell.text); setReviewed(cell.reviewed); }, [cell.text, cell.reviewed]);
  useEffect(() => { onDirty(dirty); }, [dirty, onDirty]);
  return <div className="cell-editor"><h3>Row {cell.row + 1} · {column.name}</h3>
    <label>Corrected cell<textarea aria-label="Cell text" value={text} onChange={e => setText(e.target.value)} rows={3}/></label>
    <div className="cell-save"><label><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)}/> Verified against image</label><button className="primary" disabled={busy || !dirty} onClick={() => onSave(text, reviewed)}><Check size={14}/>{busy ? 'Saving…' : 'Save cell'}</button></div>
    {cell.warnings.map(warning => <p className="cell-warning" key={warning}>{warning}</p>)}
    <details open><summary>Original OCR · {cell.source_ids.length} regions</summary><pre>{cell.raw_text || '(No text detected in this cell)'}</pre><small>Cell corrections do not overwrite the original OCR or the line editor.</small></details>
    {!!history.length && <details><summary>Cell correction history ({history.length})</summary>{history.map((h, i) => <p className="history" key={i}>{new Date(h.at).toLocaleString()}: {h.before || '(blank)'} → {h.after || '(blank)'}</p>)}</details>}
  </div>;
}

export default function TableWorkspace({doc, pageIndex, onBack, onPendingChange}) {
  const [table, setTable] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState([0, 0]);
  const [xs, setXs] = useState('');
  const [ys, setYs] = useState('');
  const [columns, setColumns] = useState([]);
  const [mode, setMode] = useState('inspect');
  const [viewTab, setViewTab] = useState('spreadsheet'); // 'spreadsheet' | 'split'
  const [reset, setReset] = useState(false);
  const [dirtyCell, setDirtyCell] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [filter, setFilter] = useState('');
  const [formulaValue, setFormulaValue] = useState('');
  const svgRef = useRef(null);
  const imageScrollRef = useRef(null);
  const tableRef = useRef(null);
  const page = doc.pages[pageIndex];
  const root = `/documents/${doc.id}/tables/${pageIndex}`;

  function adopt(next) {
    setTable(next); setXs(next.x_edges.join(', ')); setYs(next.y_edges.join(', ')); setColumns(next.columns);
    setSelected([0, 0]); setReset(false); setDirtyCell(false);
    if (next.rows?.[0]?.[0]) {
      setFormulaValue(next.rows[0][0].text);
    }
  }

  useEffect(() => {
    let cancelled = false;
    setTable(null); setError('');
    request(root).then(next => { if (!cancelled) adopt(next); }).catch(e => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [root]);

  useEffect(() => {
    if (!dirtyCell) return;
    const warn = e => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirtyCell]);

  const xEdges = parseEdges(xs), yEdges = parseEdges(ys);
  const valid = increasing(xEdges) && increasing(yEdges) && xEdges.at(-1) <= page.width && yEdges.at(-1) <= page.height && xEdges.length <= 31 && yEdges.length <= 301;
  const layoutDirty = table && (JSON.stringify(xEdges) !== JSON.stringify(table.x_edges) || JSON.stringify(yEdges) !== JSON.stringify(table.y_edges) || JSON.stringify(columns) !== JSON.stringify(table.columns));

  useEffect(() => {
    onPendingChange?.(dirtyCell || !!layoutDirty);
    return () => onPendingChange?.(false);
  }, [dirtyCell, layoutDirty, onPendingChange]);

  const activeCell = table?.rows[selected[0]]?.[selected[1]];
  useEffect(() => {
    if (activeCell) {
      setFormulaValue(activeCell.text);
    }
  }, [selected, activeCell]);

  function canLeave() { return !dirtyCell || window.confirm('This cell has unsaved changes. Discard them?'); }

  function choose(r, c) {
    if (busy || !canLeave()) return;
    setDirtyCell(false); setSelected([r, c]);
    const viewport = imageScrollRef.current;
    const region = table.rows[r]?.[c]?.polygon;
    if (viewport?.clientWidth && svgRef.current && region) {
      const ratio = svgRef.current.getBoundingClientRect().width / page.width;
      const left = region[0][0] * ratio, top = region[0][1] * ratio;
      const right = region[2][0] * ratio, bottom = region[2][1] * ratio;
      if (top < viewport.scrollTop || bottom > viewport.scrollTop + viewport.clientHeight)
        viewport.scrollTop = Math.max(0, top - viewport.clientHeight / 3);
      if (left < viewport.scrollLeft || right > viewport.scrollLeft + viewport.clientWidth)
        viewport.scrollLeft = Math.max(0, left - viewport.clientWidth / 3);
    }
  }

  function handleKeyDown(e) {
    if (!table || !table.rows.length) return;
    const [r, c] = selected;
    const maxR = table.rows.length - 1;
    const maxC = table.columns.length - 1;
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

    if (e.key === 'ArrowUp' && r > 0) { e.preventDefault(); choose(r - 1, c); }
    else if (e.key === 'ArrowDown' && r < maxR) { e.preventDefault(); choose(r + 1, c); }
    else if (e.key === 'ArrowLeft' && c > 0) { e.preventDefault(); choose(r, c - 1); }
    else if (e.key === 'ArrowRight' && c < maxC) { e.preventDefault(); choose(r, c + 1); }
  }

  async function applyLayout() {
    if (!valid || !canLeave()) return;
    setBusy(true); setError('');
    const mapped = Array.from({length:xEdges.length - 1}, (_, i) => columns[i] ?? {name:`Column ${i + 1}`,kind:'text'});
    try {
      const next = await request(root, {method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({x_edges:xEdges, y_edges:yEdges, columns:mapped, expected_revision:table.revision, reset_edits:reset})});
      adopt(next);
      return next;
    }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function saveCell(text, reviewed) {
    setBusy(true); setError('');
    try {
      const next = await request(`${root}/cells/${selected[0]}/${selected[1]}`, {method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,reviewed,expected_revision:table.revision})});
      setTable(next); setDirtyCell(false);
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }

  async function saveFormulaBar() {
    if (!activeCell || formulaValue === activeCell.text) return;
    await saveCell(formulaValue, activeCell.reviewed);
  }

  async function handleDownloadExcel() {
    if (table.revision === 0 || layoutDirty) {
      const saved = await applyLayout();
      if (saved) {
        window.location.href = `/api${root}/export/xlsx`;
      }
    } else {
      window.location.href = `/api${root}/export/xlsx`;
    }
  }

  async function reload() {
    if (!canLeave() || (layoutDirty && !window.confirm('Discard layout changes and reload the saved table?'))) return;
    setBusy(true); setError('');
    try { adopt(await request(root)); } catch(e) { setError(e.message); } finally { setBusy(false); }
  }

  function addBoundary(event) {
    if (mode === 'inspect' || busy) return;
    const rect = svgRef.current.getBoundingClientRect();
    const isX = mode === 'columns';
    const value = Math.round(isX ? (event.clientX - rect.left) / rect.width * page.width : (event.clientY - rect.top) / rect.height * page.height);
    const edges = isX ? xEdges : yEdges;
    if (edges.some(v => Math.abs(v - value) < 2)) return;
    const next = [...edges, value].sort((a, b) => a - b);
    (isX ? setXs : setYs)(next.join(', '));
  }

  if (!table) return <section className="table-workspace"><button onClick={onBack}><ArrowLeft size={16}/> Back to lines</button>{error ? <p role="alert">{error}</p> : <p role="status"><LoaderCircle className="spin" size={18}/> Finding table boundaries…</p>}</section>;

  const cell = table.rows[selected[0]]?.[selected[1]];
  const canExport = table.revision > 0 && !layoutDirty;
  const previewXs = valid ? xEdges : table.x_edges, previewYs = valid ? yEdges : table.y_edges;
  const warningCount = table.rows.flat().filter(c => c.warnings.length).length;
  const activeCellCoord = `${getColLetter(selected[1])}${selected[0] + 1}`;

  return <section className="table-workspace excel-workspace" onKeyDown={handleKeyDown} tabIndex={0}>
    {/* Excel Header & Action Bar */}
    <div className="table-heading">
      <div className="heading-left">
        <button className="back-btn" onClick={() => { if (canLeave() && (!layoutDirty || window.confirm('Discard unsaved layout changes?'))) onBack(); }}>
          <ArrowLeft size={16}/> Back to lines
        </button>
        <h2>
          <FileSpreadsheet size={24} className="excel-brand-icon"/> 
          <span>Excel Spreadsheet View</span>
          <span className="table-badge">{table.rows.length} rows × {table.columns.length} columns</span>
        </h2>
      </div>
      <div className="heading-right">
        {/* View Mode Toggle */}
        <div className="excel-view-toggle">
          <button className={viewTab === 'spreadsheet' ? 'active' : ''} onClick={() => setViewTab('spreadsheet')}>
            <Table2 size={15}/> Spreadsheet
          </button>
          <button className={viewTab === 'split' ? 'active' : ''} onClick={() => setViewTab('split')}>
            <SplitSquareVertical size={15}/> Split View
          </button>
        </div>
        {/* Prominent Download Excel Button */}
        <button className="excel-primary-download" onClick={handleDownloadExcel} disabled={busy || !valid}>
          <FileSpreadsheet size={16}/>
          <strong>Download Excel (.xlsx)</strong>
        </button>
        <button className="secondary-btn" disabled={busy} onClick={reload}>Reload</button>
      </div>
    </div>

    {error && <div className="error-banner" role="alert">{error}</div>}

    {/* Excel Formula Bar */}
    <div className="excel-formula-bar">
      <div className="formula-cell-badge" title="Active Cell">
        {activeCellCoord}
      </div>
      <div className="formula-col-name" title="Column Name">
        {table.columns[selected[1]]?.name}
      </div>
      <div className="formula-fx" aria-hidden="true">fx</div>
      <input 
        className="formula-input"
        type="text"
        aria-label="Cell Formula Value"
        value={formulaValue}
        onChange={e => setFormulaValue(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter') saveFormulaBar(); }}
        placeholder="Select a cell or type to edit…"
      />
      {cell && table.revision > 0 && formulaValue !== cell.text && (
        <button className="formula-save-btn" onClick={saveFormulaBar} disabled={busy}>
          <Check size={13}/> Save
        </button>
      )}
    </div>

    {/* Split View with Image Source (when Split View is active) */}
    {viewTab === 'split' && (
      <div className="table-inspector">
        <section className="table-source">
          <div className="panel-heading">
            <label>Image action 
              <select aria-label="Image action" value={mode} onChange={e => setMode(e.target.value)}>
                <option value="inspect">Inspect cells</option>
                <option value="columns">Click to add column boundary</option>
                <option value="rows">Click to add row boundary</option>
              </select>
            </label>
            <div className="zoom">
              <button aria-label="Zoom table source out" onClick={() => setZoom(Math.max(75, zoom - 25))}><ZoomOut size={16}/></button>
              <span>{zoom}%</span>
              <button aria-label="Zoom table source in" onClick={() => setZoom(Math.min(300, zoom + 25))}><ZoomIn size={16}/></button>
            </div>
          </div>
          <div className="table-image-scroll" ref={imageScrollRef}>
            <div className="table-image" style={{width:`${zoom}%`}}>
              <img alt="Table source with row and column boundaries" src={`/api/documents/${doc.id}/pages/${pageIndex}`}/>
              <svg ref={svgRef} viewBox={`0 0 ${page.width} ${page.height}`} onClick={addBoundary} aria-label="Table grid preview">
                {cell && mode === 'inspect' && !layoutDirty && <polygon points={cell.polygon.map(p => p.join(',')).join(' ')} className="table-selected-region"/>}
                {previewXs.map((x, i) => <line key={`x${i}`} x1={x} x2={x} y1={previewYs[0]} y2={previewYs.at(-1)} className="table-grid-line"/>)}
                {previewYs.map((y, i) => <line key={`y${i}`} x1={previewXs[0]} x2={previewXs.at(-1)} y1={y} y2={y} className="table-grid-line"/>)}
                {mode === 'inspect' && !layoutDirty && table.rows.flat().map(c => <polygon key={`${c.row}:${c.column}`} points={c.polygon.map(p => p.join(',')).join(' ')} className="table-cell-hit" onClick={() => choose(c.row,c.column)}><title>Row {c.row + 1}, {table.columns[c.column].name}</title></polygon>)}
              </svg>
            </div>
          </div>
          <p className="table-caption">Select a table cell to locate it in the source image.</p>
        </section>
        <aside className="table-cell-panel">
          {cell && table.revision > 0 ? (
            <CellEditor key={`${selected[0]}:${selected[1]}`} cell={cell} column={table.columns[selected[1]]} history={table.history.filter(h => h.action === 'cell' && h.row === selected[0] && h.column === selected[1])} busy={busy || layoutDirty} onSave={saveCell} onDirty={setDirtyCell}/>
          ) : (
            <div className="empty-results">
              <Table2 size={30}/>
              <h3>Cell Inspector</h3>
              <p>Save the layout below to enable cell review history and verification tracking.</p>
              {table.revision === 0 && (
                <button className="primary" onClick={applyLayout} disabled={busy || !valid}>
                  Save table layout
                </button>
              )}
            </div>
          )}
        </aside>
      </div>
    )}

    {/* Excel Controls Bar */}
    <div className="table-controls excel-table-controls">
      <div className="controls-left">
        <label>Find in spreadsheet <input aria-label="Find in table" placeholder="Search cell text…" value={filter} onChange={e => setFilter(e.target.value)}/></label>
        <span className="review-stats">{table.rows.flat().filter(c => c.reviewed).length} of {table.rows.flat().length} cells reviewed</span>
      </div>
      <div className="table-downloads">
        <span className="export-label"><Download size={14}/> Formats:</span>
        {['xlsx','csv','json','txt'].map(format => (
          <a key={format} aria-disabled={!canExport} href={canExport ? `/api${root}/export/${format}` : undefined}>
            {format.toUpperCase()}
          </a>
        ))}
      </div>
    </div>

    {/* The Excel Spreadsheet Table */}
    <div className="table-scroll excel-scroll-wrapper" ref={tableRef}>
      <table className="data-table excel-grid-table">
        <caption className="sr-only">Extracted table for page {pageIndex + 1}</caption>
        <thead>
          <tr className="excel-col-letter-row">
            <th className="excel-corner-cell"></th>
            {table.columns.map((c, i) => (
              <th key={i} className="excel-col-letter" scope="col">
                <span className="col-letter">{getColLetter(i)}</span>
              </th>
            ))}
          </tr>
          <tr className="excel-header-row">
            <th scope="col" className="excel-row-num-header">#</th>
            {table.columns.map((c, i) => (
              <th key={i} scope="col" className="excel-header-cell">
                <div className="header-title">{c.name}</div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {table.rows.map((row, r) => {
            const matchesFilter = !filter || row.some(c => c.text.toLowerCase().includes(filter.toLowerCase()));
            if (!matchesFilter) return null;
            const isTotalRow = row.some(c => /total|grand|net|summary/i.test(c.text));
            return (
              <tr key={r} className={`excel-data-row ${isTotalRow ? 'excel-total-row' : ''}`}>
                <th scope="row" className="excel-row-num">{r + 1}</th>
                {row.map((c, i) => {
                  const isSelected = selected[0] === r && selected[1] === i;
                  return (
                    <td 
                      key={i} 
                      className={`excel-cell ${c.warnings.length ? 'needs-review' : ''} ${isSelected ? 'active-cell' : ''} ${isTotalRow ? 'total-cell' : ''}`}
                      onClick={() => choose(r, i)}
                    >
                      <button 
                        onClick={() => choose(r, i)} 
                        aria-label={`Row ${r+1}, ${table.columns[i].name}${c.warnings.length ? ', needs review' : ''}`}
                        className="excel-cell-btn"
                      >
                        <span className="cell-content">{c.text || ' '}</span>
                        {c.reviewed ? <small className="cell-reviewed-tag">✓</small> : c.warnings.length ? <small className="cell-warn-tag">⚠</small> : null}
                      </button>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>

    {/* Layout settings & boundary adjustment */}
    <details className="layout-settings excel-layout-settings" open={table.revision === 0 ? true : undefined}>
      <summary>Adjust rows, columns & field types {layoutDirty && '· Unsaved layout changes'}</summary>
      <p>Boundaries are source-image pixels, including outer edges. Edit values here or click the image in Split View. Rebuilding archives the old grid.</p>
      <div className="edge-inputs">
        <label>Column boundaries (left → right)<input aria-label="Column boundaries" value={xs} onChange={e => setXs(e.target.value)}/></label>
        <label>Row boundaries (top → bottom)<textarea aria-label="Row boundaries" value={ys} onChange={e => setYs(e.target.value)} rows={2}/></label>
      </div>
      <div className="column-preset">
        <strong>Column mapping</strong>
        <button disabled={xEdges.length !== 9} onClick={() => setColumns(farmerColumns.map(c => ({...c})))}>Use farmer register columns</button>
      </div>
      <div className="column-mapping">
        {Array.from({length:Math.min(30, Math.max(0,xEdges.length - 1))}, (_, i) => (
          <div key={i}>
            <label>Column {i + 1} ({getColLetter(i)})
              <input aria-label={`Column ${i + 1} name`} maxLength={80} value={columns[i]?.name ?? `Column ${i + 1}`} onChange={e => setColumns(old => Array.from({length:xEdges.length - 1}, (_, j) => j === i ? {...(old[j] ?? {kind:'text'}),name:e.target.value} : old[j] ?? {name:`Column ${j+1}`,kind:'text'}))}/>
            </label>
            <select aria-label={`Column ${i + 1} validation`} value={columns[i]?.kind ?? 'text'} onChange={e => setColumns(old => Array.from({length:xEdges.length - 1}, (_, j) => j === i ? {...(old[j] ?? {name:`Column ${j+1}`}),kind:e.target.value} : old[j] ?? {name:`Column ${j+1}`,kind:'text'}))}>
              <option value="text">Free text</option>
              <option value="phone">Phone · 10 digits</option>
              <option value="aadhaar">Aadhaar · 12 digits</option>
              <option value="pashu_aadhaar">Pashu Aadhaar · 12 digits</option>
            </select>
          </div>
        ))}
      </div>
      {!!Object.keys(table.overrides).length && (
        <label className="reset-edits">
          <input type="checkbox" checked={reset} onChange={e => setReset(e.target.checked)}/> Clear existing cell edits when rebuilding
        </label>
      )}
      <div className="layout-actions">
        <button className="primary" onClick={applyLayout} disabled={busy || !valid || columns.some(c => !c.name.trim()) || (Object.keys(table.overrides).length > 0 && !reset)}>
          {busy ? 'Saving…' : table.revision ? 'Rebuild table layout' : 'Save table layout'}
        </button>
        {!valid && <span className="cell-warning"> Enter increasing boundaries within {page.width} × {page.height} pixels.</span>}
      </div>
    </details>
  </section>;
}

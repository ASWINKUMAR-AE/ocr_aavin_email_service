import { useEffect, useRef, useState } from 'react';
import { ScanLine, Upload, FileText, ShieldCheck, Sun, Moon, Search, ZoomIn, ZoomOut, Check, Download, Layers, ArrowUpRight, X, LoaderCircle } from 'lucide-react';
import { request, effectiveText } from './api';
import TableWorkspace from './TableWorkspace';
import AavinReportWorkspace from './AavinReportWorkspace';

export function LineEditor({ line, selected, onSelect, onSave, history }) {
  const [text, setText] = useState(effectiveText(line));
  const [reviewed, setReviewed] = useState(line.reviewed);
  const [busy, setBusy] = useState(false);
  const dirty = text !== effectiveText(line) || reviewed !== line.reviewed;
  useEffect(() => { setText(effectiveText(line)); setReviewed(line.reviewed); }, [line.id, line.raw_text, line.corrected_text, line.reviewed]);
  return <article id={`line-${line.id}`} className={`line-card ${selected ? 'selected' : ''}`} onMouseEnter={onSelect}>
    <div className="line-meta"><button className="line-number" onClick={onSelect}>LINE {String(line.reading_order + 1).padStart(2, '0')}</button><span className={line.confidence < .8 ? 'confidence low' : 'confidence'}>{Math.round(line.confidence * 100)}% confidence</span></div>
    <label className="sr-only" htmlFor={`edit-${line.id}`}>Correct line {line.reading_order + 1}</label>
    <textarea id={`edit-${line.id}`} value={text} onFocus={onSelect} onChange={e => setText(e.target.value)} />
    <details><summary>Original text & history</summary><p className="raw">{line.raw_text || '(empty)'}</p>{history.map((h, i) => <p className="history" key={i}>{new Date(h.at).toLocaleString()}: {h.before ?? line.raw_text} → {h.after} · {h.reviewed ? 'reviewed' : 'unreviewed'}</p>)}</details>
    <div className="line-footer"><label><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} /> Reviewed</label><button disabled={!dirty || busy} onClick={async () => { setBusy(true); try { await onSave(text, reviewed); } finally { setBusy(false); } }}>{busy ? 'Saving…' : dirty ? 'Save changes' : <><Check size={13} /> Saved</>}</button></div>
  </article>;
}

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [doc, setDoc] = useState(null);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState('');
  const [uploading, setUploading] = useState(false);
  const [health, setHealth] = useState(null);
  const [query, setQuery] = useState('');
  const [zoom, setZoom] = useState(100);
  const [tab, setTab] = useState('lines');
  const [tableDirty, setTableDirty] = useState(false);
  const [dark, setDark] = useState(localStorage.getItem('ocr-theme') === 'dark');
  const fileRef = useRef(null);
  const viewport = useRef(null);
  const activeId = useRef(null);
  const processing = uploading || ['queued', 'processing'].includes(doc?.status);
  useEffect(() => { document.documentElement.dataset.theme = dark ? 'dark' : 'light'; localStorage.setItem('ocr-theme', dark ? 'dark' : 'light'); }, [dark]);
  useEffect(() => { Promise.all([request('/health'), request('/documents')]).then(([h, d]) => { setHealth(h); setDocuments(d); }).catch(e => setError(`Backend unavailable. ${e.message}`)); }, []);
  useEffect(() => {
    if (!doc || !['queued', 'processing'].includes(doc.status)) return;
    const id = doc.id;
    const timer = setInterval(() => request(`/documents/${id}`).then(next => {
      if (activeId.current !== id) return;
      setDoc(next); setDocuments(old => old.map(d => d.id === id ? {...d, status: next.status} : d));
    }).catch(e => setError(e.message)), 1500);
    return () => clearInterval(timer);
  }, [doc?.id, doc?.status]);
  async function openDocument(id) {
    if (tableDirty && !window.confirm('Discard unsaved table changes and open another document?')) return;
    activeId.current = id;
    try { const next = await request(`/documents/${id}`); if (activeId.current === id) { setDoc(next); setPage(0); setSelected(null); setZoom(100); setError(''); } } catch (e) { setError(e.message); }
  }
  async function upload(file) {
    if (!file || processing) return;
    if (tableDirty && !window.confirm('Discard unsaved table changes and upload another document?')) return;
    setError('');
    if (file.size > (health?.max_upload_mb ?? 25) * 1024 * 1024) { setError('File exceeds the upload size limit.'); return; }
    setUploading(true);
    const body = new FormData(); body.append('file', file);
    try { const next = await request('/documents', {method: 'POST', body}); activeId.current = next.id; setDoc(next); setDocuments(old => [next, ...old]); setPage(0); setSelected(null); } catch (e) { setError(e.message); } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ''; }
  }
  async function save(line, text, reviewed) {
    const id = doc.id;
    try { const next = await request(`/documents/${id}/lines/${line.id}`, {method: 'PATCH', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({text, reviewed})}); if (activeId.current === id) setDoc(next); } catch (e) { setError(e.message); }
  }
  const currentPage = doc?.pages[page];
  const pageLines = doc?.lines.filter(l => l.page_index === page) ?? [];
  const filtered = pageLines.filter(l => effectiveText(l).toLowerCase().includes(query.toLowerCase()));
  function selectLine(id, scroll = false) { setSelected(id); if (scroll) document.getElementById(`line-${id}`)?.scrollIntoView({behavior: 'smooth', block: 'nearest'}); }
  return <div className="app-shell">
    <aside className="sidebar"><a className="brand" href="/"><span className="brand-mark"><ScanLine size={24} /></span><span>பதிவு<span className="brand-sub">BILINGUAL OCR STUDIO</span></span></a>
      <div className="workspace-label">YOUR WORKSPACE</div><button className="nav-active"><Layers size={18} /> Document studio <span className="nav-dot" /></button>
      <div className="recent-title">RECENT DOCUMENTS <span>{documents.length}</span></div>
      <div className="document-list">{documents.length ? documents.map(d => <button key={d.id} onClick={() => openDocument(d.id)} className={doc?.id === d.id ? 'document-item active' : 'document-item'}><FileText size={17} /><span><strong>{d.name}</strong><small>{d.status}</small></span></button>) : <p className="muted sidebar-empty">Your documents will appear here. Everything stays on this device.</p>}</div>
      <div className="local-card"><ShieldCheck size={21} /><strong>Private by design</strong><p>Local processing. No cloud uploads. Your pages stay yours.</p><span><i /> CPU · Tamil + English</span></div>
    </aside>
    <main><header><div className="breadcrumb">Workspace <span>/</span> <strong>Document studio</strong></div><div className="header-actions"><span className="local-pill"><i /> Local workspace</span><button className="icon-button" aria-label="Toggle color theme" onClick={() => setDark(!dark)}>{dark ? <Sun size={19} /> : <Moon size={19} />}</button></div></header>
      <div className="main-content"><div className="page-heading"><div><div className="eyebrow">FROM NOTEBOOK TO EDITABLE TEXT</div><h1>A clearer way to read your pages.</h1><p>Extract Tamil & English text, check every line, and make it yours.</p></div><button className="primary" disabled={processing} onClick={() => fileRef.current.click()}><Upload size={17} /> {uploading ? 'Uploading…' : 'Upload document'}</button></div>
        <input ref={fileRef} type="file" accept=".png,.jpg,.jpeg,.pdf" aria-label="Upload document file" className="sr-only" onChange={e => upload(e.target.files[0])} />
        {error && <div className="error-banner" role="alert">{error}<button aria-label="Dismiss error" onClick={() => setError('')}><X size={17}/></button></div>}
        <div className="workflow"><span className={doc ? 'done' : 'current'}><b>01</b> Upload your page</span><i /><span className={processing ? 'current' : doc?.status === 'complete' ? 'done' : ''}><b>02</b> Extract text</span><i /><span className={doc?.status === 'complete' ? 'current' : ''}><b>03</b> Review & export</span><div className="language-tag">தமிழ் <span>+</span> English</div></div>
        {!doc ? <section className="welcome"><div className="upload-zone" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); upload(e.dataTransfer.files[0]); }}><div className="paper-art" aria-hidden="true"><span>அ</span><div/><div/><div/><small>Aa 123</small><ScanLine size={28}/></div><h2>Give your handwriting a digital home.</h2><p>Drop a notebook photo or a PDF here.<br/>We’ll find the text. You give it the final check.</p><button className="primary" disabled={processing} onClick={() => fileRef.current.click()}><Upload size={17}/> Choose a document</button><small>PNG, JPG or PDF · up to {health?.max_upload_mb ?? 25} MB · {health?.max_pages ?? 10} pages</small></div><div className="welcome-note"><ShieldCheck size={18}/><span><strong>Your handwriting, your words.</strong> Recognition can make mistakes. Always review names and numbers before exporting.</span></div></section> : <>
          <div className="document-toolbar"><div><FileText size={19}/><strong>{doc.name}</strong><span className="status" role="status">{processing && <LoaderCircle size={14} className="spin"/>}{doc.status} {doc.status === 'processing' && `· ${doc.completed_pages}/${doc.pages.length}`}</span></div><div>{doc.processing_seconds != null && <small>{doc.processing_seconds}s</small>}<label className="page-select">Page <select value={page} onChange={e => { if (tableDirty && !window.confirm('Discard unsaved table changes and switch pages?')) return; setPage(Number(e.target.value)); setSelected(null); }}>{doc.pages.map(p => <option key={p.index} value={p.index}>{p.index + 1} of {doc.pages.length}</option>)}</select></label></div></div>
          {doc.error && <div className="error-banner" role="alert">{doc.error}</div>}{doc.warning && <div className="notice">{doc.warning}</div>}
          {tab === 'table' && doc.status === 'complete' ? <TableWorkspace key={`${doc.id}:${page}`} doc={doc} pageIndex={page} onBack={() => setTab('lines')} onPendingChange={setTableDirty}/> : tab === 'aavin' && doc.status === 'complete' ? <AavinReportWorkspace key={doc.id} doc={doc} onBack={() => setTab('lines')} /> : <div className="studio"><section className="viewer-panel"><div className="panel-heading"><span><b>Source document</b><small>Click an outline to review its text</small></span><div className="zoom"><button aria-label="Zoom out" onClick={() => setZoom(Math.max(50, zoom - 25))}><ZoomOut size={17}/></button><button onClick={() => setZoom(100)} aria-label="Reset zoom">{zoom}%</button><button aria-label="Zoom in" onClick={() => setZoom(Math.min(300, zoom + 25))}><ZoomIn size={17}/></button></div></div>
            <div className="image-viewport" ref={viewport} onPointerDown={e => { if (e.target.closest('[data-region]')) return; const el = viewport.current; el.dataset.drag = `${e.clientX},${e.clientY},${el.scrollLeft},${el.scrollTop}`; el.setPointerCapture(e.pointerId); }} onPointerMove={e => { const el = viewport.current; if (!el.dataset.drag) return; const [x,y,left,top] = el.dataset.drag.split(',').map(Number); el.scrollLeft = left - e.clientX + x; el.scrollTop = top - e.clientY + y; }} onPointerUp={() => delete viewport.current.dataset.drag} onPointerCancel={() => delete viewport.current.dataset.drag}>
              {currentPage && <div className="image-sheet" style={{width: `${zoom}%`}}><img draggable="false" alt={`Source page ${page + 1}`} src={`/api/documents/${doc.id}/pages/${page}`}/><svg viewBox={`0 0 ${currentPage.width} ${currentPage.height}`} aria-label="Detected text regions">{pageLines.map(line => <polygon data-region="true" key={line.id} points={line.polygon.map(p => p.join(',')).join(' ')} className={selected === line.id ? 'region selected' : 'region'} onMouseEnter={() => selectLine(line.id)} onClick={() => { setTab('lines'); selectLine(line.id, true); }} tabIndex={0} role="button" aria-label={`Select line ${line.reading_order + 1}: ${line.raw_text}`} onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setTab('lines'); selectLine(line.id, true); } }} />)}</svg></div>}
            </div><div className="viewer-footer"><span><i/> {pageLines.length} detected lines</span><small>Drag to pan · Coordinates match the displayed source</small></div></section>
            <section className="results-panel"><div className="result-tabs"><button className={tab === 'lines' ? 'active' : ''} onClick={() => setTab('lines')}>Review lines <span>{pageLines.length}</span></button><button className={tab === 'text' ? 'active' : ''} onClick={() => setTab('text')}>Full text <ArrowUpRight size={14}/></button><button disabled={doc.status !== 'complete'} className={tab === 'table' ? 'active' : ''} onClick={() => setTab('table')}>Table view</button><button disabled={doc.status !== 'complete'} className={tab === 'aavin' ? 'active' : ''} onClick={() => setTab('aavin')}>Aavin Abstract</button></div>
              <div className="search"><Search size={16}/><input aria-label="Search extracted text" placeholder="Find a word or number…" value={query} onChange={e => setQuery(e.target.value)}/></div>
              <div className="review-note"><span className="amber-dot"/> Confidence is a guide. Verify every identifier.</div>
              <div className="lines">{processing ? <div className="empty-results"><LoaderCircle size={27} className="spin"/><h3>Reading your pages…</h3><p>The first run loads the local CPU models.</p></div> : tab === 'text' ? <pre className="full-text">{rowText(filtered) || 'No text on this page.'}</pre> : filtered.length ? filtered.map(line => <LineEditor key={`${doc.id}/${line.id}`} line={line} selected={selected === line.id} onSelect={() => selectLine(line.id)} onSave={(text, reviewed) => save(line, text, reviewed)} history={doc.history.filter(h => h.line_id === line.id)} />) : <div className="empty-results"><FileText size={28}/><h3>No extracted lines</h3><p>{query ? 'Try a different search.' : 'OCR results will appear here.'}</p></div>}</div>
              <div className="export-bar"><span><Download size={16}/> Export saved text</span><div>{['xlsx','csv','json','txt'].map(format => <a key={format} aria-disabled={doc.status !== 'complete'} href={doc.status === 'complete' ? `/api/documents/${doc.id}/export/${format}` : undefined}>{format.toUpperCase()}</a>)}</div></div>
            </section></div>}</>}
        <footer><span><ShieldCheck size={14}/> Processed on your device. Never uploaded to a cloud.</span><span>PP-OCRv5 · Human review first</span></footer>
      </div></main></div>;
}

export function rowText(lines) {
  const rows = new Map();
  lines.forEach(line => {
    const key = line.row_index ?? line.reading_order;
    if (!rows.has(key)) rows.set(key, []);
    rows.get(key).push(effectiveText(line));
  });
  return [...rows.values()].map(row => row.join('\t')).join('\n');
}

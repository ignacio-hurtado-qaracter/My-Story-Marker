// Biblioteca: lists every generated novel from data/books.json and shows its
// parameters, Spirit, characters, summaries, Reviewer metrics and the novel itself.
// Classic script (no ES module) so the page also works when opened via file://.
// `marked` comes from the UMD build loaded in library.html; the data comes from
// data/books.js (embedded) with data/books.json as a fallback over HTTP.

const grid = document.getElementById('books-grid');
const listNote = document.getElementById('list-note');
const listView = document.getElementById('list-view');
const detailView = document.getElementById('detail-view');

let books = [];

const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const md = (s) => (s ? marked.parse(s) : '');
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('es-ES', { year: 'numeric', month: 'short', day: 'numeric' }) : '—');

const STATUS = { complete: 'Completa', error: 'Detenida con error', running: 'En curso', unknown: 'Desconocido' };
const CHECKS = { main_thread: 'Hilo principal', current_chapter: 'Capítulo actual', characters: 'Personajes', pacing: 'Ritmo' };

// ---------- list ----------
async function load() {
  try {
    let data = window.__BOOKS__;
    if (!data) {
      const res = await fetch('data/books.json', { cache: 'no-store' });
      if (!res.ok) throw new Error(res.statusText);
      data = await res.json();
    }
    books = data.books ?? [];
    listNote.textContent = books.length
      ? `${books.length} novela(s) · datos generados ${fmtDate(data.generatedAt)}`
      : '';
    renderList();
    route();
  } catch (e) {
    grid.innerHTML = `<div class="empty-state card">
      <h3>No se encontraron los datos de la biblioteca</h3>
      <p>Genera el índice de la biblioteca desde la raíz del repo:</p>
      <pre style="display:inline-block;text-align:left"><code>node web/scripts/build-data.mjs</code></pre>
      <p class="small">Eso crea <code>web/data/books.js</code>, que esta página carga directamente.</p>
    </div>`;
    listNote.textContent = '';
  }
}

function renderList() {
  if (!books.length) {
    grid.innerHTML = `<div class="empty-state card">
      <h3>Todavía no hay novelas</h3>
      <p>Crea la primera desde <a href="index.html">Crear novela</a> y ejecuta el harness.</p></div>`;
    return;
  }
  grid.innerHTML = books
    .map(
      (b) => `<button class="card book-card" data-slug="${esc(b.slug)}">
        <div class="cover"><h3>${esc(b.title)}</h3></div>
        <div class="pills">
          <span class="pill ${b.status === 'complete' ? 'pass' : b.status === 'error' ? 'fail' : ''}">${esc(STATUS[b.status] ?? b.status)}</span>
          <span class="pill neutral">${esc(b.language ?? '—')}</span>
          <span class="pill neutral">${esc(b.model ?? '—')}</span>
        </div>
        <p class="premise">${esc(b.premise ?? 'Sin premisa registrada.')}</p>
        <p class="small muted" style="margin:0">${b.stats.chapters} capítulos · ${b.stats.words.toLocaleString('es-ES')} palabras · ${b.stats.verdicts} veredictos · ${fmtDate(b.updatedAt)}</p>
      </button>`
    )
    .join('');
  grid.querySelectorAll('.book-card').forEach((el) => el.addEventListener('click', () => (location.hash = el.dataset.slug)));
}

// ---------- routing ----------
function route() {
  const slug = decodeURIComponent(location.hash.slice(1));
  const book = books.find((b) => b.slug === slug);
  if (book) openDetail(book);
  else {
    detailView.classList.remove('open');
    listView.style.display = '';
  }
}
window.addEventListener('hashchange', route);
document.getElementById('back-link').addEventListener('click', (e) => { e.preventDefault(); location.hash = ''; });

// ---------- detail ----------
function openDetail(b) {
  listView.style.display = 'none';
  detailView.classList.add('open');
  window.scrollTo({ top: 0 });

  document.getElementById('d-status').textContent = STATUS[b.status] ?? b.status;
  document.getElementById('d-title').textContent = b.title;
  document.getElementById('d-premise').textContent = b.premise ?? '';
  document.getElementById('d-pills').innerHTML = [
    ['neutral', `Idioma · ${b.language ?? '—'}`],
    ['neutral', `Modelo · ${b.model ?? '—'}`],
    ['neutral', `${b.stats.chapters} capítulos`],
    ['neutral', `${b.stats.words.toLocaleString('es-ES')} palabras`],
    ['', `books/${b.slug}/`],
  ].map(([cls, t]) => `<span class="pill ${cls}">${esc(t)}</span>`).join('');

  panel('overview').innerHTML = renderOverview(b);
  panel('params').innerHTML = renderParams(b);
  panel('spirit').innerHTML = renderSpirit(b);
  panel('characters').innerHTML = renderCharacters(b);
  panel('summaries').innerHTML = renderSummaries(b);
  panel('metrics').innerHTML = renderMetrics(b);
  panel('novel').innerHTML = b.raw.novel
    ? `<article class="prose">${md(b.raw.novel)}</article>`
    : `<div class="empty-state">Esta ejecución no produjo <code>novel.md</code> (Spec1 §2.2: sólo se escribe al completar).</div>`;

  activateTab('overview');
}

const panel = (name) => document.querySelector(`[data-panel="${name}"]`);
function activateTab(name) {
  document.querySelectorAll('#tabs button').forEach((b) => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab-panel').forEach((p) => p.classList.toggle('active', p.dataset.panel === name));
}
document.querySelectorAll('#tabs button').forEach((b) => b.addEventListener('click', () => activateTab(b.dataset.tab)));

// ---------- renderers ----------
function renderOverview(b) {
  const mt = b.main_thread ?? {};
  const t = b.totals ?? {};
  return `
    <div class="grid-2">
      <div>
        <div class="card">
          <span class="eyebrow">Tono y estilo</span>
          <p>${esc(b.tone_and_style ?? '—')}</p>
        </div>
        <div class="card">
          <span class="eyebrow">Hilo principal</span>
          <h4>Introducción</h4><p>${esc(mt.introduction ?? '—')}</p>
          <h4>Desarrollo</h4><p>${esc(mt.development ?? '—')}</p>
          <h4>Resolución</h4><p style="margin:0">${esc(mt.resolution ?? '—')}</p>
        </div>
      </div>
      <div>
        <div class="card">
          <span class="eyebrow">Ejecución</span>
          <dl class="kv">
            <dt>Estado</dt><dd>${esc(b.status)}</dd>
            <dt>Posición</dt><dd>${esc(b.position?.note ?? '—')}</dd>
            <dt>Capítulos</dt><dd>${t.chapters ?? b.stats.chapters}</dd>
            <dt>Fragmentos aprobados</dt><dd>${t.fragments_approved ?? b.stats.approved}</dd>
            <dt>Rechazos</dt><dd>${t.rejections ?? b.stats.rejected}</dd>
            <dt>Fallos de fragmento</dt><dd>${t.fragment_failures ?? 0}</dd>
            <dt>Regeneraciones de capítulo</dt><dd>${t.chapter_regenerations ?? 0}</dd>
            <dt>Párrafos por capítulo</dt><dd>${(t.paragraphs_per_chapter ?? []).join(' · ') || '—'} <span class="muted">(objetivo ${t.target_paragraphs ?? '—'})</span></dd>
            <dt>Palabras</dt><dd>${b.stats.words.toLocaleString('es-ES')}</dd>
            <dt>Carpeta</dt><dd>books/${esc(b.slug)}/</dd>
            <dt>Actualizado</dt><dd>${fmtDate(b.updatedAt)}</dd>
          </dl>
        </div>
        <div class="card">
          <span class="eyebrow">Capítulos</span>
          <ol style="margin:0;padding-left:1.2rem">
            ${(b.chapters ?? b.chapterTitles.map((t) => ({ title: t }))).map((c) => `<li><strong>${esc(c.title)}</strong>${c.beats ? ` <span class="muted small">· ${c.beats.length} beats</span>` : ''}</li>`).join('')}
          </ol>
        </div>
      </div>
    </div>`;
}

function renderParams(b) {
  const c = b.config;
  if (!c) return `<div class="empty-state">No hay <code>run.json</code> con la configuración de esta ejecución.</div>`;
  const val = (v) => (v === null || v === undefined || v === '' ? `<dd class="empty">null (por defecto)</dd>` : `<dd>${esc(typeof v === 'object' ? JSON.stringify(v) : v)}</dd>`);
  const group = (title, entries) => `<div class="card"><h4>${title}</h4><dl class="kv">${entries.map(([k, v]) => `<dt>${k}</dt>${val(v)}`).join('')}</dl></div>`;
  return `
    <div class="params-grid">
      ${group('Historia', [['theme', c.theme], ['tone_and_style', c.tone_and_style], ['language', c.language], ['model', c.model]])}
      ${group('Capítulos', [['count', c.chapters?.count], ['target_paragraphs', c.chapters?.target_paragraphs]])}
      ${group('Fragmento', [['min_paragraphs', c.fragment?.min_paragraphs], ['max_paragraphs', c.fragment?.max_paragraphs]])}
      ${group('Contexto', [['recent_paragraphs', c.context?.recent_paragraphs], ['distant_chapters', c.context?.distant_chapters]])}
      ${group('Reintentos', [['max_fragment_retries', c.retries?.max_fragment_retries], ['max_fragment_failures_per_chapter', c.retries?.max_fragment_failures_per_chapter], ['max_chapter_regenerations', c.retries?.max_chapter_regenerations]])}
      ${group('Salida', Object.entries(c.output ?? {}))}
    </div>
    <div class="card" style="margin-top:1.5rem">
      <span class="eyebrow">config_snapshot (run.json)</span>
      <pre><code>${esc(JSON.stringify(c, null, 2))}</code></pre>
    </div>`;
}

function renderSpirit(b) {
  if (!b.chapters) return `<article class="prose">${md(b.raw.spirit ?? '_Sin spirit.md_')}</article>`;
  const beat = (bt) => `<li><code>${esc(bt.id)}</code> <span class="pill ${bt.status === 'done' ? 'pass' : 'neutral'}">${esc(bt.status)}</span><br>${esc(bt.description)}</li>`;
  return `
    <div class="card">
      <span class="eyebrow">Premisa</span>
      <p>${esc(b.premise ?? '—')}</p>
    </div>
    ${b.chapters.map((c) => `
      <div class="card">
        <span class="eyebrow">Capítulo ${c.id}</span>
        <h3>${esc(c.title)}</h3>
        <p class="small muted">Objetivo: ${c.target_paragraphs ?? '—'} párrafos · ${c.beats?.length ?? 0} beats</p>
        ${c.introduction ? `<h4>Introducción</h4><p>${esc(c.introduction)}</p>` : ''}
        <h4>Desarrollo</h4><p>${esc(c.development)}</p>
        <h4>Resolución</h4><p>${esc(c.resolution)}</p>
        <h4>Beats</h4>
        <ul style="padding-left:1.2rem">${(c.beats ?? []).map(beat).join('')}</ul>
      </div>`).join('')}
    <details class="card" style="margin-top:1.5rem">
      <summary style="cursor:pointer;font-weight:600">Ver spirit.md completo</summary>
      <article class="prose" style="margin-top:1rem">${md(b.raw.spirit)}</article>
    </details>`;
}

function renderCharacters(b) {
  if (!b.characters) return `<article class="prose">${md(b.raw.characters ?? '_Sin characters.md_')}</article>`;
  return `<div class="characters">${b.characters.map((c) => `
    <div class="card character">
      <h3>${esc(c.name)}</h3>
      <div class="role">${esc(c.role)}</div>
      <dl style="margin:0">
        <dt>Descripción</dt><dd>${esc(c.description)}</dd>
        <dt>Arco</dt><dd>${esc(c.arc)}</dd>
        <dt>Estado final</dt><dd>${esc(c.state)}</dd>
      </dl>
    </div>`).join('')}</div>`;
}

function renderSummaries(b) {
  if (!b.summaries.length) return `<div class="empty-state">No hay resúmenes en <code>summaries/</code>.</div>`;
  return `<div class="summary-list">${b.summaries.map((s) => `
    <div class="card"><span class="eyebrow">${esc(s.file)}</span><article class="prose">${md(s.markdown)}</article></div>`).join('')}</div>`;
}

function renderMetrics(b) {
  if (!b.metrics.length) return `<div class="empty-state">No hay registros en <code>metrics.jsonl</code>.</div>`;
  const keys = Object.keys(CHECKS);
  const rows = b.metrics.map((m) => `
    <tr>
      <td><code>${esc(m.fragment ?? '—')}</code></td>
      <td><code>${esc(m.beat ?? '—')}</code></td>
      <td class="c">${m.attempt ?? '—'}</td>
      ${keys.map((k) => `<td class="c"><span class="dot ${m.checks?.[k] === 'pass' ? 'pass' : 'fail'}" title="${CHECKS[k]}: ${esc(m.checks?.[k] ?? '—')}"></span></td>`).join('')}
      <td class="c"><span class="pill ${m.approved ? 'pass' : 'fail'}">${m.approved ? 'aprobado' : 'rechazado'}</span></td>
      <td>${(m.beats_completed ?? []).map((x) => `<code>${esc(x)}</code>`).join(' ') || '<span class="muted">—</span>'}</td>
      <td class="c">${m.chapter_closable ? '✓' : ''}</td>
      <td class="c">${m.paragraphs ?? '—'}</td>
      <td class="small muted">${esc((m.reasons ?? []).join(' · ') || m.note || '')}</td>
    </tr>`).join('');

  const fails = b.stats.checkFails ?? {};
  return `
    <div class="card" style="margin-bottom:1.5rem">
      <span class="eyebrow">Veredictos del Reviewer</span>
      <dl class="kv">
        <dt>Veredictos</dt><dd>${b.stats.verdicts}</dd>
        <dt>Aprobados</dt><dd>${b.stats.approved}</dd>
        <dt>Rechazados</dt><dd>${b.stats.rejected}</dd>
        ${keys.map((k) => `<dt>Fallos en «${CHECKS[k]}»</dt><dd>${fails[k] ?? 0}</dd>`).join('')}
      </dl>
    </div>
    <div class="metrics-legend">
      <span><i class="dot pass"></i> pass</span><span><i class="dot fail"></i> fail</span>
      <span class="muted">Un registro por veredicto, incluidos rechazos (Spec1 §5.3).</span>
    </div>
    <div style="overflow-x:auto">
    <table class="metrics">
      <thead><tr>
        <th>Fragmento</th><th>Beat</th><th>Intento</th>
        ${keys.map((k) => `<th title="${CHECKS[k]}">${CHECKS[k]}</th>`).join('')}
        <th>Veredicto</th><th>Beats completados</th><th>Cierra cap.</th><th>Párr.</th><th>Motivos / notas</th>
      </tr></thead>
      <tbody>${rows}</tbody>
    </table></div>`;
}

load();

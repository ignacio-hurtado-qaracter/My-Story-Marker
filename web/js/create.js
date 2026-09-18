// Create page: builds config.json live from the form. Empty fields are omitted
// so the harness applies its own defaults (spec1 §2.1). Only chapters.count is required.

const form = document.getElementById('config-form');
const preview = document.getElementById('json-preview');
const note = document.getElementById('preview-note');
const toast = document.getElementById('toast');

const COMMENT =
  'Input of the Story Creator Harness. See spec1.md section 2.1. Only chapters.count is required; every other field falls back to its default.';

function setDeep(obj, path, value) {
  const keys = path.split('.');
  let cur = obj;
  for (let i = 0; i < keys.length - 1; i++) {
    cur[keys[i]] ??= {};
    cur = cur[keys[i]];
  }
  cur[keys[keys.length - 1]] = value;
}

function buildConfig() {
  const cfg = { $comment: COMMENT };
  let filled = 0;
  for (const el of form.elements) {
    if (!el.name) continue;
    const raw = el.value.trim();
    if (raw === '') continue;
    filled++;
    const value = el.type === 'number' ? Number(raw) : raw;
    setDeep(cfg, el.name, value);
  }
  return { cfg, filled };
}

function validate(cfg) {
  const problems = [];
  const count = cfg.chapters?.count;
  if (count === undefined) problems.push('Falta el número de capítulos (obligatorio).');
  else if (!Number.isInteger(count) || count < 1) problems.push('El número de capítulos debe ser un entero ≥ 1.');

  const min = cfg.fragment?.min_paragraphs;
  const max = cfg.fragment?.max_paragraphs;
  if (min !== undefined && max !== undefined && min > max) {
    problems.push('El mínimo de párrafos por fragmento no puede superar al máximo.');
  }
  return problems;
}

function render() {
  const { cfg, filled } = buildConfig();
  const problems = validate(cfg);
  preview.textContent = JSON.stringify(cfg, null, 2);
  if (problems.length) {
    note.textContent = problems.join(' ');
    note.style.color = 'var(--fail)';
  } else {
    const omitted = 12 - filled;
    note.textContent =
      omitted > 0
        ? `${filled} campo(s) definidos · ${omitted} usarán el valor por defecto del harness.`
        : 'Todos los campos definidos explícitamente.';
    note.style.color = '';
  }
  return { cfg, problems };
}

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add('show');
  clearTimeout(showToast.t);
  showToast.t = setTimeout(() => toast.classList.remove('show'), 2200);
}

form.addEventListener('input', render);
form.addEventListener('reset', () => setTimeout(render, 0));

document.getElementById('btn-download').addEventListener('click', () => {
  const { cfg, problems } = render();
  if (problems.length) {
    showToast('Revisa los campos marcados antes de descargar.');
    document.getElementById('chapters_count').focus();
    return;
  }
  const blob = new Blob([JSON.stringify(cfg, null, 2) + '\n'], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = Object.assign(document.createElement('a'), { href: url, download: 'config.json' });
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  showToast('config.json descargado');
});

document.getElementById('btn-copy').addEventListener('click', async () => {
  const { cfg } = render();
  try {
    await navigator.clipboard.writeText(JSON.stringify(cfg, null, 2));
    showToast('JSON copiado al portapapeles');
  } catch {
    showToast('No se pudo copiar. Selecciona el texto de la vista previa.');
  }
});

render();

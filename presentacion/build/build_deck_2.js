// presentacion-2: propuesta formal a cliente (10 min + anexos), identidad Qaracter.
//
//   node presentacion/build/build_deck_2.js            -> presentacion/presentacion-2.pptx
//   STUDENT_NAME="..." PRES_DATE="..." node ...
//
// Requiere pptxgenjs y sharp (NODE_PATH a un node_modules que los tenga). El PDF se obtiene
// con LibreOffice: soffice --headless --convert-to pdf presentacion/presentacion-2.pptx
// Las cifras salen de build/data/runs.json y evals/results/*/*.json.

const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");
const sharp = require("sharp");

const HERE = __dirname;
const ROOT = path.resolve(HERE, "..", "..");
const IMG2 = path.join(HERE, "img2");
const CROPS = path.join(IMG2, "crops");
fs.mkdirSync(CROPS, { recursive: true });

const STUDENT = process.env.STUDENT_NAME || "[NOMBRE_ESTUDIANTE]";
const DATE = process.env.PRES_DATE || "25 de septiembre de 2026";
const CLIENT = "Cuentalia Regalos, S.L.";
const CLIENT_SHORT = "Cuentalia";

// ---------------------------------------------------------------- data
const runs = JSON.parse(fs.readFileSync(path.join(HERE, "data", "runs.json"), "utf8"));
const evalOf = (label, b) =>
  JSON.parse(fs.readFileSync(path.join(ROOT, "evals", "results", label, `${b}.json`), "utf8"));
const BRIEFS = ["b2-infantil", "b3-injection", "b4-temporal", "b5-contradiction"];
const after = Object.fromEntries(BRIEFS.map((b) => [b, evalOf("after", b)]));
const before = Object.fromEntries(BRIEFS.map((b) => [b, evalOf("before", b)]));
const fin = runs.final_novel;
const byRole = {};
for (const b of BRIEFS.slice(0, 3))
  for (const [k, v] of Object.entries(after[b].cost.by_role)) byRole[k] = (byRole[k] || 0) + v;
const roleTotal = Object.values(byRole).reduce((a, b) => a + b, 0);
const share = (r) => byRole[r] / roleTotal;

const eur = (n, d = 2) => n.toLocaleString("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d });
const usd = (n) => `${eur(n)} USD`;

// ---------------------------------------------------------------- brand
const C = {
  ink: "1E2B37", ink2: "3D4A56", muted: "5E6A77", line: "E6E9EC", surf: "F7F8FA",
  brand: "FF7A2F", brand600: "E5661F", brand100: "FFE9DC", brand50: "FFF5EE",
  acc: "AE4E14", pass: "16794A", passT: "E4F5EA", fail: "B83232", failT: "FBE5E5", white: "FFFFFF",
  ink3: "2A3B4A",
};
const F = "Arial";
const W = 10, H = 5.625, MX = 0.5;

const pres = new pptxgen();
pres.layout = "LAYOUT_16x9";
pres.author = "Qaracter";
pres.company = "Qaracter";
pres.title = "My Story Marker — propuesta para " + CLIENT_SHORT;
pres.theme = { headFontFace: F, bodyFontFace: F };

const img = (n) => path.join(IMG2, n);
const LOGO = img("logo.png"), LOGO_W = img("logo-white.png"), MARK = img("mark.png");
const LOGO_R = 1400 / 330;

async function crop(src, aspect, name, gravity = "north") {
  const out = path.join(CROPS, name + ".png");
  const meta = await sharp(src).metadata();
  let w = meta.width, h = Math.round(meta.width / aspect);
  if (h > meta.height) { h = meta.height; w = Math.round(h * aspect); }
  const top = gravity === "north" ? 0 : Math.round((meta.height - h) / 2);
  const left = Math.round((meta.width - w) / 2);
  await sharp(src).extract({ left, top, width: w, height: h }).toFile(out);
  return out;
}

// ---------------------------------------------------------------- helpers
function text(slide, t, o) {
  slide.addText(t, { fontFace: F, color: C.ink, fontSize: 12, margin: 0, valign: "top", isTextBox: true, ...o });
}
let pageNo = 0;
function base(kicker, title, { annex = false } = {}) {
  const s = pres.addSlide();
  pageNo += 1;
  s.background = { color: C.white };
  s.addImage({ path: MARK, x: MX, y: 0.33, w: 0.17, h: 0.17 });
  text(s, kicker.toUpperCase(), { x: MX + 0.26, y: 0.3, w: 7, h: 0.24, fontSize: 9.5, bold: true, color: C.acc, charSpacing: 1.5 });
  text(s, title, { x: MX, y: 0.58, w: 9, h: 0.55, fontSize: annex ? 20 : 23, bold: true, valign: "middle" });
  s.addImage({ path: LOGO, x: MX, y: 5.2, w: 0.11 * LOGO_R, h: 0.11 });
  text(s, `My Story Marker · propuesta para ${CLIENT_SHORT}${annex ? " · anexo" : ""}`, {
    x: 1.12, y: 5.18, w: 6, h: 0.16, fontSize: 7.5, color: C.muted, valign: "middle",
  });
  text(s, String(pageNo), { x: 8.9, y: 5.18, w: 0.6, h: 0.16, fontSize: 7.5, color: C.muted, align: "right", valign: "middle" });
  return s;
}
function card(s, x, y, w, h, fill = C.surf, line) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x, y, w, h, rectRadius: 0.08, fill: { color: fill }, line: line ? { color: line, width: 0.75 } : { type: "none" },
  });
}
function badge(s, x, y, label, { size = 0.34, fill = C.brand, color = C.white, fs = 11 } = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w: size, h: size, rectRadius: 0.08, fill: { color: fill }, line: { type: "none" } });
  text(s, label, { x, y, w: size, h: size, fontSize: fs, bold: true, color, align: "center", valign: "middle" });
}
function pill(s, x, y, w, h, t, { fill = C.brand50, color = C.acc, fs = 8, bold = true, align = "center" } = {}) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: Math.min(h / 2, 0.12), fill: { color: fill }, line: { type: "none" } });
  text(s, t, { x: x + 0.05, y, w: w - 0.1, h, fontSize: fs, bold, color, align, valign: "middle" });
}
function arrow(s, x1, y1, x2, y2, color = C.muted) {
  s.addShape(pres.shapes.LINE, {
    x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.abs(x2 - x1) || 0.001, h: Math.abs(y2 - y1) || 0.001,
    flipH: x2 < x1, flipV: y2 < y1, line: { color, width: 1.25, endArrowType: "triangle" },
  });
}
function bullets(s, items, o) {
  s.addText(
    items.map((it, i) => {
      const parts = Array.isArray(it) ? it : [{ text: it }];
      return parts.map((p, j) => ({
        text: p.text,
        options: { bold: p.bold, color: p.color, bullet: j === 0 ? { indent: 12 } : undefined, breakLine: j === parts.length - 1 && i < items.length - 1, paraSpaceAfter: 4 },
      }));
    }).flat(),
    { fontFace: F, fontSize: 10.5, color: C.ink, margin: 0, valign: "top", isTextBox: true, ...o },
  );
}
function table(s, rows, o) {
  const [head, ...body] = rows;
  const fs = o.fontSize || 9;
  const mk = (c, opts) => (typeof c === "object" && c !== null && c.text !== undefined ? { text: c.text, options: { ...opts, ...c.options } } : { text: String(c), options: opts });
  const data = [
    head.map((c) => mk(c, { bold: true, color: C.white, fill: { color: C.ink }, fontSize: fs, fontFace: F, valign: "middle" })),
    ...body.map((r, i) => r.map((c) => mk(c, { color: C.ink, fill: { color: i % 2 ? C.surf : C.white }, fontSize: fs, fontFace: F, valign: "middle" }))),
  ];
  s.addTable(data, { border: { type: "solid", pt: 0.5, color: C.line }, margin: 0.05, ...o });
}
const ok = (t = "✓") => ({ text: t, options: { color: C.pass, bold: true, align: "center" } });
const ko = (t = "✗") => ({ text: t, options: { color: C.fail, bold: true, align: "center" } });
const na = () => ({ text: "—", options: { color: C.muted, align: "center" } });
function framed(s, p, x, y, w, h) {
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x - 0.04, y: y - 0.04, w: w + 0.08, h: h + 0.08, rectRadius: 0.06, fill: { color: C.white }, line: { color: C.line, width: 0.75 }, shadow: { type: "outer", color: "1E2B37", opacity: 0.12, blur: 6, offset: 2, angle: 90 } });
  s.addImage({ path: p, x, y, w, h });
}
function stat(s, x, y, w, big, small, { color = C.ink, fs = 26 } = {}) {
  text(s, big, { x, y, w, h: 0.45, fontSize: fs, bold: true, color, valign: "bottom" });
  text(s, small, { x, y: y + 0.48, w, h: 0.4, fontSize: 8.5, color: C.muted });
}

// ================================================================ slides
async function build() {
  const cropCover = await crop(path.join(HERE, "img", "novela-10-portada.png"), 641 / 910, "portada");
  const cropWizard = await crop(path.join(ROOT, "frontend/screenshots/new-novel/desktop-4-historia.png"), 1.753, "wizard");
  const cropReader = await crop(path.join(ROOT, "frontend/screenshots/visual-check/02-index.png"), 1.753, "reader");
  const v2n = await crop(img("v2-novedades.png"), 0.78, "v2n");

  // ------------------------------------------------------------ 1 · Portada
  {
    const s = pres.addSlide(); pageNo += 1;
    s.background = { color: C.ink };
    s.addImage({ path: LOGO_W, x: MX, y: 0.45, w: 0.4 * LOGO_R, h: 0.4 });
    text(s, "PROPUESTA DE SERVICIO", { x: MX, y: 1.35, w: 5.5, h: 0.25, fontSize: 10, bold: true, color: C.brand, charSpacing: 2 });
    text(s, "My Story Marker", { x: MX, y: 1.62, w: 6, h: 0.75, fontSize: 40, bold: true, color: C.white, valign: "middle" });
    text(s, "Novelas personalizadas para regalar, escritas por un harness de agentes que se puede verificar", {
      x: MX, y: 2.4, w: 5.6, h: 0.6, fontSize: 14, color: "C9D1D9",
    });
    const rows = [["Cliente", CLIENT], ["Ocasión", "Catálogo de Navidad 2026: la novela-regalo personalizada"], ["Fecha", DATE], ["Presenta", STUDENT]];
    rows.forEach(([k, v], i) => {
      const y = 3.3 + i * 0.38;
      text(s, k.toUpperCase(), { x: MX, y, w: 1.1, h: 0.3, fontSize: 8.5, bold: true, color: C.brand, charSpacing: 1, valign: "middle" });
      text(s, v, { x: MX + 1.15, y, w: 4.6, h: 0.3, fontSize: 11.5, color: C.white, valign: "middle" });
    });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: 6.55, y: 0.55, w: 3.0, h: 4.4, rectRadius: 0.12, fill: { color: C.ink3 }, line: { type: "none" } });
    s.addImage({ path: cropCover, x: 6.8, y: 0.8, w: 3.5 * 641 / 910, h: 3.5 });
    text(s, "Portada real de la novela de ejemplo (10 capítulos, PDF exportado por el sistema)", { x: 6.8, y: 4.42, w: 2.5, h: 0.4, fontSize: 7.5, color: "AEB8C2" });
    s.addNotes(`[0:00–0:30] Buenos días. Soy ${STUDENT}, de Qaracter, y presento a ${CLIENT} nuestra propuesta: My Story Marker, un servicio que escribe novelas personalizadas para regalar.\nLa ocasión es su catálogo de Navidad: quieren vender un regalo que no existe hecho.\nLa idea que quiero que se lleven: lo difícil no es escribir diez capítulos con IA, es poder demostrar que lo que se entrega es coherente, está personalizado y no contiene nada vetado.`);
  }

  // ------------------------------------------------------------ 2 · Problema y cliente
  {
    const s = base("Problema y cliente", "Un regalo único que hoy no se puede comprar hecho");
    text(s, "Quién compra y para qué", { x: MX, y: 1.3, w: 4, h: 0.3, fontSize: 13, bold: true });
    const who = [
      ["Hijos y nietos", "jubilaciones, 70 cumpleaños, homenajes a un padre o una abuela"],
      ["Parejas", "aniversarios, bodas, «cómo nos conocimos»"],
      ["Padres y padrinos", "un cuento en el que el niño es el protagonista (cumpleaños, comunión)"],
    ];
    who.forEach(([h, d], i) => {
      const y = 1.72 + i * 0.78;
      card(s, MX, y, 4.1, 0.66, C.brand50);
      badge(s, MX + 0.14, y + 0.16, String(i + 1));
      text(s, h, { x: MX + 0.62, y: y + 0.08, w: 3.35, h: 0.24, fontSize: 11, bold: true });
      text(s, d, { x: MX + 0.62, y: y + 0.32, w: 3.35, h: 0.3, fontSize: 9, color: C.ink2 });
    });
    text(s, "Por qué las alternativas actuales no funcionan", { x: 4.9, y: 1.3, w: 4.6, h: 0.3, fontSize: 13, bold: true });
    table(s, [
      ["Alternativa", "Por qué falla"],
      ["Escritor por encargo", "semanas o meses y precio de artesanía; un regalo tiene fecha"],
      ["Libro plantilla", "solo cambia el nombre: el destinatario no se reconoce"],
      ["Chat con un LLM", "mezcla nombres, olvida recuerdos, contradice fechas, ignora vetos; sin PDF ni correcciones"],
    ], { x: 4.9, y: 1.72, w: 4.6, colW: [1.35, 3.25], fontSize: 9, rowH: 0.42 });
    card(s, 4.9, 3.72, 4.6, 0.62, C.ink);
    text(s, [
      { text: "Lo que pide " + CLIENT_SHORT + ": ", options: { bold: true, color: C.brand } },
      { text: "10 capítulos en horas, en los que el destinatario se reconozca, sin nada vetado y corregibles.", options: { color: C.white } },
    ], { x: 5.05, y: 3.72, w: 4.3, h: 0.62, fontSize: 10, valign: "middle" });
    text(s, "Criterio de calidad del sistema (D11): personalización y calidad narrativa pesan igual. Meter los datos a martillazos no cuenta como éxito.", {
      x: MX, y: 4.5, w: 9, h: 0.4, fontSize: 9, italic: true, color: C.muted,
    });
    s.addNotes(`[0:30–1:30] ¿Quién compra? Hijos para la jubilación de un padre, parejas para un aniversario, padres que quieren un cuento con su hijo de protagonista.\nLas alternativas fallan: un escritor tarda meses y un regalo tiene fecha; un libro plantilla solo cambia el nombre; y un chat con un LLM, sin más, cambia nombres, olvida recuerdos, contradice fechas y no respeta los vetos del cliente, como el nombre de una expareja.\nNuestro criterio de calidad: personalización y calidad narrativa pesan igual.`);
  }

  // ------------------------------------------------------------ 3 · Configuración y lectura
  {
    const s = base("Configuración y lectura", "Configurar, leer y corregir una novela");
    const cols = [
      [cropWizard, "1", "Configurar", "Asistente de 5 pasos: destinatario, personas, recuerdos, historia (género, tono, vetos) y dedicatoria. El brief se valida con JSON Schema y reglas de coherencia antes de gastar un token."],
      [cropReader, "2", "Leer", "Lector web con portada y dedicatoria, índice, capítulos y fichas de personajes con «Aparece en». El PDF exportado tiene la misma estructura y enlaces internos."],
      [v2n, "3", "Corregir", "«La perra se llama Nala»: se pide desde el lector, la CLI o la API. Solo se regeneran los capítulos que usan ese hecho, en una versión nueva; la anterior se conserva."],
    ];
    cols.forEach(([p, n, h, d], i) => {
      const x = MX + i * 3.08, w = 2.84;
      const ih = 1.62;
      if (i === 2) {
        framed(s, p, x + (w - 1.62 * 0.78) / 2, 1.35, 1.62 * 0.78, 1.62);
      } else framed(s, p, x, 1.35, w, ih);
      badge(s, x, 3.2, n);
      text(s, h, { x: x + 0.45, y: 3.2, w: w - 0.45, h: 0.34, fontSize: 13, bold: true, valign: "middle" });
      text(s, d, { x, y: 3.62, w, h: 1.2, fontSize: 9.5, color: C.ink2 });
    });
    text(s, "Capturas reales: asistente «Nueva novela», validador visual del lector (Playwright MCP) y página «Novedades» del PDF de la versión 2.", {
      x: MX, y: 4.82, w: 9, h: 0.25, fontSize: 8, color: C.muted, italic: true,
    });
    s.addNotes(`[1:30–2:30] Configurar: el comprador rellena un asistente de cinco pasos. Al final, el brief se valida: si faltan datos o hay contradicciones, por ejemplo romance para un niño de seis años, se rechaza antes de generar nada.\nLeer: la novela se publica en un lector web con portada, dedicatoria, índice y fichas de personajes; y se exporta a PDF con la misma estructura.\nCorregir: si el lector dice «la perra se llama Nala», solo se regeneran los capítulos que usan ese dato, en una versión nueva; la anterior no se toca. Lo veremos en la demo.`);
  }

  // ------------------------------------------------------------ 4 · Arquitectura: roles y bucle
  {
    const s = base("Arquitectura del harness · 1/2", "Cinco roles con un solo trabajo, orquestados por código");
    const roles = [
      ["interviewer", "brief + hechos del texto libre"],
      ["planner", "plan, reparto, cronología, calendario"],
      ["writer", "3 escenas por capítulo"],
      ["editor", "une, pule y reescribe"],
      ["judge", "rúbrica de 5 criterios"],
      ["publicación", "versión v · lector + PDF"],
    ];
    const gates = [
      "hook · brief_schema", "plan_check · Lean del plan", "scene_accept · ≤ 2 reescrituras",
      "chapter_close · ≤ 2 · checkpoint", "pre_publish · cobertura · Lean · juez · visual", "≤ 2 rondas de reparación; si no, bloqueada",
    ];
    const bw = 1.3, gap = 0.24, y0 = 1.3;
    roles.forEach(([r, d], i) => {
      const x = MX + i * (bw + gap);
      const last = i === roles.length - 1;
      card(s, x, y0, bw, 0.82, last ? C.brand : C.ink);
      text(s, r, { x: x + 0.08, y: y0 + 0.08, w: bw - 0.16, h: 0.26, fontSize: 11, bold: true, color: C.white, align: "center", fontFace: last ? F : "Courier New" });
      text(s, d, { x: x + 0.08, y: y0 + 0.36, w: bw - 0.16, h: 0.4, fontSize: 8, color: last ? C.white : "C9D1D9", align: "center" });
      if (i < roles.length - 1) arrow(s, x + bw + 0.02, y0 + 0.41, x + bw + gap - 0.02, y0 + 0.41, C.brand);
      arrow(s, x + bw / 2, y0 + 0.84, x + bw / 2, y0 + 1.0, C.muted);
      pill(s, x, y0 + 1.02, bw, 0.5, gates[i], { fs: 7.5 });
    });
    text(s, "↺  Cada fallo vuelve, con su evidencia y un presupuesto de reintentos, al rol que puede arreglarlo. Agotado el presupuesto, la versión se bloquea: nunca se publica.", {
      x: MX, y: 2.95, w: 9, h: 0.3, fontSize: 9.5, color: C.acc, bold: true,
    });
    // bottom row
    card(s, MX, 3.4, 4.4, 1.55, C.surf, C.line);
    text(s, "Orquestador · app/novel/pipeline.py", { x: MX + 0.18, y: 3.5, w: 4.1, h: 0.28, fontSize: 11, bold: true });
    bullets(s, [
      "Decide qué documentos ve cada rol y valida su salida con JSON Schema.",
      "Escribe en la story bible en nombre del rol: la tabla de permisos se aplica en código, no en un prompt.",
      "Ningún modelo tiene herramientas de escritura; todos corren en Claude Haiku 4.5.",
    ], { x: MX + 0.18, y: 3.82, w: 4.1, h: 1.1, fontSize: 9 });
    card(s, 5.1, 3.4, 2.1, 1.55, C.brand50);
    text(s, "Story bible", { x: 5.25, y: 3.5, w: 1.85, h: 0.28, fontSize: 11, bold: true });
    text(s, "SQLite autoritativa: brief, hechos y su uso por escena, cronología, versiones, checkpoints y audit log.", { x: 5.25, y: 3.82, w: 1.85, h: 1.05, fontSize: 8.5, color: C.ink2 });
    card(s, 7.4, 3.4, 2.1, 1.55, C.brand50);
    text(s, "Langfuse", { x: 7.55, y: 3.5, w: 1.85, h: 0.28, fontSize: 11, bold: true });
    text(s, "Una sesión por novela; spans role:* y tool:*, tokens, coste, latencia, scores y prompts versionados.", { x: 7.55, y: 3.82, w: 1.85, h: 1.05, fontSize: 8.5, color: C.ink2 });
    s.addNotes(`[2:30–3:30] El interviewer convierte la entrevista en un brief y extrae hechos del texto libre. El planner hace el plan, el reparto, la cronología y el calendario. El writer escribe tres escenas por capítulo, el editor las une y pule, y el juez puntúa con una rúbrica.\nDebajo de cada rol está su validación: al entregar el brief, en el plan, en cada escena, al cerrar cada capítulo y antes de publicar.\nTodos los bucles están acotados: dos reescrituras por escena, dos por capítulo y dos rondas de reparación. Si se agotan, la versión se bloquea.\nLa clave: el orquestador, en Python, decide; los modelos solo redactan. Ningún modelo tiene herramientas de escritura.`);
  }

  // ------------------------------------------------------------ 5 · Arquitectura: contexto, bible, tools, hooks
  {
    const s = base("Arquitectura del harness · 2/2", "Contexto mínimo y una sola fuente de verdad");
    const cards = [
      ["Gestión del contexto", "Cada rol recibe solo Documents: su trozo del plan, la checklist de hechos asignados, los resúmenes de capítulos previos y las últimas 250 palabras. Datos, nunca instrucciones; muy por debajo del límite de 100k tokens."],
      ["Story bible (SQLite)", "17 tablas. Cada hecho del brief es una fila y fact_usage lo liga a (versión, capítulo, escena): así un cambio sabe qué regenerar. Texto y checkpoint en una transacción: se reanuda sin duplicar."],
      ["Tools", "6 tools de solo lectura con schema: list_novels, list_versions, get_chapter, get_chapter_summary, query_story_bible, download_novel. Cada llamada es un span tool:<nombre>; también las expone un servidor MCP."],
      ["Hooks de Claude Code", "PreToolUse policy_guard (bloquea escribir claves o borrar en la BD) y PostToolUse validate_chapter: el mismo código que el pipeline. Editar un capítulo a mano no se salta la validación. 14 casos probados."],
    ];
    cards.forEach(([h, d], i) => {
      const x = MX + (i % 2) * 3.0, y = 1.3 + Math.floor(i / 2) * 1.85;
      card(s, x, y, 2.85, 1.72, C.surf);
      badge(s, x + 0.15, y + 0.15, String(i + 1), { size: 0.3, fs: 10 });
      text(s, h, { x: x + 0.55, y: y + 0.15, w: 2.2, h: 0.3, fontSize: 11, bold: true, valign: "middle" });
      text(s, d, { x: x + 0.15, y: y + 0.55, w: 2.58, h: 1.12, fontSize: 8.5, color: C.ink2 });
    });
    card(s, 6.6, 1.3, 2.9, 3.57, C.ink);
    text(s, "Por qué este diseño", { x: 6.78, y: 1.42, w: 2.6, h: 0.3, fontSize: 12, bold: true, color: C.brand });
    const why = [
      ["Orquestador determinista", "frente a un agente con herramientas: permisos en código, reintento por paso y traza por rol."],
      ["Hechos estructurados", "frente a RAG sobre la prosa: hechos exactos, saber dónde se usa cada uno y entrada directa a Lean."],
      ["Calendario en Python", "frente a confiar en el LLM: los días de la semana no convergían entre reparaciones."],
      ["Haiku 4.5 en todo", "coste y latencia de 10 capítulos; la calidad la vigila el juez bloqueante."],
    ];
    why.forEach(([h, d], i) => {
      const y = 1.82 + i * 0.75;
      text(s, h, { x: 6.78, y, w: 2.6, h: 0.22, fontSize: 9.5, bold: true, color: C.white });
      text(s, d, { x: 6.78, y: y + 0.23, w: 2.6, h: 0.5, fontSize: 8, color: "C9D1D9" });
    });
    s.addNotes(`[3:30–4:30] Contexto: ningún rol ve toda la novela ni el texto libre crudo. Recibe su trozo del plan, los hechos que le tocan, resúmenes de los capítulos anteriores y el final del último. Así cabemos de sobra en el límite de 100k tokens y el texto del cliente nunca actúa como instrucción.\nStory bible: una SQLite autoritativa. Cada hecho es una fila, y sabemos en qué escena se usa: es lo que permite regenerar solo lo afectado.\nTools de solo lectura con schema, trazadas en Langfuse, y los hooks de Claude Code usan el mismo código que el pipeline.\nPor qué: permisos en código y no en prompts, hechos exactos en vez de RAG, y lo determinista (el calendario) fuera del modelo.`);
  }

  // ------------------------------------------------------------ 6 · Validadores
  {
    const s = base("Validación · 1/4", "Cuatro tipos de validador, en cuatro puntos");
    const pts = ["hook", "scene_accept", "chapter_close", "pre_publish"];
    const ptd = ["al entregar el brief", "cada escena", "cada capítulo", "antes de publicar"];
    pts.forEach((p, i) => {
      const x = 2.45 + i * 1.78;
      pill(s, x, 1.28, 1.66, 0.46, "", { fill: C.ink });
      text(s, p, { x, y: 1.3, w: 1.66, h: 0.24, fontSize: 9.5, bold: true, color: C.white, align: "center", fontFace: "Courier New" });
      text(s, ptd[i], { x, y: 1.52, w: 1.66, h: 0.2, fontSize: 7.5, color: "C9D1D9", align: "center" });
      if (i < 3) arrow(s, x + 1.67, 1.51, x + 1.77, 1.51, C.brand);
    });
    const types = [
      ["Programático", ["brief_schema", "schema_role_output · no_placeholders", "chapter_length · exact_names · calendar_consistency · prose_repetition", "brief_coverage · visual_check"]],
      ["Guardrail", ["free_text_injection (prescan)", "forbidden_words_scene", "forbidden_words_chapter", ""]],
      ["Semántico", ["", "", "judge_chapter", "judge_novel (≥ 3 por criterio, media ≥ 3,5)"]],
      ["Formal", ["", "", "", "lean_chronology (4 invariantes) · TLA+/TLC del flujo en desarrollo"]],
    ];
    types.forEach(([t, cells], r) => {
      const y = 1.88 + r * 0.66;
      card(s, MX, y, 1.8, 0.56, r % 2 ? C.surf : C.brand50);
      text(s, t, { x: MX + 0.12, y, w: 1.6, h: 0.56, fontSize: 11, bold: true, valign: "middle" });
      cells.forEach((c, i) => {
        const x = 2.45 + i * 1.78;
        if (!c) { s.addShape(pres.shapes.OVAL, { x: x + 0.78, y: y + 0.23, w: 0.1, h: 0.1, fill: { color: C.line }, line: { type: "none" } }); return; }
        card(s, x, y, 1.66, 0.56, C.white, C.line);
        text(s, c, { x: x + 0.06, y, w: 1.54, h: 0.56, fontSize: 7, color: C.ink, align: "center", valign: "middle", fontFace: "Courier New" });
      });
    });
    card(s, MX, 4.58, 9, 0.46, C.ink);
    text(s, [
      { text: "Si falla: ", options: { bold: true, color: C.brand } },
      { text: "vuelve al rol productor con la evidencia (escena → writer, capítulo → editor, novela → capítulos citados). Cada resultado se guarda en validator_result y llega a Langfuse como score.", options: { color: C.white } },
    ], { x: MX + 0.15, y: 4.58, w: 8.7, h: 0.46, fontSize: 9, valign: "middle" });
    s.addNotes(`[4:30–5:00] Cuatro tipos de validador y cuatro puntos de ejecución. Programáticos: schema, longitud, nombres exactos, cobertura de los datos del brief, y calendar_consistency, que comprueba que un día de la semana junto a una fecha es correcto. Guardrails: inyección y palabras prohibidas, en escena y en capítulo. Semánticos: el juez por capítulo y por novela. Formales: Lean sobre la cronología de cada novela y TLA+ sobre el propio harness.\nCada fallo vuelve al rol que lo produjo, con la evidencia.`);
  }

  // ------------------------------------------------------------ 7 · Evals y tuning
  {
    const s = base("Validación · 2/4", "Resultados por brief, y la mejora medida tras el tuning");
    const lbl = { published: "publicada", blocked: "bloqueada", rejected_by_validation: "rechazado", pipeline_error: "parada (plan)" };
    const outc = (e) => {
      const st = e.final && e.final.status ? e.final.status : e.outcome === "rejected_by_validation" ? "rejected_by_validation" : e.outcome;
      const t = lbl[st] || st;
      return st === "published" ? ok(t) : st === "rejected_by_validation" ? { text: t, options: { color: C.muted, align: "center" } } : ko(t);
    };
    const decisive = {
      "b2-infantil": ["brief_coverage ✗ (frase literal)", "todos ✓"],
      "b3-injection": ["brief_coverage ✗ · inyección ⚑", "todos ✓ · inyección ⚑ no seguida"],
      "b4-temporal": ["error en el plan", "judge_chapter / judge_novel ✗ (edad)"],
      "b5-contradiction": ["brief_schema ✗", "brief_schema ✗ (6 años + romance)"],
    };
    const rows = [["Brief", "Antes", "Después", "Qué decidió (antes → después)", "USD"]];
    for (const b of BRIEFS) {
      const c = after[b].cost && after[b].cost.cost_usd;
      rows.push([{ text: b, options: { fontFace: "Courier New" } }, outc(before[b]), outc(after[b]), decisive[b].join("  →  "), c ? eur(c) : "—"]);
    }
    table(s, rows, { x: MX, y: 1.3, w: 6.1, colW: [1.25, 0.85, 0.85, 2.6, 0.55], fontSize: 8.5, rowH: 0.4 });
    text(s, "b4 bloqueada es el resultado esperado: su trampa de edad no tiene lectura coherente. b5 se rechaza antes de generar. Umbrales del juez intactos.", {
      x: MX, y: 3.4, w: 6.1, h: 0.4, fontSize: 8, italic: true, color: C.muted,
    });
    text(s, "Qué cambió en el tuning 1", { x: MX, y: 3.85, w: 6, h: 0.25, fontSize: 10.5, bold: true });
    bullets(s, [
      "brief_coverage: palabras de contenido normalizadas, no la frase literal del recuerdo.",
      "Planner con time_marker por capítulo; juez bloquea solo por un defecto «alta» concreto.",
      "Reparación solo de los capítulos citados; MAX_REPAIR_ROUNDS 1 → 2 (TLC re-ejecutado).",
    ], { x: MX, y: 4.12, w: 6.1, h: 0.9, fontSize: 8.5 });
    // stats column
    card(s, 6.85, 1.3, 2.65, 1.7, C.ink);
    text(s, "EVALS · 3 BRIEFS GENERABLES", { x: 7.0, y: 1.4, w: 2.4, h: 0.22, fontSize: 7.5, bold: true, color: C.brand, charSpacing: 1 });
    text(s, "0/3 → 2/3", { x: 7.0, y: 1.65, w: 2.4, h: 0.6, fontSize: 30, bold: true, color: C.white });
    text(s, "novelas publicadas antes → después del tuning 1", { x: 7.0, y: 2.3, w: 2.4, h: 0.5, fontSize: 8.5, color: "C9D1D9" });
    card(s, 6.85, 3.15, 2.65, 1.87, C.brand50);
    text(s, "10 CAPÍTULOS · TUNING 2", { x: 7.0, y: 3.25, w: 2.4, h: 0.22, fontSize: 7.5, bold: true, color: C.acc, charSpacing: 1 });
    text(s, "bloqueada → publicada", { x: 7.0, y: 3.5, w: 2.45, h: 0.4, fontSize: 14, bold: true });
    text(s, `Calendario calculado en Python y calendar_consistency en chapter_close. Resultado: ${fin.chapters} capítulos, ${fin.words.toLocaleString("es-ES")} palabras, ${fin.repair_rounds} rondas de reparación, ${usd(fin.cost_usd)}.`, {
      x: 7.0, y: 3.92, w: 2.4, h: 1.05, fontSize: 8.5, color: C.ink2,
    });
    s.addNotes(`[5:00–5:30] Cinco briefs de evaluación: ejemplo, infantil, inyección, trampas temporales y contradictorio. Antes del tuning se publicaban 0 de 3: brief_coverage exigía la frase literal del recuerdo. Tras el tuning 1, 2 de 3, sin bajar ningún umbral de calidad. El de trampas temporales sigue bloqueado, y es lo correcto.\nEn la novela de 10 capítulos, el segundo intento se bloqueó porque los días de la semana no cuadraban con sus fechas y cada reparación inventaba otros. Tuning 2: el calendario lo calcula Python. El intento siguiente se publicó a la primera: ${fin.words} palabras, ${usd(fin.cost_usd)}.`);
  }

  // ------------------------------------------------------------ 8 · Lean + TLC
  {
    const s = base("Validación · 3/4", "Lean prueba la historia; TLC prueba el harness");
    text(s, "Un fallo detectado por Lean (caso L04)", { x: MX, y: 1.3, w: 4.3, h: 0.28, fontSize: 12, bold: true });
    card(s, MX, 1.65, 4.3, 0.78, C.failT);
    text(s, [
      { text: "b4-temporal, sin el prechequeo del plan: ", options: { bold: true, color: C.fail } },
      { text: "la mascota muere en 2005 y lleva los anillos en la boda de 2008. lean_chronology falla en noAfterExit, señalando evento, fecha y capítulo.", options: { color: C.ink } },
    ], { x: MX + 0.14, y: 1.65, w: 4.02, h: 0.78, fontSize: 9, valign: "middle" });
    table(s, [
      ["Validador", "¿Lo vio?"],
      [{ text: "lean_chronology", options: { fontFace: "Courier New" } }, ok("Sí · noAfterExit")],
      [{ text: "judge_novel", options: { fontFace: "Courier New" } }, ok("Sí · continuidad 2/5")],
      [{ text: "judge_chapter", options: { fontFace: "Courier New" } }, ko("No · aprobó el capítulo")],
      ["6 validadores programáticos", ko("No")],
    ], { x: MX, y: 2.55, w: 4.3, colW: [2.2, 2.1], fontSize: 8.5, rowH: 0.3 });
    text(s, "4 invariantes: temporalOrder · agesCoherent · noBilocation · noAfterExit. Corre en pre_publish (lake build) y sobre el plan antes de escribir (~0,12 USD frente a ~1,3 USD de una novela).", {
      x: MX, y: 4.15, w: 4.3, h: 0.6, fontSize: 8.5, color: C.ink2,
    });
    // TLC
    text(s, "Propiedades verificadas con TLC", { x: 5.2, y: 1.3, w: 4.3, h: 0.28, fontSize: 12, bold: true });
    table(s, [
      ["Propiedad", "Garantiza"],
      ["NoUnvalidatedPublish", "no se publica nada que no pasó todos los validadores"],
      ["ResumeNoDupNoLoss", "reanudar tras un crash no duplica ni pierde capítulos"],
      ["PreviousVersionKept", "la versión publicada anterior no cambia"],
      ["RetriesBounded", "reintentos acotados, también tras un crash"],
      ["EveryGenerationEnds", "liveness: acaba publicada o en error"],
    ].map((r, i) => (i ? [{ text: r[0], options: { fontFace: "Courier New", fontSize: 7.5 } }, r[1]] : r)), { x: 5.2, y: 1.65, w: 4.3, colW: [1.7, 2.6], fontSize: 8, rowH: 0.32 });
    card(s, 5.2, 3.72, 4.3, 1.05, C.ink);
    text(s, "5.492.531", { x: 5.35, y: 3.78, w: 2.2, h: 0.5, fontSize: 24, bold: true, color: C.white, valign: "middle" });
    text(s, "estados distintos, sin errores", { x: 5.35, y: 4.28, w: 2.2, h: 0.4, fontSize: 8.5, color: "C9D1D9" });
    text(s, "N = 5 capítulos · 3 escenas · reintentos 2/2 · reparación 2 · profundidad 127 · 8 min 17 s. Antes, 4 contraejemplos (CE1–CE4) cambiaron el diseño.", {
      x: 7.55, y: 3.8, w: 1.85, h: 0.95, fontSize: 7.5, color: "C9D1D9",
    });
    s.addNotes(`[5:30–6:00] Lean: de la story bible se genera la cronología y se demuestran cuatro invariantes. El caso real: con el brief de trampas temporales, la mascota muere en 2005 y lleva los anillos en la boda de 2008. Lean lo vio, con evento y capítulo; el juez de capítulo lo aprobó. Siendo honestos, el juez de novela también lo vio; el valor de Lean es que es determinista y actúa sobre el plan, antes de gastar la escritura.\nTLA+: el harness es una máquina de estados. TLC comprueba que nunca se publica nada sin validar, que reanudar no duplica ni pierde capítulos, que la versión anterior se conserva, que los reintentos están acotados y que toda generación termina. Cinco millones y medio de estados, sin errores.`);
  }

  // ------------------------------------------------------------ 9 · Langfuse
  {
    const s = base("Validación · 4/4 · Observabilidad", "Una traza real del brief de inyección");
    const b3 = after["b3-injection"];
    const ch = b3.cost.by_chapter;
    const tree = [
      [0, "session", "eval-after-b3-injection", "una por novela"],
      [1, "trace", "generate", `${b3.cost.calls} llamadas · ${usd(b3.cost.cost_usd)} · ${Math.round(b3.cost.latency_s)} s`],
      [2, "span", "phase:plan · role:interviewer, role:planner", `${ch[0].calls} llamadas · ${usd(ch[0].cost_usd)}`],
      ...ch.slice(1).map((c) => [2, "span", `chapter:${c.chapter} · role:writer ×3, editor, judge`, `${c.calls} llamadas · ${usd(c.cost_usd)} · ${Math.round(c.latency_s)} s`]),
      [3, "span", "tool:get_chapter_summary · tool:query_story_bible", "contexto del writer"],
      [2, "span", "phase:pre_publish · judge_novel · lean · visual", "versión 1 publicada"],
    ];
    card(s, MX, 1.3, 5.6, 3.72, C.ink);
    tree.forEach(([lvl, kind, name, meta], i) => {
      const y = 1.42 + i * 0.44, x = MX + 0.15 + lvl * 0.3;
      pill(s, x, y + 0.04, 0.62, 0.24, kind, { fill: kind === "span" ? C.ink3 : C.brand, color: C.white, fs: 7 });
      text(s, name, { x: x + 0.7, y, w: 4.7 - lvl * 0.3, h: 0.2, fontSize: 8.5, bold: true, color: C.white, fontFace: "Courier New" });
      text(s, meta, { x: x + 0.7, y: y + 0.2, w: 4.7 - lvl * 0.3, h: 0.18, fontSize: 7.5, color: "AEB8C2" });
    });
    text(s, "Scores de la traza", { x: 6.35, y: 1.3, w: 3.1, h: 0.25, fontSize: 11, bold: true });
    const v = b3.validators;
    const sc = [
      ["free_text_injection", "flagged ×2 (prescan + modelo)", false],
      ["forbidden_words_scene", `${v.forbidden_words_scene.units}/${v.forbidden_words_scene.units} · 1,0`, true],
      ["prose_repetition", `min ${eur(v.prose_repetition.min_score, 1)}`, true],
      ["judge_chapter", `3/3 · min ${eur(v.judge_chapter.min_score, 1)}`, true],
      ["judge_novel · lean", "aprobada", true],
    ];
    sc.forEach(([n, val, good], i) => {
      const y = 1.62 + i * 0.36;
      text(s, n, { x: 6.35, y, w: 1.75, h: 0.3, fontSize: 7.5, fontFace: "Courier New", valign: "middle" });
      pill(s, 8.1, y + 0.03, 1.4, 0.24, val, { fill: good ? C.passT : C.brand100, color: good ? C.pass : C.acc, fs: 7 });
    });
    text(s, "Prompts versionados usados", { x: 6.35, y: 3.5, w: 3.1, h: 0.25, fontSize: 11, bold: true });
    text(s, b3.prompts.filter((p) => !p.prompt_version.startsWith("sha")).map((p) => `${p.prompt_name} v${p.prompt_version}`).join(" · "), {
      x: 6.35, y: 3.78, w: 3.15, h: 0.45, fontSize: 8, color: C.ink2, fontFace: "Courier New",
    });
    text(s, `Tokens: ${b3.cost.input_tokens.toLocaleString("es-ES")} de entrada · ${b3.cost.output_tokens.toLocaleString("es-ES")} de salida · ${b3.cost.cache_creation.toLocaleString("es-ES")} de caché. Datos de llm_call (evals/results/after/b3-injection.json), la misma instrumentación que envía spans y scores a Langfuse.`, {
      x: 6.35, y: 4.28, w: 3.15, h: 0.75, fontSize: 7, color: C.muted, italic: true,
    });
    s.addNotes(`[6:00–6:30] Así se ve una novela en Langfuse: una sesión por novela, una traza por generación, spans por fase, por capítulo, por rol y por tool, con tokens, coste y latencia. Esta es la del brief con inyección: ${b3.cost.calls} llamadas, ${usd(b3.cost.cost_usd)}, unos ${Math.round(b3.cost.latency_s / 60)} minutos.\nCada validador llega como score: aquí se ve la inyección marcada dos veces, por el prescan y por el modelo, y aun así todos los validadores en verde: no se siguió.\nY los prompts están versionados: sabemos qué versión produjo cada resultado, que es lo que hace creíble el antes y el después del tuning.`);
  }

  // ------------------------------------------------------------ 10 · Guardrails
  {
    const s = base("Guardrails", "Reglas que se cumplen aunque el modelo no quiera");
    // forbidden word flow
    text(s, "Palabras prohibidas: detección y reescritura", { x: MX, y: 1.3, w: 9, h: 0.26, fontSize: 11.5, bold: true });
    const flow = [
      ["Escena escrita", "contiene «idiota» (veto global)", C.surf, C.ink],
      ["forbidden_words_scene", "reject · término, ámbito y escena", C.failT, C.fail],
      ["Feedback al writer", "reescritura 1 de ≤ 2", C.brand50, C.acc],
      ["Escena aceptada", "0 apariciones; decisión en policy_decision", C.passT, C.pass],
    ];
    flow.forEach(([h, d, fill, col], i) => {
      const x = MX + i * 2.3;
      card(s, x, 1.62, 2.05, 0.72, fill);
      text(s, h, { x: x + 0.1, y: 1.66, w: 1.85, h: 0.28, fontSize: 9.5, bold: true, color: col, fontFace: i === 1 ? "Courier New" : F });
      text(s, d, { x: x + 0.1, y: 1.95, w: 1.85, h: 0.36, fontSize: 8, color: C.ink2 });
      if (i < 3) arrow(s, x + 2.07, 1.98, x + 2.28, 1.98, C.brand);
    });
    text(s, "Un solo normalizador (NFKD, sin tildes, plurales): detecta t0nt0 · tontooo · t.o.n.t.o · cabrones → cabrón; sin falsos positivos en «tontería» o «ridículo». Vetos en 3 niveles: global, del cliente, léxico.", {
      x: MX, y: 2.42, w: 9, h: 0.38, fontSize: 8.5, color: C.ink2,
    });
    const q = [
      ["Datos personales", ["Los datos del destinatario viven solo en la story bible; cada novela tiene dueño y otro usuario recibe 404 (bcrypt + JWT).", "Claves fuera del repo; el hook bloquea escribirlas. Evals con destinatarios ficticios."]],
      ["Injection", ["Prescan determinista antes del modelo: 17/17 variantes. El extractor solo devuelve hechos y marca la sospecha.", "Ningún rol recibe el texto libre crudo: b3 marcó 5 patrones y se publicó sin seguirlos."]],
      ["Audit log", ["policy_decision, validator_result y llm_call: cada decisión, validador y llamada con prompt, tokens y coste.", "Nada se borra: una versión nueva nunca sobrescribe la anterior."]],
    ];
    q.forEach(([h, items], i) => {
      const x = MX + i * 3.05;
      card(s, x, 2.95, 2.85, 2.07, C.surf);
      badge(s, x + 0.14, 3.07, String(i + 1), { size: 0.3, fs: 10 });
      text(s, h, { x: x + 0.54, y: 3.07, w: 2.2, h: 0.3, fontSize: 11, bold: true, valign: "middle" });
      bullets(s, items, { x: x + 0.14, y: 3.5, w: 2.6, h: 1.5, fontSize: 9.5 });
    });
    s.addNotes(`[6:30–7:00] Palabras prohibidas: en un experimento real, una escena usó un insulto de la lista global; forbidden_words_scene la rechazó, volvió al writer con el término y la reescritura lo eliminó. Todo queda en policy_decision.\nDatos personales: solo en la base de datos, cada novela tiene dueño y nadie más la ve. Inyección: prescan determinista, y el texto libre nunca llega crudo a un rol. Y todo queda en el audit log.`);
  }

  // ------------------------------------------------------------ 11 · Presupuesto y coste
  {
    const s = base("Presupuesto y coste", "Coste medido y propuesta económica");
    const nala = 0.94;
    const worst = Math.max(...runs.ten_chapter_attempts.map((a) => a.cost_usd));
    stat(s, MX, 1.25, 1.45, eur(fin.cost_usd), "USD de modelo, novela de 10 capítulos publicada", { color: C.acc });
    stat(s, MX + 1.5, 1.25, 1.45, eur(nala), "USD por un cambio del lector (9 capítulos)");
    stat(s, MX + 3.0, 1.25, 1.45, `${fin.minutes} min`, "de generación, sin intervención");
    // Real measured cost (llm_call of ejemplos/harness-demo.sqlite + evals/results/*/*.json).
    const real = runs.real_costs;
    const rr = real.final_by_role;
    s.addChart(pres.charts.BAR, [{ name: "USD", labels: rr.map((r) => r[0]), values: rr.map((r) => r[1]) }], {
      x: MX, y: 2.2, w: 2.15, h: 2.35, barDir: "bar", chartColors: [C.brand],
      showTitle: true, title: "Coste por rol, novela publicada (USD)", titleFontSize: 8, titleColor: C.ink, titleFontFace: F,
      showValue: true, dataLabelFontSize: 8, dataLabelColor: C.ink, dataLabelFormatCode: "0.00",
      catAxisLabelColor: C.ink2, catAxisLabelFontSize: 8, catAxisLabelFontFace: F, valAxisHidden: true,
      valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, catAxisOrientation: "maxMin",
    });
    text(s, "GASTO REAL MEDIDO", { x: MX + 2.3, y: 2.22, w: 2.1, h: 0.2, fontSize: 7.5, bold: true, color: C.acc, charSpacing: 1 });
    real.items.forEach(([k, v], i) => {
      const y = 2.44 + i * 0.25;
      const last = i === real.items.length - 1;
      text(s, k, { x: MX + 2.3, y, w: 1.5, h: 0.24, fontSize: 7.5, bold: last, color: last ? C.ink : C.ink2, valign: "middle" });
      text(s, eur(v), { x: MX + 3.75, y, w: 0.65, h: 0.24, fontSize: 7.5, bold: last, color: last ? C.acc : C.ink, align: "right", valign: "middle" });
    });
    text(s, `Novela publicada: ${eur(real.per_chapter_min)}–${eur(real.per_chapter_max)} USD por capítulo, ${fin.calls} llamadas, ${real.output_tokens.toLocaleString("es-ES")} tokens de salida. Techo por bucles acotados: el peor intento costó ${usd(worst)} y no se cobra (solo se factura lo publicado). Haiku 4.5: 1 USD/M tokens de entrada, 5 USD/M de salida.`, {
      x: MX, y: 4.58, w: 4.4, h: 0.5, fontSize: 7, color: C.muted, italic: true,
    });
    // proposal
    card(s, 5.15, 1.25, 4.35, 3.8, C.ink);
    text(s, "PROPUESTA ECONÓMICA", { x: 5.35, y: 1.36, w: 4, h: 0.22, fontSize: 8, bold: true, color: C.brand, charSpacing: 1.5 });
    const lines = [
      ["Piloto de implantación (8 semanas)", "28.800 €"],
      ["   integración con la tienda y login", "8.000 €"],
      ["   lector y PDF con marca blanca", "6.400 €"],
      ["   QA editorial: 50 novelas y calibración del juez", "7.200 €"],
      ["   RGPD: enmascarado en trazas, borrado, DPA", "4.800 €"],
      ["   formación y puesta en marcha", "2.400 €"],
      ["Plataforma (hosting, Langfuse, soporte)", "600 €/mes"],
      ["Por novela publicada (incluye 1 cambio)", "12 €"],
      ["Cambios adicionales", "2 €"],
    ];
    lines.forEach(([k, v], i) => {
      const y = 1.64 + i * 0.27;
      const sub = k.startsWith("   ");
      text(s, k.trim(), { x: 5.35 + (sub ? 0.18 : 0), y, w: 3.0, h: 0.25, fontSize: sub ? 8 : 9, bold: !sub, color: sub ? "AEB8C2" : C.white, valign: "middle" });
      text(s, v, { x: 8.3, y, w: 1.05, h: 0.25, fontSize: sub ? 8 : 9, bold: !sub, color: sub ? "AEB8C2" : C.white, align: "right", valign: "middle" });
    });
    card(s, 5.3, 4.12, 4.05, 0.8, C.ink3);
    text(s, [
      { text: "Ejemplo con PVP de 39 €: ", options: { bold: true, color: C.brand } },
      { text: "12 € a Qaracter, 27 € de margen bruto para " + CLIENT_SHORT + "; la cuota se cubre con 23 novelas al mes. Precios sin IVA; 1 USD ≈ 0,90 € (supuesto).", options: { color: C.white } },
    ], { x: 5.45, y: 4.12, w: 3.8, h: 0.8, fontSize: 8, valign: "middle" });
    s.addNotes(`[7:00–8:00] Coste medido: la novela de diez capítulos publicada costó ${usd(fin.cost_usd)} de modelo y ${fin.minutes} minutos; un cambio del lector, unos 0,94 USD. El writer es el rol más caro, luego editor y juez: son los que producen y leen más texto.\nGasto real de todo el desarrollo con modelo: ${usd(real.items[real.items.length - 1][1])}, contando los tres intentos bloqueados, las evals antes y después del tuning y el experimento de Lean.\nComo los bucles están acotados, el coste también: el peor intento medido costó ${usd(worst)}, y ese riesgo lo asumimos nosotros: solo se factura lo publicado.\nPropuesta: un piloto de ocho semanas por 28.800 euros (integración, marca blanca, QA editorial con 50 novelas y el trabajo de RGPD), 600 euros al mes de plataforma y 12 euros por novela publicada. Con un precio de venta de 39 euros, a ${CLIENT_SHORT} le quedan 27 de margen bruto.`);
  }

  // ------------------------------------------------------------ 12 · Demo
  {
    const s = base("Demo", "«La perra se llama Nala»: solo cambia lo afectado");
    const zw = 3.9, zh = 3.9 / 2.35;
    framed(s, img("v1-zoom.png"), MX, 1.35, zw, zh);
    pill(s, MX + zw - 1.8, 1.35 - 0.14, 1.65, 0.26, "versión 1 · «Canela»", { fill: C.ink, color: C.white });
    framed(s, img("v2-zoom.png"), MX, 1.35 + zh + 0.3, zw, zh);
    pill(s, MX + zw - 1.8, 1.35 + zh + 0.3 - 0.14, 1.65, 0.26, "versión 2 · «Nala»", { fill: C.brand, color: C.white });
    const steps = [
      "Petición en el lector: pet.canela.name → «Nala»",
      "fact_usage dice qué capítulos usan el hecho: 1 y 3–10",
      "Se regeneran solo esos, en la versión 2; el 2 se copia",
      "Mismos validadores; se exporta el PDF con «Novedades»",
    ];
    steps.forEach((t, i) => {
      const y = 1.35 + i * 0.5;
      badge(s, 4.85, y, String(i + 1), { size: 0.32, fs: 10 });
      text(s, t, { x: 5.3, y, w: 4.2, h: 0.32, fontSize: 9.5, valign: "middle" });
    });
    const st = [["44 → 0", "«Canela» en v1 → v2"], ["0 → 45", "«Nala» en v1 → v2"], ["v1", "intacta"], ["~27 min", "~0,94 USD"]];
    st.forEach(([b, sm], i) => {
      const x = 4.85 + i * 1.18;
      card(s, x, 3.45, 1.06, 0.9, i === 2 ? C.passT : C.brand50);
      text(s, b, { x, y: 3.52, w: 1.06, h: 0.4, fontSize: 14, bold: true, align: "center", color: i === 2 ? C.pass : C.acc, valign: "middle" });
      text(s, sm, { x: x + 0.04, y: 3.92, w: 0.98, h: 0.38, fontSize: 7.5, align: "center", color: C.ink2 });
    });
    text(s, "Misma página en ejemplos/novela-ejemplo.pdf (v1) y ejemplos/novela-ejemplo-v2-cambio-nala.pdf (v2). El índice de la v2 marca cada capítulo «(modificado)».", {
      x: 4.85, y: 4.45, w: 4.65, h: 0.5, fontSize: 8, color: C.muted, italic: true,
    });
    s.addNotes(`[8:00–8:30] DEMO. Abrir el lector en la novela de ejemplo, capítulo 1, y pedir «la perra se llama Nala» (o mostrar el PDF regenerado si no hay tiempo).\nEl sistema busca el hecho, ve en fact_usage que lo usan los capítulos 1 y 3 a 10, y regenera solo esos en la versión 2; el capítulo 2 se copia tal cual. Pasan los mismos validadores y el PDF sale con una página de novedades.\nResultado: Canela aparecía 44 veces en la versión 1 y 0 en la 2; Nala 45 veces. La versión 1 sigue intacta. Unos 27 minutos y menos de un dólar.`);
  }

  // ------------------------------------------------------------ 13 · Riesgos y siguientes pasos
  {
    const s = base("Riesgos y siguientes pasos", "Lo que aún no está demostrado y cómo lo cerramos");
    table(s, [
      ["Riesgo", "Mitigación"],
      ["Días sin fecha al lado («aquel lunes») y duraciones no se validan", "extender calendar_consistency a la prosa"],
      ["Lean solo prueba lo que el planner registra en la cronología", "evento «departure» obligatorio si el brief dice que alguien se fue"],
      ["Un brief contradictorio bloquea bien pero caro (b4: timeout de 45 min)", "prechequeo del plan más estricto; parar antes de escribir"],
      ["Fichas de personajes sin versionar (solo el nombre)", "versionar reparto por versión"],
      ["Datos personales reales en prompts y trazas", "enmascarado en Langfuse, borrado a petición y DPA (piloto)"],
      ["Juez aún no calibrado con revisión humana", "QA editorial de 50 novelas con la misma rúbrica"],
    ], { x: MX, y: 1.3, w: 5.7, colW: [3.0, 2.7], fontSize: 8, rowH: 0.42 });
    text(s, "Siguientes pasos", { x: 6.55, y: 1.3, w: 3, h: 0.28, fontSize: 12, bold: true });
    const nx = [["Semanas 1–2", "integración y RGPD"], ["Semanas 3–5", "marca blanca y 50 novelas de QA"], ["Semanas 6–7", "calibración del juez y validadores nuevos"], ["Semana 8", "lanzamiento en el catálogo de Navidad"]];
    nx.forEach(([h, d], i) => {
      const y = 1.7 + i * 0.8;
      badge(s, 6.55, y, String(i + 1), { size: 0.36, fs: 11, fill: i === 3 ? C.brand : C.ink });
      if (i < 3) s.addShape(pres.shapes.LINE, { x: 6.73, y: y + 0.38, w: 0, h: 0.4, line: { color: C.line, width: 1.5 } });
      text(s, h, { x: 7.05, y: y - 0.02, w: 2.4, h: 0.22, fontSize: 9.5, bold: true });
      text(s, d, { x: 7.05, y: y + 0.2, w: 2.4, h: 0.4, fontSize: 8.5, color: C.ink2 });
    });
    s.addNotes(`[8:30–9:30] Prefiero decir yo lo que no está demostrado: el calendario solo se valida junto a una fecha; Lean solo prueba lo que el planner registra; un brief contradictorio se bloquea bien pero caro; las fichas no están versionadas; y antes de producción hay que enmascarar los datos personales en las trazas y calibrar el juez con revisión humana.\nTodo eso está en el plan del piloto: ocho semanas hasta el catálogo de Navidad.`);
  }

  // ------------------------------------------------------------ 14 · Contraportada
  {
    const s = pres.addSlide(); pageNo += 1;
    s.background = { color: C.ink };
    s.addImage({ path: MARK, x: 6.3, y: 0.9, w: 3.2, h: 3.2 * 595 / 600, transparency: 90 });
    s.addImage({ path: LOGO_W, x: MX, y: 0.7, w: 0.5 * LOGO_R, h: 0.5 });
    text(s, "Gracias", { x: MX, y: 1.7, w: 5.5, h: 0.8, fontSize: 40, bold: true, color: C.white, valign: "middle" });
    text(s, "Separamos la verdad de la prosa: lo que es cierto sobre la historia vive en una base de datos y lo comprueban validadores, Lean y TLA+. Solo se publica lo que pasa todo.", {
      x: MX, y: 2.5, w: 5.4, h: 0.8, fontSize: 12, color: "C9D1D9",
    });
    const ct = [["Empresa", "Qaracter"], ["Contacto", STUDENT], ["Web", "qaracter.com"]];
    ct.forEach(([k, v], i) => {
      const y = 3.45 + i * 0.3;
      text(s, k.toUpperCase(), { x: MX, y, w: 1.1, h: 0.26, fontSize: 8.5, bold: true, color: C.brand, charSpacing: 1, valign: "middle" });
      text(s, v, { x: MX + 1.15, y, w: 4.5, h: 0.26, fontSize: 11, color: C.white, valign: "middle" });
    });
    text(s, "Anexo: tabla completa de evals", { x: 6.3, y: 4.85, w: 3.2, h: 0.25, fontSize: 9, color: "AEB8C2", align: "right" });
    s.addNotes(`[9:30–10:00] Si me tengo que quedar con una decisión: separar la verdad de la prosa. Lo que es cierto sobre la historia vive en una base de datos y lo comprueban validadores deterministas, Lean y TLA+; los modelos solo redactan, y solo se publica lo que pasa todo.\nMuchas gracias. En el anexo está la tabla completa de evals, y el resto del detalle en los anexos PDF; encantado de responder preguntas.`);
  }

  // ================================================================ ANEXOS
  // A4 tabla completa evals
  {
    const s = base("Anexo · Evals", "Tabla completa: validador × brief, antes y después del tuning 1", { annex: true });
    const vs = ["brief_schema", "forbidden_words_scene", "forbidden_words_chapter", "chapter_length", "exact_names", "brief_coverage", "prose_repetition", "judge_chapter", "judge_novel", "lean_chronology", "visual_check"];
    const cell = (e, n) => { const r = e.validators && e.validators[n]; if (!r) return n === "brief_schema" && e.outcome === "rejected_by_validation" ? ko() : na(); return r.passed ? ok() : ko(); };
    const rows = [["Validador", ...BRIEFS.slice(0, 3).map((b) => "antes " + b.split("-")[0]), ...BRIEFS.map((b) => "después " + b.split("-")[0])]];
    for (const n of vs) rows.push([{ text: n, options: { fontFace: "Courier New", fontSize: 7 } }, ...BRIEFS.slice(0, 3).map((b) => cell(before[b], n)), ...BRIEFS.map((b) => cell(after[b], n))]);
    rows.push([{ text: "coste USD", options: { bold: true } }, ...BRIEFS.slice(0, 3).map((b) => (before[b].cost ? eur(before[b].cost.cost_usd) : "—")), ...BRIEFS.map((b) => (after[b].cost ? eur(after[b].cost.cost_usd) : "—"))]);
    table(s, rows, { x: MX, y: 1.25, w: 9, colW: [2.1, ...Array(7).fill(6.9 / 7)], fontSize: 7.5, rowH: 0.26 });
    text(s, "b2 infantil · b3 inyección · b4 trampas temporales · b5 contradictorio (rechazado en el brief). Fuente: evals/results.md y evals/results/{before,after}/*.json. Detalle: presentacion/anexo-evals-tabla.pdf.", {
      x: MX, y: 4.72, w: 9, h: 0.3, fontSize: 7.5, color: C.muted, italic: true,
    });
    s.addNotes("Anexo: la tabla completa de evals.");
  }
  const out = path.join(ROOT, "presentacion", "presentacion-2.pptx");
  await pres.writeFile({ fileName: out });
  console.log("written", out);
}

build().catch((e) => { console.error(e); process.exit(1); });

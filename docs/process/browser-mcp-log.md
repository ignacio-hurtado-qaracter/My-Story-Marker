# Log del browser MCP (Playwright MCP)

> Registro (spec 004, D10; exam K06, V05). Qué inspeccionó el agente con el browser MCP,
> qué detectó y qué cambio provocó. Solo lo que pasó de verdad.

## Configuración

- Servidor: el de [`.mcp.json`](../../.mcp.json), `npx -y @playwright/mcp@latest
  --headless --isolated --browser chromium` (serverInfo `Playwright 1.64.0-alpha`), con
  `PLAYWRIGHT_MCP_EXECUTABLE_PATH=/opt/pw-browsers/chromium-1194/chrome-linux/chrome`.
- Cliente: [`docs/process/tools/mcp_browser_probe.py`](./tools/mcp_browser_probe.py), un
  cliente JSON-RPC por stdio (solo biblioteca estándar) que hace lo mismo que el comando
  [`/inspect-novel`](../../.claude/commands/inspect-novel.md) pero repetible y con
  transcripción.
- Herramientas MCP usadas: `initialize`, `tools/list` (25 herramientas), `browser_resize`,
  `browser_navigate`, `browser_snapshot`, `browser_evaluate`, `browser_take_screenshot`,
  `browser_console_messages`.

## Entrada 1 — 2026-09-24, novela `demo-faro`, versiones 1 y 2

**Montaje.** BD de prueba aparte (no `data/harness.sqlite`, donde se generaban dos
novelas): `HARNESS_DB=<scratch>/demo.sqlite uv run python -m app.reader.dev_seed`
(3 capítulos; v2 = cambio "el perro se llama Nala" sobre los capítulos 1 y 3). Backend
`uvicorn app.main:app --port 8010`; frontend `vite --port 5183` con
`VITE_BACKEND_URL=http://127.0.0.1:8010`. Rama `docs/process-part1` = `340ede7`.

**Qué se inspeccionó.** Las pasadas que quedan en las transcripciones son dos, escritorio
1280×900 y móvil 390×844 (antes hubo tres de puesta a punto del cliente con cinco páginas);
en cada una siete páginas y después cada enlace a capítulo encontrado en índice y fichas:

| Página | Comprobado | Escritorio | Móvil |
|---|---|---|---|
| Portada `/novelas/demo-faro` | título `h1`, destinatario, dedicatoria, enlaces "Empezar a leer" e "Índice", PDF | ✅ título "La luz de Cabo Luz", "Una novela para …", bloque *Dedicatoria* con el texto del brief | ✅ |
| Índice v2 | 3 capítulos enlazados, marca `modificado` en 1 y 3, aviso de novedades | ✅ "esta versión cambia los capítulos 1, 3 respecto a la versión 1, que se conserva" | ✅ |
| Capítulo 1 v2 | título, marca de cambio, texto, navegación | ✅ nombre nuevo en el texto, "Capítulo siguiente →" | ✅ |
| Personajes y lugares v2 | fichas de personajes y lugares con "Aparece en" | ✅ 3 personajes, 2 lugares, 10 enlaces a capítulos | ✅ |
| Índice v1 (`?v=1`) | versión anterior legible, sin marcas | ✅ enlaces conservan `?v=1` | ✅ |
| Capítulo 1 v1 | texto de la versión anterior | ✅ nombre antiguo en el texto | ✅ |
| Personajes v1 | fichas de la versión anterior | ⚠️ ver hallazgo 2 | ⚠️ |
| Enlaces a capítulo (3 distintos) | cada uno aterriza en su capítulo | ✅ 3/3 | ✅ 3/3 (uno tardó >1 s, ver hallazgo 1) |

Sin desbordamiento horizontal en ninguna página (`scrollWidth == clientWidth`: 1280/1280 y
390/390), `lang="es"`, ninguna `<img>` sin `alt`, títulos de pestaña con el nombre de la
página. El PDF de la v2 responde 200 `application/pdf` (13.807 bytes).

Capturas (`browser_take_screenshot`, página completa) y transcripciones en
[`frontend/screenshots/browser-mcp/`](../../frontend/screenshots/browser-mcp/):
`desktop-*.png`, `mobile-*.png`, `transcript-desktop.json`, `transcript-mobile.json`.

**Qué se detectó.**

1. **500 intermitente en `GET /novels/{id}` (backend).** La consola del navegador registró
   `Failed to load resource: 500` en `/api/novels/demo-faro` en 4 de las 5 pasadas completas
   que se hicieron (en la portada, el capítulo 1 o el índice v1, según la pasada). El log de uvicorn da la causa: `sqlite3.ProgrammingError: SQLite
   objects created in a thread can only be used in that same thread`. La dependencia
   `get_repository` de [`app/reader/router.py`](../../backend/app/reader/router.py) es un
   generador síncrono que abre `BibleRepository` en un hilo del threadpool, y el endpoint
   síncrono lo usa en otro; `open_authoritative` abre los ficheros con
   `check_same_thread=True` (solo `:memory:` usa `False`). Reproducido fuera del navegador:
   40 peticiones secuenciales → 40 × 200; 20 concurrentes → 12 × 500. El lector **no lo
   muestra** porque TanStack Query reintenta (3 veces, con espera), pero la página tarda
   ≥ 1 s más: en la pasada móvil el capítulo 1 aún no tenía `h1` al segundo de navegar.
   Los tests no lo ven porque `TestClient` ejecuta en un solo hilo.
   *Arreglo propuesto (no aplicado; es código de B1/B10):* abrir la conexión autoritativa
   de ficheros con `check_same_thread=False` (cada petición usa su repositorio en
   exclusiva, sin compartirlo), o que la dependencia y el endpoint corran en el mismo hilo;
   y un test que lance peticiones concurrentes contra la app real.
2. **Las fichas no son versionadas (contenido).** En `personajes?v=1` la mascota aparece
   con el nombre **nuevo**, mientras que el capítulo 1 de esa misma v1 usa el **antiguo**.
   La API lo confirma: `GET /novels/demo-faro/bible?version=1` devuelve el personaje con el
   nombre actual. Causa: `character`/`place` no tienen columna de versión; `change_fact`
   los renombra en sitio (`rename_cast`). En la semilla la descripción lo disimula
   ("(… en la versión 1)"), pero con una novela real la ficha de la versión anterior
   contradiría su propio texto. *Arreglo propuesto:* derivar el nombre mostrado del valor
   del hecho en esa versión (la nota `change` de `novel_version` guarda `old`/`new`) o
   versionar el reparto; decisión de diseño (D6, K1), así que pasa por spec.
3. **Menores.** `favicon.ico` 404 en cada carga (no hay icono en `index.html`); aviso de
   three.js `THREE.Clock … deprecated` en la portada. Sin efecto visible.

**Qué cambio provocó.** Ninguno en código ni prompts todavía: este bloque no posee
`backend/` ni `frontend/`. Los hallazgos 1 y 2 se han enviado al orquestador para que los
asigne (B1/B10). Se añadirá aquí el commit que los cierre.

## Pendiente

- Inspeccionar con el mismo cliente las dos novelas reales de la oleada C cuando estén
  publicadas (10 capítulos: índice completo, fichas del reparto real, `modificado` tras un
  `change_fact`).
- El validador `visual_check` de `pre_publish` usa Playwright directamente (no el MCP) con
  la spec `frontend/e2e/visual-check.spec.ts`; su primera ejecución está en `5d9ef24`
  (`demo-faro`, v2: 1 passed, capturas en `frontend/screenshots/visual-check/`).

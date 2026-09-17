# My-Story-Maker · Frontend

Sitio estático (sin build) para el Story Creator Harness. Tres páginas:

| Página | Fichero | Qué hace |
|--------|---------|----------|
| Crear novela | `index.html` | Formulario con todos los parámetros de `config.json` vacíos. Genera, copia y descarga el JSON. Fondo three.js (módulo en línea). |
| Biblioteca | `library.html` | Lista las novelas de `books/` con parámetros, Spirit, personajes, resúmenes, métricas del Reviewer y la novela. |
| Arquitectura | `architecture.html` | Diagrama 3D interactivo (three.js) de agentes y flujo. Clic en un nodo muestra su contrato. |

## Ejecutar

Funciona abriendo los HTML directamente (`file://`) o sirviéndolos por HTTP.

```bash
# 1. Genera el índice de la biblioteca a partir de books/
node web/scripts/build-data.mjs

# 2. Sirve la carpeta web/
npx serve web
# o
python -m http.server 8080 --directory web
```

Abre http://localhost:3000 (serve) o http://localhost:8080.

## Logo

La cabecera carga `assets/Logo_Qaracter.svg`. Si no existe, usa `assets/qaracter-logo.svg`
(una recreación vectorial). El logo oficial está en `web/assets/Logo_Qaracter.svg`.

## Datos de la biblioteca y actualización automática

`scripts/build-data.mjs` recorre `books/<slug>/` y escribe `data/books.json` y `data/books.js` (el mismo contenido como script, para `file://`) con:
`run.json` (config_snapshot, totales, estado), `metrics.jsonl`, el YAML de `spirit.md` y
`characters.md` parseado, los resúmenes de `summaries/`, y `novel.md`.

La biblioteca se mantiene al día sola por dos vías:

1. **Hooks de Claude Code** (`.claude/settings.json`): tras cada `Write`/`Edit` del harness y al
   terminar cada turno se ejecuta `node web/scripts/build-data.mjs --quiet`, así `data/books.js`
   siempre refleja lo que hay en `books/`. Si los hooks no se activan en una sesión ya abierta,
   ejecuta `/hooks` una vez o reinicia Claude Code para que cargue la configuración.
2. **Sondeo en la página**: `library.html` recarga `data/books.js` cada 5 s (con cache-busting) y
   re-renderiza solo si algo cambió, mostrando un aviso cuando aparece una novela nueva. Funciona
   también abriendo el HTML desde disco. El botón «Actualizar ahora» fuerza una comprobación.

Alternativa por HTTP: `node web/scripts/serve.mjs [puerto]` sirve `web/` y genera los datos en vivo
desde `books/` en cada petición, sin depender de los hooks.

## Dependencias (CDN)

- three.js 0.160 (`cdn.jsdelivr.net/npm/three`), con OrbitControls y CSS2DRenderer.
- marked 12 para renderizar Markdown en la biblioteca.
- Fuentes Inter y JetBrains Mono desde Google Fonts.

# Presentación técnico-comercial

**Idioma: español.**

Presentación formal de My Story Marker como solución técnico-comercial: el problema del
cliente (novelas personalizadas para regalar), el harness que las genera y la evidencia de
que funciona. El deck y los anexos se generan con scripts desde los ficheros del
repositorio, así que se pueden reconstruir tras cada ejecución (por ejemplo, después de la
novela final o de la iteración de tuning) y sus cifras no se quedan viejas.

## Contenido

| Fichero | Qué es |
|---|---|
| [`presentacion.pptx`](./presentacion.pptx) | Deck principal, formato editable (PowerPoint), 20 diapositivas; **cada una lleva su guion en las notas del orador** |
| [`presentacion.pdf`](./presentacion.pdf) | El mismo deck en PDF (convertido con LibreOffice) |
| [`guion.md`](./guion.md) | **Guion de la presentación** (≈ 14–15 min): por diapositiva, mensaje clave, qué decir, cifras que mencionar y transición; después, las preguntas probables del tribunal con respuestas cortas y la frase para el email. Se genera con el deck, desde los mismos datos |
| [`anexo-arquitectura.pdf`](./anexo-arquitectura.pdf) | Arquitectura del harness: roles, validadores y su punto de ejecución, esquema SQLite de la story bible, máquina de estados, oleadas de construcción (diagramas Mermaid renderizados desde `docs/process/diagramas.md`) |
| [`anexo-tla-spec.pdf`](./anexo-tla-spec.pdf) | Especificación TLA+ completa (`.tla` y `.cfg`), propiedades, correspondencia acción → código, salida de TLC y los contraejemplos CE1–CE4 |
| [`anexo-lean-invariantes.pdf`](./anexo-lean-invariantes.pdf) | Modelo Lean 4 de la cronología (`Basic.lean`), los cuatro invariantes, cronologías de ejemplo y el caso real (L04) |
| [`anexo-evals-tabla.pdf`](./anexo-evals-tabla.pdf) | Cinco briefs × validadores, tuning 1 antes/después, novelas completas (3 y 10 capítulos) y tuning 2, coste y latencia por ejecución y por capítulo |
| [`anexo-revision-humana.pdf`](./anexo-revision-humana.pdf) | Protocolo de revisión humana, la rúbrica del juez y la plantilla en blanco. **La revisión en sí la hace el autor (pendiente)**; cuando exista `evals/human-review/review-*.yaml` y su `comparison-*.md`, el anexo los incluye al reconstruirse |
| [`build/`](./build/) | Scripts de generación (`build_deck.py`, `build_annexes.py`, `common.py`), los datos de las novelas (`build/data/runs.json`) y las imágenes (`build/img/*.png`: diagramas y páginas de la novela de ejemplo) |

### Diapositivas

Narrativa: problema → solución → cómo funciona → cómo sabemos que funciona → resultados y
coste → decisiones → limitaciones → cierre.

1. Portada · 2. Problema y propuesta de valor (D11) · 3. Demo: portada, índice, fichas y el
cambio «el perro se llama Nala» · 4. Arquitectura y roles · 5. Memoria: story bible SQLite ·
6. Validadores (cuatro tipos, punto de ejecución; `calendar_consistency`, linter X02) ·
7. Guardrails y texto libre no confiable · 8. Lean 4 y el caso real L04 · 9. TLA+: máquina
de estados, invariantes, TLC · 10. Contraejemplos CE1–CE4 · 11. Langfuse · 12. Evals y
tuning 1 (0/3 → 2/3 publicadas) · 13. Seguridad (X04) y opcionales X01 MCP, X02 linter,
X03 login · 14. Novelas de 10 capítulos bloqueadas → tuning 2 (calendario) · 15. Novela de
ejemplo · 16. Coste y latencia · 17. Uso de Claude Code · 18. Decisiones y trade-offs ·
19. Limitaciones y siguientes pasos · 20. La decisión de diseño más importante.

## Decisión de diseño más importante

> Separar la verdad (story bible SQLite + validadores deterministas + Lean/TLA+) de la
> prosa generada, con un bucle acotado planner → writer → editor → juez que solo publica
> versiones que pasan todos los validadores.

La versión en una frase para el email de entrega está al final de [`guion.md`](./guion.md).

## Vídeo de demo

Enlace: **pendiente — enlace a añadir por el autor**. Si el fichero supera el límite de
GitHub se enlaza aquí y desde el [README raíz](../README.md); si no, se sube a esta carpeta.

## Cómo reconstruir

Desde la raíz del repositorio:

```bash
# deck (pptx + pdf) y guion.md
uvx --with python-pptx --with pymupdf python presentacion/build/build_deck.py
# anexos
uvx --with markdown python presentacion/build/build_annexes.py
```

Todo es **data-driven**: ninguna cifra final está escrita en el script. Qué lee cada uno en
vivo: `build/data/runs.json` (novelas), `evals/results.md` y `evals/results/*/*.json`
(resultados, coste, versiones de prompt), `evals/results/tuning.md`,
`docs/process/iteraciones.md` (tuning 2), `docs/process/lean-caso-real.md`,
`docs/process/red-team-log.md`, `docs/security-report.md`, `formal/tla/tlc-output.txt`,
`GiftNovelHarness.cfg` y `COUNTEREXAMPLES.md`, `backend/app/novel/pipeline.py` (límites de
reintentos), `ejemplos/*.pdf` y `evals/human-review/`. Si un fichero falta o un campo es
`null`, la diapositiva, el guion o el anexo dicen **pendiente** y se completan solos al
volver a ejecutar el script.

### `build/data/runs.json`: la novela final

Cifras de las novelas completas, tomadas de los logs de la CLI (`data/logs/<novel_id>.log`:
`cost so far`, llamadas, tiempo de modelo, palabras por capítulo) y de los commits citados:

| Clave | Contenido |
|---|---|
| `three_chapter_novel` | la novela de 3 capítulos publicada (`novela-infantil`, 0,85 USD, 3.409 palabras, 1 ronda, 21 min) |
| `ten_chapter_attempts[]` | los dos intentos de 10 capítulos bloqueados: `status`, `validator`, `why`, `chapters_written`, `repair_rounds`, `calls`, `cost_usd`, `minutes`, `model_time_s`, `motivated` (tuning 1 / tuning 2) |
| `final_novel` | **la novela final (la rellena el orquestador)**: `novel_id`, `status` (`published` · `blocked` · `stopped_error`), `version`, `chapters`, `words` (suma de los capítulos publicados), `repair_rounds`, `calls`, `cost_usd`, `minutes` (de reloj, creación → resultado en el log), `judge_novel` (veredicto corto, p. ej. «aprueba, media 4,2»), `pdf` (`ejemplos/novela-ejemplo.pdf`) |

Al terminar la novela de 10 capítulos, el orquestador:

1. exporta el PDF de la versión publicada a `ejemplos/novela-ejemplo.pdf`;
2. rellena `final_novel` en `build/data/runs.json` con los datos del log;
3. ejecuta los dos comandos de arriba (deck + guion, y anexos) y commitea el resultado.

Con `final_novel.status = "published"` y el PDF presente, la diapositiva 15 muestra la
portada, el índice y el capítulo 1 de esa novela con sus cifras, la 14 marca el intento
final como publicado, la 16 usa su coste y tiempo, y el guion y las preguntas cambian de
redacción. Si queda bloqueada, se muestra como tal (sigue siendo evidencia de que no se
publica nada sin validar).

Requisitos y opciones:

- **PDF del deck:** LibreOffice con Impress (`soffice`; en Debian/Ubuntu
  `apt-get install libreoffice-impress`) y, para que el PDF respete las métricas de
  Calibri/Cambria, `fonts-crosextra-carlito fonts-crosextra-caladea`. `--no-pdf` genera
  solo el `.pptx`; `--no-guion` no reescribe `guion.md`.
- **Páginas de la novela:** con PyMuPDF (`--with pymupdf`) se renderizan desde el PDF de
  `ejemplos/` a `build/img/novela-*.png`; sin él se usan los PNG versionados.
- **Anexos:** Chromium headless (se busca en `CHROME_PATH`, `/opt/pw-browsers/chromium-*`
  o el `PATH`). `--only tla,lean,evals,revision,arquitectura` genera una parte.
- **Diagramas:** los bloques Mermaid se renderizan con `npx @mermaid-js/mermaid-cli` y se
  cachean en `build/img/` por hash de su fuente; sin `npx` se usan los PNG versionados.
  `--render` fuerza el renderizado.
- El guion (`guion.md`) y las notas del orador salen del mismo código
  (`Script` en `build_deck.py`): para cambiar lo que se dice, edita el script y reconstruye.

## Relacionado

- Novela de ejemplo: [`../ejemplos/`](../ejemplos/README.md)
- Documentación de proceso: [`../docs/process/`](../docs/process/README.md)

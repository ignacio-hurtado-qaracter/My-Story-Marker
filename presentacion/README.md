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
| [`presentacion.pptx`](./presentacion.pptx) | Deck principal, formato editable (PowerPoint), 19 diapositivas con notas del orador |
| [`presentacion.pdf`](./presentacion.pdf) | El mismo deck en PDF (convertido con LibreOffice) |
| [`anexo-arquitectura.pdf`](./anexo-arquitectura.pdf) | Arquitectura del harness: roles, validadores y su punto de ejecución, esquema SQLite de la story bible, máquina de estados, oleadas de construcción (diagramas Mermaid renderizados desde `docs/process/diagramas.md`) |
| [`anexo-tla-spec.pdf`](./anexo-tla-spec.pdf) | Especificación TLA+ completa (`.tla` y `.cfg`), propiedades, correspondencia acción → código, salida de TLC y los contraejemplos CE1–CE4 |
| [`anexo-lean-invariantes.pdf`](./anexo-lean-invariantes.pdf) | Modelo Lean 4 de la cronología (`Basic.lean`), los cuatro invariantes, cronologías de ejemplo y el caso real (L04) o su estado |
| [`anexo-evals-tabla.pdf`](./anexo-evals-tabla.pdf) | Cinco briefs × validadores, iteración de tuning antes/después, coste y latencia por ejecución y por capítulo |
| [`anexo-revision-humana.pdf`](./anexo-revision-humana.pdf) | Protocolo de revisión humana, la rúbrica del juez y la plantilla en blanco. **La revisión en sí la hace el autor (pendiente)**; cuando exista `evals/human-review/review-*.yaml` y su `comparison-*.md`, el anexo los incluye al reconstruirse |
| [`build/`](./build/) | Scripts de generación (`build_deck.py`, `build_annexes.py`, `common.py`) y los diagramas renderizados (`build/img/*.png`) |

### Diapositivas

1. Portada · 2. Problema y propuesta de valor (D11) · 3–4. Demo del producto (portada,
índice, fichas; cambio «el perro se llama Nala» y PDF con novedades) · 5. Arquitectura y
roles · 6. Memoria: story bible SQLite · 7. Validadores (tipos y punto de ejecución) ·
8. Guardrails y policy · 9. Lean 4 · 10. TLA+: máquina de estados, invariantes, TLC ·
11. Contraejemplos CE1–CE4 · 12. Observabilidad con Langfuse · 13. Evals y tuning ·
14. Red-team · 15. Uso de Claude Code · 16. Coste y latencia · 17. Decisiones y
trade-offs · 18. Limitaciones y siguientes pasos · 19. La decisión de diseño más importante.

## Decisión de diseño más importante

> Separar la verdad (story bible SQLite + validadores deterministas + Lean/TLA+) de la
> prosa generada, con un bucle acotado planner → writer → editor → juez que solo publica
> versiones que pasan todos los validadores.

## Vídeo de demo

Enlace: **pendiente — enlace a añadir por el autor**. Si el fichero supera el límite de
GitHub se enlaza aquí y desde el [README raíz](../README.md); si no, se sube a esta carpeta.

## Cómo reconstruir

Desde la raíz del repositorio:

```bash
# deck (pptx + pdf)
uvx --with python-pptx --with matplotlib python presentacion/build/build_deck.py
# anexos
uvx --with markdown python presentacion/build/build_annexes.py
```

Qué lee cada uno en vivo: `evals/results.md`, `evals/results/*/*.json` (resultados, coste,
versiones de prompt), `evals/results/tuning.md`, `formal/tla/tlc-output.txt`,
`formal/tla/GiftNovelHarness.cfg`, `formal/tla/COUNTEREXAMPLES.md`,
`docs/process/red-team-log.md`, `docs/process/lean-caso-real.md` y
`evals/human-review/`. Si un fichero aún no existe, la diapositiva o el anexo lo marca como
pendiente y se completa solo al volver a ejecutar el script.

Requisitos y opciones:

- **PDF del deck:** LibreOffice con Impress (`soffice`; en Debian/Ubuntu
  `apt-get install libreoffice-impress`) y, para que el PDF respete las métricas de
  Calibri/Cambria, `fonts-crosextra-carlito fonts-crosextra-caladea`. `--no-pdf` genera
  solo el `.pptx`.
- **Anexos:** Chromium headless (se busca en `CHROME_PATH`, `/opt/pw-browsers/chromium-*`
  o el `PATH`). `--only tla,lean,evals,revision,arquitectura` genera una parte.
- **Diagramas:** los bloques Mermaid se renderizan con `npx @mermaid-js/mermaid-cli` y se
  cachean en `build/img/` por hash de su fuente; sin `npx` se usan los PNG versionados.
  `--render` fuerza el renderizado.
- Las cifras de coste por novela de 10 capítulos son una **estimación** a partir de los
  capítulos medidos en las evals; se recalculan al reconstruir.

## Relacionado

- Novela de ejemplo: [`../ejemplos/`](../ejemplos/README.md)
- Documentación de proceso: [`../docs/process/`](../docs/process/README.md)

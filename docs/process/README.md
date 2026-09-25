# Documentación de proceso

Esta carpeta es un **área de registro** (spec 004, decisión D10): cuenta cómo se razonó y
qué pasó, y cita el diseño en `docs/` ([arquitectura](../architecture.md),
[definiciones](../definitions.md), [verificación](../verification.md)) sin definirlo. Si una página empieza a
decir cómo funciona el sistema, esa afirmación se mueve al documento de diseño que la
posee. Se edita sin Process 1; commits con prefijo `docs(process):`.

Las páginas se escriben en la fase de cierre del bloque B12
([spec 016](../../specs/016-repo-process-presentation/016-repo-process-presentation.md)).
Los resultados de los evals, las dos iteraciones de tuning y la novela de ejemplo publicada
están en el [registro de iteraciones](./iteraciones.md#evals-y-tuning). Lo que queda en
manos del autor está al final, en [Pendiente para el autor](#pendiente-para-el-autor).

## Índice

Orden de lectura recomendado:

| # | Página | Contenido |
|---|---|---|
| 1 | [Spec inicial](./spec-inicial.md) | Qué se decidió construir y por qué, antes del código: la confrontación de la spec 004, decisiones D1–D11, bloques, oleadas y desviaciones V1–V6 |
| 2 | [Trade-offs](./trade-offs.md) | Cada decisión como opciones, criterios y elección: single- vs multi-agent, story bible, modelo de lectura, TLA+ con el flujo real, invariantes de Lean, `claude -p`, Haiku, 3 escenas, severidad del juez, normalización, verificación ligera, worktrees |
| 3 | [Explainers](./explainers/README.md) | Un explainer breve por concepto del curso aplicado (20), cada uno con su ruta al código |
| 4 | [Diagramas](./diagramas.md) | Arquitectura del harness, máquina de estados TLA+ (`stateDiagram`), esquema SQLite (`erDiagram`), validadores con su punto de ejecución |
| 5 | [Subagentes, comandos y skills](./subagentes-comandos-skills.md) | Orquestador y subagentes por bloque, comandos de [`.claude/commands/`](../../.claude/commands/), skills de [`.claude/skills/`](../../.claude/skills/README.md) (incluida la creada, [`gift-novel-run`](../../.claude/skills/gift-novel-run/SKILL.md)), memoria, hooks y MCP |
| 6 | [Log del browser MCP](./browser-mcp-log.md) | Uso real de Playwright MCP ([`.mcp.json`](../../.mcp.json)) sobre el lector: qué inspeccionó, qué detectó, qué cambio provocó |
| 7 | [Registro de iteraciones](./iteraciones.md) | Causa → efecto: contraejemplos de TLC, ejecuciones en vivo, Lean, schemathesis; evals, tuning 1 y 2, novela de ejemplo publicada y cambio del lector |
| 8 | [Red-team log](./red-team-log.md) | Casos adversariales, qué defensa los detectó y cómo se resolvió |

Herramienta: [`tools/mcp_browser_probe.py`](./tools/mcp_browser_probe.py), el cliente
JSON-RPC por stdio que conduce Playwright MCP para el log del browser MCP; sus capturas y
transcripciones están en [`frontend/screenshots/browser-mcp/`](../../frontend/screenshots/browser-mcp/).

## Pendiente para el autor

Lo que el programa 004 no puede cerrar por sí mismo (spec 004, AC 9). El comprobador del
examen da 71/72; lo único que le falta es el vídeo.

1. **Grabar el vídeo de demo** (P05) y enlazarlo desde el [README raíz](../../README.md#enlaces)
   y [`presentacion/README.md`](../../presentacion/README.md), o dejarlo en
   `presentacion/`. Guion: [`presentacion/guion.md`](../../presentacion/guion.md).
2. **Revisión humana** de una novela completa (S02): leer
   [`ejemplos/novela-ejemplo.pdf`](../../ejemplos/novela-ejemplo.pdf), rellenar una copia
   de [`evals/human-review/review-template.yaml`](../../evals/human-review/review-template.yaml)
   con la rúbrica de [`rubrica.md`](../../evals/human-review/rubrica.md) y compararla con el
   juez: `cd backend && uv run python ../evals/human-review/compare.py REVISION.yaml
   --novel-id novela-ejemplo-a --version 1`. Cierra la spec 011 en su parte manual y la
   AC 9 de la 004.
3. **Rotar la clave de Langfuse**: estuvo en claro fuera del repositorio durante el
   programa (spec 004, *Open questions*). Ningún fichero versionado la contiene.
4. ~~**Decidir sobre `backend/tests/test_boundaries_mirror.py`**~~ — **resuelto** (2026-09-25,
   opción 1 aprobada por el autor): exenciones fichero a fichero en `tools/check_boundaries.py`
   y `semgrep/forbidden-store-write.yaml`, commit `138add6`. Suite completa: 1760 pasan, 0 fallan.
5. **Enviar el correo de entrega** con el enlace al repositorio, al PDF de ejemplo, a la
   presentación y al vídeo.
6. **Repositorio MyFactory**: preparar o enlazar el repositorio de MyFactory que pide la
   entrega.

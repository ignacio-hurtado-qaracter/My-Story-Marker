# Documentación de proceso

Esta carpeta es un **área de registro** (spec 004, decisión D10): cuenta cómo se razonó y
qué pasó, y cita el diseño en `docs/` ([arquitectura](../architecture.md),
[definiciones](../definitions.md), [verificación](../verification.md)) sin definirlo. Si una página empieza a
decir cómo funciona el sistema, esa afirmación se mueve al documento de diseño que la
posee. Se edita sin Process 1; commits con prefijo `docs(process):`.

Las páginas se escriben en la fase de cierre del bloque B12
([spec 016](../../specs/016-repo-process-presentation/016-repo-process-presentation.md)).
Lo que depende de la ejecución de los evals (bloque B11) está marcado como **pendiente**.

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
| 7 | [Registro de iteraciones](./iteraciones.md) | Causa → efecto: contraejemplos de TLC, ejecuciones en vivo, Lean, schemathesis; evals y tuning pendientes |
| 8 | [Red-team log](./red-team-log.md) | Casos adversariales, qué defensa los detectó y cómo se resolvió |

Herramienta: [`tools/mcp_browser_probe.py`](./tools/mcp_browser_probe.py), el cliente
JSON-RPC por stdio que conduce Playwright MCP para el log del browser MCP; sus capturas y
transcripciones están en [`frontend/screenshots/browser-mcp/`](../../frontend/screenshots/browser-mcp/).

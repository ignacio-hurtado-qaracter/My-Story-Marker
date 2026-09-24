# Documentación de proceso

Esta carpeta es un **área de registro** (spec 004, decisión D10): cuenta cómo se razonó y
qué pasó, y cita el diseño en `docs/` ([arquitectura](../architecture.md),
[definiciones](../definitions.md), [verificación](../verification.md)) sin definirlo. Si una página empieza a
decir cómo funciona el sistema, esa afirmación se mueve al documento de diseño que la
posee. Se edita sin Process 1; commits con prefijo `docs(process):`.

Las páginas se completan en la fase de cierre del bloque B12
([spec 016](../../specs/016-repo-process-presentation/016-repo-process-presentation.md)).

## Índice

| Página | Contenido | Estado |
|---|---|---|
| `spec-inicial.md` | Qué se decidió construir y por qué, antes de escribir código (specs 001 y 004) | pendiente |
| `trade-offs.md` | Cada decisión como opciones, criterios y elección: single- vs multi-agent, formato de la story bible, modelo de lectura, integración de TLA+ con el flujo real, invariantes de Lean priorizados | pendiente |
| `explainers/` | Un explainer breve por cada concepto del curso aplicado | pendiente |
| `diagramas.md` | Arquitectura del harness, máquina de estados TLA+ (`stateDiagram`), esquema SQLite (`erDiagram`), tabla de validadores con su punto de ejecución | pendiente |
| `iteraciones.md` | Registro de iteraciones: qué cambió tras cada eval, contraejemplo de TLC o fallo de Lean, con causa y efecto | pendiente |
| `red-team.md` | Casos adversariales probados, qué validador los detectó (o no) y cómo se resolvió | pendiente |
| `browser-mcp-log.md` | Uso real del browser MCP (Playwright MCP, [`.mcp.json`](../../.mcp.json)): qué inspeccionó el agente, qué detectó y qué cambio provocó | pendiente |
| `subagentes-y-comandos.md` | Subagentes usados y comandos propios de [`.claude/commands/`](../../.claude/commands/), con propósito y resultado | pendiente |
| `skills.md` | Skills usadas o creadas, en [`.claude/skills/`](../../.claude/skills/README.md), incluida la del harness [`gift-novel-run`](../../.claude/skills/gift-novel-run/SKILL.md) | pendiente |

## Artefactos de Claude Code ya versionados

- Comandos: [`generate-novel`](../../.claude/commands/generate-novel.md),
  [`inspect-novel`](../../.claude/commands/inspect-novel.md),
  [`exam-gap`](../../.claude/commands/exam-gap.md),
  [`change-fact`](../../.claude/commands/change-fact.md).
- Memoria: [`project.md`](../../.claude/memory/project.md),
  [`conventions.md`](../../.claude/memory/conventions.md).
- Skill del harness: [`.claude/skills/gift-novel-run/`](../../.claude/skills/gift-novel-run/SKILL.md).
- Configuración MCP: [`.mcp.json`](../../.mcp.json) con Playwright MCP.

Su uso real (qué se ejecutó y con qué resultado) se registra en las páginas de arriba, no
aquí.

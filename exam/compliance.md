# Cumplimiento del examen

Generado por `python exam/check.py` a partir de `exam/requirements.toml`. No se edita a mano.

Las comprobaciones son heurísticas: ✅ dice que el artefacto existe, no que sea bueno.

**Obligatorios comprobables cumplidos: 12 de 72.**

Leyenda: ✅ cumple · 🟡 parcial · ❌ falta · 📝 manual · 📝✅ existe, revisar a mano

## Resumen por bloque

| Bloque | ✅ | 🟡 | ❌ | 📝 |
|---|---|---|---|---|
| Entregables | 3 | 0 | 2 | 3 |
| Presentación | 1 | 0 | 4 | 0 |
| Claude Code | 2 | 1 | 3 | 0 |
| 1. Configuración | 0 | 0 | 4 | 0 |
| 2. Lectura | 0 | 0 | 7 | 0 |
| 3. Harness | 1 | 0 | 4 | 1 |
| 4. Memoria | 0 | 0 | 4 | 0 |
| 5a. Programáticos | 0 | 1 | 5 | 0 |
| 5b. Semánticos | 0 | 0 | 2 | 0 |
| 5c. Lean 4 | 0 | 0 | 4 | 0 |
| 5d. TLA+ | 0 | 0 | 5 | 0 |
| Evaluación | 0 | 0 | 3 | 0 |
| 6. Observabilidad | 1 | 0 | 2 | 0 |
| 7. Guardrails | 1 | 0 | 4 | 1 |
| Docs de proceso | 1 | 1 | 4 | 0 |
| Opcionales | 1 | 0 | 3 | 0 |

## Entregables

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| E01 | ✅ | README.md en la raíz del repo | ✓ exists: README.md |
| E02 | ❌ | Brief de ejemplo reproducible, citado desde el README (provisional: ejemplos/brief-ejemplo.json) | ✗ 0 file(s) for ejemplos/brief-ejemplo.* (need 1)<br>✗ /brief-ejemplo/ found 0x in README.md (need 1) |
| E03 | ✅ | .env.example versionado | ✓ exists: backend/.env.example |
| E04 | ✅ | Sin API keys ni tokens en ningún fichero versionado | ✓ no match in tracked files |
| E05 | ❌ | Novela de ejemplo completa de 10 capítulos en PDF | ✗ missing: ejemplos/novela-ejemplo.pdf |
| E06 | 📝✅ | CLAUDE.md en la raíz, cuidado y legible (se puntúa) | ✓ exists: CLAUDE.md |
| E07 | 📝 | Repositorio MyFactory: commit final enlazado | — |
| E08 | 📝 | Email de entrega con los dos enlaces a commit y la frase de decisión de diseño (máx. 3 líneas) | — |

## Presentación

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| P01 | ✅ | presentacion/README.md con el contenido y el idioma elegido | ✓ exists: presentacion/README.md<br>✓ /(?i)idioma/ in presentacion/README.md |
| P02 | ❌ | Deck principal en PDF | ✗ 0 file(s) for presentacion/*.pdf (need 1) |
| P03 | ❌ | Deck en formato editable (pptx, key, odp) | ✗ 0 file(s) for presentacion/*.pptx \| presentacion/*.key \| presentacion/*.odp (need 1) |
| P04 | ❌ | Anexos como ficheros individuales con nombre descriptivo (anexo-*.pdf) | ✗ 0 file(s) for presentacion/anexo-*.pdf (need 1) |
| P05 | ❌ | Vídeo de demo en presentacion/ o enlazado desde el README | ✗ 0 file(s) for presentacion/*.mp4 \| presentacion/*.mov \| presentacion/*.webm (need 1)<br>✗ /(?i)https?://\S*(loom\.com\|youtu\.?be\|vimeo\.com\|drive\.google)/ found 0x in README.md \| presentacion/README.md (need 1) |

## Claude Code

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| K01 | ✅ | Comandos personalizados versionados en .claude/commands/ | ✓ 1 file(s) for .claude/commands/*.md (need 1) |
| K02 | ❌ | Ficheros de memoria versionados en .claude/ (provisional: .claude/memory/) | ✗ 0 file(s) for .claude/memory/*.md (need 1) |
| K03 | ✅ | Configuración MCP con un servidor de inspección de navegador | ✓ /(?i)(playwright\|chrome)/ in .mcp.json |
| K04 | 🟡 | Skills del desarrollo en el repo y referenciadas desde /docs | ✓ 4 file(s) for .claude/skills/*/SKILL.md (need 1)<br>✗ /\.claude/skills/ found 0x in docs/**/*.md (need 1) |
| K05 | ❌ | Subagentes y comandos propios documentados en /docs con propósito y resultado | ✗ /(?i)(subagent\|\.claude/commands\|\.claude/agents)/ found 0x in docs/**/*.md (need 1) |
| K06 | ❌ | Uso real del browser MCP documentado: qué inspeccionó, qué detectó, qué cambió | ✗ /(?i)(playwright mcp\|browser mcp\|chrome mcp)/ found 0x in docs/**/*.md (need 1) |

## 1. Configuración

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| C01 | ❌ | Agente entrevistador: nombre, edad, rasgos, recuerdos, género, tono, extensión y temas vetados | ✗ /(?i)interview/ found 0x in backend/app/**/*.py (need 1) |
| C02 | ❌ | Brief estructurado y validado con schema | ✗ 0 file(s) for backend/schemas/brief*.json (need 1) |
| C03 | ❌ | Detecta datos que faltan y al menos un tipo de contradicción (edad frente a género o tono) | ✗ /(?i)contradict/ found 0x in backend/app/brief/**/*.py \| backend/app/interview/**/*.py (need 1) |
| C04 | ❌ | Texto libre pegado por el usuario tratado como no confiable, con hechos extraídos | ✗ /(?i)untrusted/ found 0x in backend/app/**/*.py (need 1) |

## 2. Lectura

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| R01 | ❌ | Lector web (frontend) o PDF interactivo | ✗ 0 file(s) for frontend/src/**/*.tsx \| backend/app/**/pdf*.py \| backend/app/**/export*.py (need 1) |
| R02 | ❌ | Índice de capítulos navegable | ✗ /(?i)(table.?of.?contents\|\btoc\b\|índice)/ found 0x in frontend/src/**/*.tsx \| backend/app/**/*.py (need 1) |
| R03 | ❌ | Ficha de personajes y lugares desde la story bible, con enlaces al capítulo donde aparecen | ✗ /(?i)(character.?sheet\|ficha\|glossary\|dramatis)/ found 0x in frontend/src/**/*.tsx \| backend/app/**/*.py (need 1) |
| R04 | ❌ | Portada con dedicatoria personalizada | ✗ /(?i)dedicat/ found 0x in frontend/src/**/*.tsx \| backend/app/**/*.py (need 1) |
| R05 | ❌ | Cambio pedido por el lector: identifica capítulos que usan el hecho y regenera solo esos | ✗ /(?i)change.?request/ found 0x in backend/app/**/*.py (need 1) |
| R06 | ❌ | Se marcan los capítulos cambiados (web) o hay página de novedades (PDF) | ✗ /(?i)(changed_chapters\|novedades\|what.?s.?new)/ found 0x in frontend/src/**/*.tsx \| backend/app/**/*.py (need 1) |
| R07 | ❌ | Se conserva la versión anterior de la novela | ✗ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*version/ found 0x in backend/app/**/*.sql (need 1) |

## 3. Harness

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| H01 | ❌ | Tres roles como mínimo (planner, writer, editor/critic) invocados por un orquestador | ✗ /(?i)def (plan\|write\|revise\|critique\|edit\|audit)\w*\(/ found 1x in backend/app/agents/**/*.py (need 3) |
| H02 | 📝✅ | Una skill reutilizable propia del harness | ✓ 4 file(s) for .claude/skills/*/SKILL.md (need 1) |
| H03 | ❌ | Hook de validación de capítulo | ✗ /(?i)chapter/ found 0x in .claude/settings.json \| .claude/hooks/* (need 1) |
| H04 | ❌ | Hook de policy | ✗ /(?i)policy/ found 0x in .claude/settings.json \| .claude/hooks/* (need 1) |
| H05 | ✅ | Tools con schema validado | ✓ /(?i)(def toolset_for\|tool_schema\|input_schema)/ in backend/app/commons/permissions/toolsets.py |
| H06 | ❌ | Retries con límite, usados por el orquestador | ✗ /TURN_MAX_REVISIONS\|MAX_RETRIES\|max_attempts/ found 0x in backend/app/agents/**/*.py (need 1) |

## 4. Memoria

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| M01 | ❌ | Story bible en SQLite: cada hecho registra en qué capítulos se usa | ✗ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*fact/ found 0x in backend/app/**/*.sql (need 1) |
| M02 | ❌ | Tabla de cronología en SQLite (eventos, momento, personajes, lugar) | ✗ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*(chrono\|event\|timeline)/ found 0x in backend/app/**/*.sql (need 1) |
| M03 | ❌ | Resúmenes por capítulo que alimentan el contexto de los siguientes | ✗ /(?i)def \w*(digest\|summar\|rollup)\w*\(/ found 0x in backend/app/agents/**/*.py (need 1) |
| M04 | ❌ | Checkpoint por capítulo y reanudación desde el último completado | ✗ /(?i)(checkpoint\|def resume)/ found 0x in backend/app/**/*.py (need 1) |

## 5a. Programáticos

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| V01 | ❌ | Longitud de cada capítulo dentro del rango (1.000–1.500 palabras) | ✗ /(?i)(word_range\|min_words\|max_words)/ found 0x in backend/app/**/*.py (need 1) |
| V02 | ❌ | Nombre del destinatario y personajes escritos exactamente como en la story bible | ✗ /(?i)(exact_name\|name_spelling)/ found 0x in backend/app/**/*.py (need 1) |
| V03 | ❌ | Cada elemento personalizado obligatorio del brief aparece en algún capítulo (contra SQLite) | ✗ /(?i)(brief_coverage\|required_element)/ found 0x in backend/app/**/*.py (need 1) |
| V04 | 🟡 | Schema del brief y de la salida de cada rol validados | ✓ /class \w+Output\(/ in backend/app/commons/schemas/role_outputs.py<br>✗ 0 file(s) for backend/schemas/brief*.json (need 1) |
| V05 | ❌ | Validación visual con browser MCP: índice, ficha y portada renderizan; fallos vuelven al rol | ✗ /(?i)(playwright mcp\|browser mcp\|chrome mcp)/ found 0x in docs/process/**/*.md (need 1) |
| V06 | ❌ | Cada validador tiene nombre, punto de ejecución y envía su resultado a Langfuse como score | ✗ /(?i)(create_score\|score_current\|\.score\()/ found 0x in backend/app/**/*.py (need 1) |

## 5b. Semánticos

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| S01 | ❌ | LLM-as-judge con rúbrica (continuidad, tono, calidad narrativa, personalización natural), nota y justificación por criterio | ✗ /(?i)rubric/ found 0x in backend/app/**/*.py \| backend/app/**/*.md (need 1) |
| S02 | ❌ | Revisión humana de una novela completa con la misma rúbrica, comparada con el juez | ✗ /(?i)(human review\|revisión humana)/ found 0x in docs/process/**/*.md \| evals/**/*.md (need 1) |

## 5c. Lean 4

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| L01 | ❌ | Generador del fichero Lean con los hechos temporales, a partir de SQLite | ✗ /(?i)\.lean\b/ found 0x in backend/app/**/*.py \| formal/**/*.py (need 1) |
| L02 | ❌ | Proyecto Lean con al menos dos invariantes | ✗ 0 file(s) for formal/lean/**/lakefile.* (need 1)<br>✗ /(?m)^(theorem\|def)\s/ found 0x in formal/lean/**/*.lean (need 2) |
| L03 | ❌ | lake build automático; si falla, la versión no se publica y el fallo vuelve al editor | ✗ /lake/ found 0x in backend/app/**/*.py (need 1) |
| L04 | ❌ | Caso real detectado solo por Lean, o justificación de por qué no hubo ninguno | ✗ /(?i)\blean\b/ found 0x in docs/process/**/*.md \| formal/lean/README.md (need 1) |

## 5d. TLA+

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| T01 | ❌ | Especificación TLA+/PlusCal: configuración, planificación, escritura, validación, publicación, retries, checkpoint y regeneración | ✗ 0 file(s) for formal/tla/*.tla (need 1) |
| T02 | ❌ | Al menos tres invariantes de seguridad y una propiedad de liveness | ✗ /(?m)^INVARIANTS?\b/ found 0x in formal/tla/*.cfg (need 1)<br>✗ /(?m)^PROPERT(Y\|IES)\b/ found 0x in formal/tla/*.cfg (need 1) |
| T03 | ❌ | Configuración TLC en el repo sobre un modelo pequeño (5 capítulos, 2 reintentos) | ✗ 0 file(s) for formal/tla/*.cfg (need 1) |
| T04 | ❌ | README que mapea cada acción de la especificación a un estado o transición del código | ✗ missing: formal/tla/README.md |
| T05 | ❌ | Contraejemplos de TLC documentados junto con el cambio que provocaron | ✗ /(?i)(counterexample\|contraejemplo)/ found 0x in docs/process/**/*.md \| formal/tla/README.md (need 1) |

## Evaluación

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| EV1 | ❌ | Cinco briefs de prueba: uno adversarial (injection) y uno con incoherencia temporal | ✗ 0 file(s) for evals/briefs/*.json (need 5) |
| EV2 | ❌ | Tabla por brief de qué validadores pasaron y cuáles fallaron | ✗ 0 file(s) for evals/results*.md \| docs/process/evals*.md (need 1) |
| EV3 | ❌ | Una iteración de tuning documentada, antes y después, con la versión de prompt | ✗ /(?i)(tuning)/ found 0x in docs/**/*.md \| evals/**/*.md (need 1) |

## 6. Observabilidad

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| O01 | ✅ | Una traza por generación, una sesión por novela (entrevista y regeneraciones incluidas) | ✓ /(?i)session_id/ in backend/app/commons/llm/tests/test_claude_code_command.py |
| O02 | ❌ | Span con nombre por rol y por tool; tokens, coste y latencia por llamada, capítulo y novela | ✗ /(?i)langfuse/ found 0x in backend/app/**/*.py (need 1) |
| O03 | ❌ | Prompts versionados en Langfuse | ✗ /(?i)get_prompt/ found 0x in backend/app/**/*.py (need 1) |

## 7. Guardrails

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| G01 | ❌ | Listas de palabras prohibidas en SQLite, globales y por novela | ✗ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*(forbidden\|banned\|blocklist)/ found 0x in backend/app/**/*.sql (need 1) |
| G02 | ❌ | Normalización antes de comparar: mayúsculas, acentos, plurales y variantes simples | ✗ /unicodedata/ found 0x in backend/app/**/*.py (need 1) |
| G03 | 📝 | Una coincidencia devuelve el capítulo al writer con límite; agotado, se detiene e informa | — |
| G04 | ❌ | Audit log de las decisiones del policy engine (cada coincidencia también en Langfuse) | ✗ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*audit/ found 0x in backend/app/**/*.sql (need 1) |
| G05 | ❌ | Tests con un caso por nivel y un caso de variante (acento o plural) | ✗ 0 file(s) for backend/app/**/tests/test_*forbidden*.py \| backend/app/**/tests/test_*guardrail*.py (need 1) |
| G06 | ✅ | Máximo de 100.000 tokens de contexto por llamada | ✓ /CONTEXT_TOKEN_CAP\s*(:[^=\n]+)?=\s*100_000/ in backend/app/commons/config.py |

## Docs de proceso

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| D01 | ✅ | Spec inicial: qué se decidió construir y por qué, antes del código | ✓ 2 file(s) for docs/process/spec-inicial*.md \| specs/001-*/001-*.md (need 1) |
| D02 | ❌ | Trade-offs: cada decisión relevante con opciones, criterios y elección | ✗ 0 file(s) for docs/process/trade-offs*.md \| docs/process/adr/*.md (need 1) |
| D03 | ❌ | Explainers: uno por concepto del curso aplicado en el proyecto | ✗ 0 file(s) for docs/process/explainers/*.md (need 3) |
| D04 | 🟡 | Diagramas: arquitectura del harness, máquina de estados TLA+, esquema SQLite, tabla de validadores | ✓ /flowchart/ in docs/architecture.md (+1)<br>✗ /stateDiagram/ found 0x in docs/process/**/*.md \| formal/tla/README.md (need 1)<br>✗ /erDiagram/ found 0x in docs/process/**/*.md \| docs/architecture.md (need 1)<br>✗ /(?i)validator/ found 0x in docs/process/**/*.md \| docs/verification.md (need 1) |
| D05 | ❌ | Registro de iteraciones: qué cambió tras cada eval, contraejemplo TLC o fallo Lean, y por qué | ✗ 0 file(s) for docs/process/iteraciones*.md \| docs/process/iterations*.md (need 1) |
| D06 | ❌ | Red-team log: casos adversariales, qué validador los detectó y cómo se resolvió | ✗ 0 file(s) for docs/process/red-team*.md (need 1) |

## Opcionales

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| X01 | ❌ | Servidor MCP de solo lectura (FastMCP) para consultar y descargar novelas *(opcional)* | ✗ /(?i)fastmcp/ found 0x in backend/app/**/*.py \| backend/pyproject.toml (need 1) |
| X02 | ✅ | Linters de prosa (repeticiones, frases largas, clichés de IA, consistencia de narrador) *(opcional)* | ✓ /(?i)(cliche\|readability\|repetition)/ in backend/app/ledger/audit/persist.py |
| X03 | ❌ | Login con SQLite (hash bcrypt, JWT) y aislamiento de novelas por usuario *(opcional)* | ✗ /(?i)(bcrypt\|argon2)/ found 0x in backend/pyproject.toml (need 1) |
| X04 | ❌ | Informe de seguridad en docs/security-report.md *(opcional)* | ✗ missing: docs/security-report.md |

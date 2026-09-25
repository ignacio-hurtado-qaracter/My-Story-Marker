# Cumplimiento del examen

Generado por `python exam/check.py` a partir de `exam/requirements.toml`. No se edita a mano.

Las comprobaciones son heurísticas: ✅ dice que el artefacto existe, no que sea bueno.

**Obligatorios comprobables cumplidos: 71 de 72.**

Leyenda: ✅ cumple · 🟡 parcial · ❌ falta · 📝 manual · 📝✅ existe, revisar a mano

## Resumen por bloque

| Bloque | ✅ | 🟡 | ❌ | 📝 |
|---|---|---|---|---|
| Entregables | 5 | 0 | 0 | 3 |
| Presentación | 4 | 0 | 1 | 0 |
| Claude Code | 6 | 0 | 0 | 0 |
| 1. Configuración | 4 | 0 | 0 | 0 |
| 2. Lectura | 7 | 0 | 0 | 0 |
| 3. Harness | 5 | 0 | 0 | 1 |
| 4. Memoria | 4 | 0 | 0 | 0 |
| 5a. Programáticos | 6 | 0 | 0 | 0 |
| 5b. Semánticos | 1 | 0 | 0 | 1 |
| 5c. Lean 4 | 3 | 0 | 0 | 1 |
| 5d. TLA+ | 4 | 0 | 0 | 1 |
| Evaluación | 3 | 0 | 0 | 0 |
| 6. Observabilidad | 3 | 0 | 0 | 0 |
| 7. Guardrails | 5 | 0 | 0 | 1 |
| Docs de proceso | 6 | 0 | 0 | 0 |
| Opcionales | 4 | 0 | 0 | 0 |

## Entregables

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| E01 | ✅ | README.md en la raíz del repo | ✓ exists: README.md |
| E02 | ✅ | Brief de ejemplo reproducible, citado desde el README (provisional: ejemplos/brief-ejemplo.json) | ✓ 1 file(s) for ejemplos/brief-ejemplo.* (need 1)<br>✓ /brief-ejemplo/ in README.md |
| E03 | ✅ | .env.example versionado | ✓ exists: .env.example |
| E04 | ✅ | Sin API keys ni tokens en ningún fichero versionado | ✓ no match in tracked files |
| E05 | ✅ | Novela de ejemplo completa de 10 capítulos en PDF | ✓ exists: ejemplos/novela-ejemplo.pdf |
| E06 | 📝✅ | CLAUDE.md en la raíz, cuidado y legible (se puntúa) | ✓ exists: CLAUDE.md |
| E07 | 📝 | Repositorio MyFactory: commit final enlazado | — |
| E08 | 📝 | Email de entrega con los dos enlaces a commit y la frase de decisión de diseño (máx. 3 líneas) | — |

## Presentación

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| P01 | ✅ | presentacion/README.md con el contenido y el idioma elegido | ✓ exists: presentacion/README.md<br>✓ /(?i)idioma/ in presentacion/README.md |
| P02 | ✅ | Deck principal en PDF | ✓ 6 file(s) for presentacion/*.pdf (need 1) |
| P03 | ✅ | Deck en formato editable (pptx, key, odp) | ✓ 1 file(s) for presentacion/*.pptx \| presentacion/*.key \| presentacion/*.odp (need 1) |
| P04 | ✅ | Anexos como ficheros individuales con nombre descriptivo (anexo-*.pdf) | ✓ 5 file(s) for presentacion/anexo-*.pdf (need 1) |
| P05 | ❌ | Vídeo de demo en presentacion/ o enlazado desde el README | ✗ 0 file(s) for presentacion/*.mp4 \| presentacion/*.mov \| presentacion/*.webm (need 1)<br>✗ /(?i)https?://\S*(loom\.com\|youtu\.?be\|vimeo\.com\|drive\.google)/ found 0x in README.md \| presentacion/README.md (need 1) |

## Claude Code

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| K01 | ✅ | Comandos personalizados versionados en .claude/commands/ | ✓ 4 file(s) for .claude/commands/*.md (need 1) |
| K02 | ✅ | Ficheros de memoria versionados en .claude/ (provisional: .claude/memory/) | ✓ 2 file(s) for .claude/memory/*.md (need 1) |
| K03 | ✅ | Configuración MCP con un servidor de inspección de navegador | ✓ /(?i)(playwright\|chrome)/ in .mcp.json |
| K04 | ✅ | Skills del desarrollo en el repo y referenciadas desde /docs | ✓ 6 file(s) for .claude/skills/*/SKILL.md (need 1)<br>✓ /\.claude/skills/ in docs/process/README.md (+3) |
| K05 | ✅ | Subagentes y comandos propios documentados en /docs con propósito y resultado | ✓ /(?i)(subagent\|\.claude/commands\|\.claude/agents)/ in docs/process/README.md (+4) |
| K06 | ✅ | Uso real del browser MCP documentado: qué inspeccionó, qué detectó, qué cambió | ✓ /(?i)(playwright mcp\|browser mcp\|chrome mcp)/ in docs/architecture.md (+10) |

## 1. Configuración

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| C01 | ✅ | Agente entrevistador: nombre, edad, rasgos, recuerdos, género, tono, extensión y temas vetados | ✓ /(?i)interview/ in backend/app/auth/tests/test_auth.py (+24) |
| C02 | ✅ | Brief estructurado y validado con schema | ✓ 1 file(s) for backend/schemas/brief*.json (need 1) |
| C03 | ✅ | Detecta datos que faltan y al menos un tipo de contradicción (edad frente a género o tono) | ✓ /(?i)contradict/ in backend/app/interview/brief.py (+4) |
| C04 | ✅ | Texto libre pegado por el usuario tratado como no confiable, con hechos extraídos | ✓ /(?i)untrusted/ in backend/app/interview/__init__.py (+8) |

## 2. Lectura

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| R01 | ✅ | Lector web (frontend) o PDF interactivo | ✓ 39 file(s) for frontend/src/**/*.tsx \| backend/app/**/pdf*.py \| backend/app/**/export*.py (need 1) |
| R02 | ✅ | Índice de capítulos navegable | ✓ /(?i)(table.?of.?contents\|\btoc\b\|índice)/ in backend/app/export/pdf.py (+12) |
| R03 | ✅ | Ficha de personajes y lugares desde la story bible, con enlaces al capítulo donde aparecen | ✓ /(?i)(character.?sheet\|ficha\|glossary\|dramatis)/ in backend/app/export/pdf.py (+5) |
| R04 | ✅ | Portada con dedicatoria personalizada | ✓ /(?i)dedicat/ in backend/app/bible/__init__.py (+17) |
| R05 | ✅ | Cambio pedido por el lector: identifica capítulos que usan el hecho y regenera solo esos | ✓ /(?i)change.?request/ in backend/app/reader/__init__.py (+4) |
| R06 | ✅ | Se marcan los capítulos cambiados (web) o hay página de novedades (PDF) | ✓ /(?i)(changed_chapters\|novedades\|what.?s.?new)/ in backend/app/bible/models.py (+15) |
| R07 | ✅ | Se conserva la versión anterior de la novela | ✓ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*version/ in backend/app/commons/db/authoritative/migrations/1000_init.sql |

## 3. Harness

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| H01 | ✅ | Tres roles como mínimo (planner, writer, editor/critic) invocados por un orquestador | ✓ /(?i)def plan(_(novel\|chapters?\|scenes\|structure\|story))?\(/ in backend/app/novel/pipeline.py (+1)<br>✓ /(?i)def write\w*\(/ in backend/app/agents/roles/writer.py (+6)<br>✓ /(?i)def (critique\|audit\|edit\|polish\|judge)\w*\(/ in backend/app/agents/roles/auditor.py (+5) |
| H02 | 📝✅ | Una skill reutilizable propia del harness | ✓ 6 file(s) for .claude/skills/*/SKILL.md (need 1) |
| H03 | ✅ | Hook de validación de capítulo | ✓ /(?i)chapter/ in .claude/hooks/README.md (+5) |
| H04 | ✅ | Hook de policy | ✓ /(?i)policy/ in .claude/hooks/README.md (+4) |
| H05 | ✅ | Tools con schema validado | ✓ /(?i)(def toolset_for\|tool_schema\|input_schema)/ in backend/app/commons/permissions/toolsets.py (+5) |
| H06 | ✅ | Retries con límite, usados por el orquestador | ✓ /TURN_MAX_REVISIONS\|MAX_RETRIES\|max_attempts/ in backend/app/agents/turn.py |

## 4. Memoria

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| M01 | ✅ | Story bible en SQLite: cada hecho registra en qué capítulos se usa | ✓ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*fact/ in backend/app/commons/db/authoritative/migrations/1000_init.sql |
| M02 | ✅ | Tabla de cronología en SQLite (eventos, momento, personajes, lugar) | ✓ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*(chrono\|event\|timeline)/ in backend/app/commons/db/authoritative/migrations/1000_init.sql |
| M03 | ✅ | Resúmenes por capítulo que alimentan el contexto de los siguientes | ✓ /(?i)def \w*(digest\|summar\|rollup)\w*\(/ in backend/app/agents/roles/writer.py (+6) |
| M04 | ✅ | Checkpoint por capítulo y reanudación desde el último completado | ✓ /(?i)(checkpoint\|def resume)/ in backend/app/agents/router.py (+11)<br>✓ /(?i)(chapter\w{0,20}(checkpoint\|resume)\|(checkpoint\|resume)\w{0,20}chapter\|last_completed_chapter)/ in backend/app/bible/repository.py (+4) |

## 5a. Programáticos

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| V01 | ✅ | Longitud de cada capítulo dentro del rango (1.000–1.500 palabras) | ✓ /(?i)\b(chapter_word_range\|chapter_min_words\|chapter_max_words\|word_range\|min_words\|max_words)\b/ in backend/app/validators/programmatic/length.py |
| V02 | ✅ | Nombre del destinatario y personajes escritos exactamente como en la story bible | ✓ /(?i)(exact_name\|name_spelling)/ in backend/app/novel/context.py (+5) |
| V03 | ✅ | Cada elemento personalizado obligatorio del brief aparece en algún capítulo (contra SQLite) | ✓ /(?i)(brief_coverage\|required_element)/ in backend/app/validators/programmatic/__init__.py (+2) |
| V04 | ✅ | Schema del brief y de la salida de cada rol validados | ✓ /class \w+Output\(/ in backend/app/commons/schemas/role_outputs.py<br>✓ 1 file(s) for backend/schemas/brief*.json (need 1) |
| V05 | ✅ | Validación visual con browser MCP: índice, ficha y portada renderizan; fallos vuelven al rol | ✓ /(?i)(playwright mcp\|browser mcp\|chrome mcp)/ in docs/process/README.md (+7) |
| V06 | ✅ | Cada validador tiene nombre, punto de ejecución y envía su resultado a Langfuse como score | ✓ /(?i)(create_score\|score_current\|\.score\()/ in backend/app/commons/observability/__init__.py (+9) |

## 5b. Semánticos

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| S01 | ✅ | LLM-as-judge con rúbrica (continuidad, tono, calidad narrativa, personalización natural), nota y justificación por criterio | ✓ /(?i)rubric/ in backend/app/judge/__init__.py (+5) |
| S02 | 📝✅ | Revisión humana de una novela completa con la misma rúbrica, comparada con el juez | ✓ /(?i)(human review\|revisión humana)/ in docs/process/explainers/11-llm-as-judge.md (+3) |

## 5c. Lean 4

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| L01 | ✅ | Generador del fichero Lean con los hechos temporales, a partir de SQLite | ✓ /(?i)\.lean\b/ in backend/app/formal/lean_export.py (+3) |
| L02 | ✅ | Proyecto Lean con al menos dos invariantes | ✓ 1 file(s) for formal/lean/**/lakefile.* (need 1)<br>✓ /(?m)^(theorem\|def)\s/ in formal/lean/Chronology/Basic.lean (+1) |
| L03 | ✅ | lake build automático; si falla, la versión no se publica y el fallo vuelve al editor | ✓ /lake/ in backend/app/formal/__init__.py (+6) |
| L04 | 📝✅ | Caso real detectado solo por Lean, o justificación de por qué no hubo ninguno | ✓ /(?i)\blean\b/ in docs/process/README.md (+11) |

## 5d. TLA+

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| T01 | ✅ | Especificación TLA+/PlusCal: configuración, planificación, escritura, validación, publicación, retries, checkpoint y regeneración | ✓ 1 file(s) for formal/tla/*.tla (need 1) |
| T02 | ✅ | Al menos tres invariantes de seguridad y una propiedad de liveness | ✓ /(?m)^INVARIANTS?\b/ in formal/tla/GiftNovelHarness.cfg<br>✓ /(?m)^PROPERT(Y\|IES)\b/ in formal/tla/GiftNovelHarness.cfg |
| T03 | ✅ | Configuración TLC en el repo sobre un modelo pequeño (5 capítulos, 2 reintentos) | ✓ 1 file(s) for formal/tla/*.cfg (need 1) |
| T04 | ✅ | README que mapea cada acción de la especificación a un estado o transición del código | ✓ exists: formal/tla/README.md |
| T05 | 📝✅ | Contraejemplos de TLC documentados junto con el cambio que provocaron | ✓ /(?i)(counterexample\|contraejemplo)/ in docs/process/README.md (+5) |

## Evaluación

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| EV1 | ✅ | Cinco briefs de prueba: uno adversarial (injection) y uno con incoherencia temporal | ✓ 5 file(s) for evals/briefs/*.json (need 5) |
| EV2 | ✅ | Tabla por brief de qué validadores pasaron y cuáles fallaron | ✓ 1 file(s) for evals/results*.md \| docs/process/evals*.md (need 1) |
| EV3 | ✅ | Una iteración de tuning documentada, antes y después, con la versión de prompt | ✓ /(?i)(tuning)/ in docs/process/README.md (+11) |

## 6. Observabilidad

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| O01 | ✅ | Una traza por generación, una sesión por novela (entrevista y regeneraciones incluidas) | ✓ /(?i)session_id/ in backend/app/auth/tests/test_auth.py (+15) |
| O02 | ✅ | Span con nombre por rol y por tool; tokens, coste y latencia por llamada, capítulo y novela | ✓ /(?i)langfuse/ in backend/app/bible/repository.py (+19) |
| O03 | ✅ | Prompts versionados en Langfuse | ✓ /(?i)get_prompt/ in backend/app/commons/observability/langfuse_observer.py (+1) |

## 7. Guardrails

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| G01 | ✅ | Listas de palabras prohibidas en SQLite, globales y por novela | ✓ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*(forbidden\|banned\|blocklist)/ in backend/app/commons/db/authoritative/migrations/1000_init.sql |
| G02 | ✅ | Normalización antes de comparar: mayúsculas, acentos, plurales y variantes simples | ✓ /unicodedata/ in backend/app/policy/normalise.py |
| G03 | 📝 | Una coincidencia devuelve el capítulo al writer con límite; agotado, se detiene e informa | — |
| G04 | ✅ | Audit log de las decisiones del policy engine (cada coincidencia también en Langfuse) | ✓ /(?i)CREATE TABLE\s+(IF NOT EXISTS\s+)?\w*(audit\|policy_decision)/ in backend/app/commons/db/authoritative/migrations/1000_init.sql |
| G05 | ✅ | Tests con un caso por nivel y un caso de variante (acento o plural) | ✓ 1 file(s) for backend/app/**/tests/test_*forbidden*.py \| backend/app/**/tests/test_*guardrail*.py (need 1) |
| G06 | ✅ | Máximo de 100.000 tokens de contexto por llamada | ✓ /CONTEXT_TOKEN_CAP\s*(:[^=\n]+)?=\s*100_000/ in backend/app/commons/config.py |

## Docs de proceso

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| D01 | ✅ | Spec inicial: qué se decidió construir y por qué, antes del código | ✓ 3 file(s) for docs/process/spec-inicial*.md \| specs/001-*/001-*.md (need 1) |
| D02 | ✅ | Trade-offs: cada decisión relevante con opciones, criterios y elección | ✓ 1 file(s) for docs/process/trade-offs*.md \| docs/process/adr/*.md (need 1) |
| D03 | ✅ | Explainers: uno por concepto del curso aplicado en el proyecto | ✓ 21 file(s) for docs/process/explainers/*.md (need 3) |
| D04 | ✅ | Diagramas: arquitectura del harness, máquina de estados TLA+, esquema SQLite, tabla de validadores | ✓ /flowchart/ in docs/architecture.md (+4)<br>✓ /stateDiagram/ in docs/process/README.md (+2)<br>✓ /erDiagram/ in docs/process/README.md (+1)<br>✓ /(?i)validator/ in docs/process/diagramas.md (+8) |
| D05 | ✅ | Registro de iteraciones: qué cambió tras cada eval, contraejemplo TLC o fallo Lean, y por qué | ✓ 1 file(s) for docs/process/iteraciones*.md \| docs/process/iterations*.md (need 1) |
| D06 | ✅ | Red-team log: casos adversariales, qué validador los detectó y cómo se resolvió | ✓ 1 file(s) for docs/process/red-team*.md (need 1) |

## Opcionales

| Id | Estado | Requisito | Evidencia |
|---|---|---|---|
| X01 | ✅ | Servidor MCP de solo lectura (FastMCP) para consultar y descargar novelas *(opcional)* | ✓ /(?i)fastmcp/ in backend/app/auth/tests/test_auth.py (+2) |
| X02 | ✅ | Linters de prosa (repeticiones, frases largas, clichés de IA, consistencia de narrador) *(opcional)* | ✓ /(?i)(cliche\|readability\|repetition)/ in backend/app/ledger/audit/persist.py (+2) |
| X03 | ✅ | Login con SQLite (hash bcrypt, JWT) y aislamiento de novelas por usuario *(opcional)* | ✓ /(?i)(bcrypt\|argon2)/ in backend/pyproject.toml |
| X04 | ✅ | Informe de seguridad en docs/security-report.md *(opcional)* | ✓ exists: docs/security-report.md |

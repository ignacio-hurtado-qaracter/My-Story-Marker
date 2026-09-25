# Trade-offs

> Registro (spec 004, D10). Cada decisión relevante como **opciones → criterios →
> elección**, con lo que costó. El diseño resultante está en [`docs/`](../architecture.md);
> las decisiones numeradas D1–D11 y V1–V6 son las de la
> [spec 004](../../specs/004-exam-refactor-programme/004-exam-refactor-programme.md#2-cross-cutting-decisions)
> y su [plan](../../specs/004-exam-refactor-programme/004-exam-refactor-programme-plan.md).

## Índice

1. [Single-agent vs multi-agent](#single-agent-vs-multi-agent)
2. [Formato de la story bible](#formato-de-la-story-bible)
3. [Modelo de lectura](#modelo-de-lectura)
4. [Integración de TLA+ con el flujo real](#integración-de-tla-con-el-flujo-real)
5. [Invariantes de Lean priorizados](#invariantes-de-lean-priorizados)
6. [`claude -p` frente a API key](#claude--p-frente-a-api-key)
7. [Haiku 4.5 para todos los roles](#haiku-45-para-todos-los-roles)
8. [Tres escenas por capítulo](#tres-escenas-por-capítulo)
9. [Severidad del juez frente a bucles de reescritura](#severidad-del-juez-frente-a-bucles-de-reescritura)
10. [Normalización de términos prohibidos](#normalización-de-términos-prohibidos)
11. [Verificación ligera (V3)](#verificación-ligera-v3)
12. [Paralelismo con un worktree por agente (V1)](#paralelismo-con-un-worktree-por-agente-v1)

---

## Single-agent vs multi-agent

**Opciones.** (a) Un único agente con herramientas que planifica, escribe y se corrige.
(b) Varios roles con prompt, esquema de salida y permisos propios, orquestados por código.

**Criterios.** Que cada escritura en la story bible tenga un responsable (Figura 3);
contexto por llamada bajo el tope de 100k; poder validar y reintentar cada paso por
separado; trazas por rol en Langfuse; que un fallo vuelva al rol que puede arreglarlo.

**Elección: (b), multi-agent con orquestador determinista** (D7). Seis roles:
`interviewer` (brief), `planner` (plan, reparto, cronología), `writer` (escenas), `editor`
(une, pule, autocrítica, reescritura con feedback), `judge` (rúbrica, solo lectura salvo sus
resultados) y `canoniser` (heredado del harness genérico). **Ningún modelo tiene
herramientas**: el orquestador (`backend/app/novel/pipeline.py`) decide qué documentos ve
cada rol y escribe él en la BD. Así la tabla de permisos se aplica en código, no en un
prompt ([Figura 3](../architecture.md#figure-3--agents-and-write-permissions)).

**Coste.** Más llamadas (≈ 7 por capítulo en el smoke de 1 capítulo: 3 escenas, editor,
ajuste de longitud, juez) y más código de orquestación. Nota honesta: en el pipeline de la
novela-regalo el `canoniser` no se invoca; la "canonización" es determinista
(`persist_plan`, `fact_usage_recorder`). Sigue en la tabla por el harness heredado.

## Formato de la story bible

**Opciones.** (a) Ficheros YAML/Markdown por novela como fuente, SQLite como índice
derivado (lo que decía `docs/`). (b) SQLite autoritativa. (c) Ficheros + índice derivado +
reconstrucción.

**Criterios.** El examen pide la story bible en SQLite y que cada hecho sepa qué capítulos
lo usan; `change_fact` necesita esa consulta; Lean necesita una tabla de cronología; los
validadores y el lector leen lo mismo; una sola fuente de verdad.

**Elección: (b)** (D1, D2). `backend/app/bible/repository.py` (`BibleRepository`) es el
único código que toca `HARNESS_DB`. Tablas en el
[esquema](./diagramas.md#esquema-sqlite). Con **V4** fuimos un paso más allá: el texto de
cada capítulo también es una fila de `chapter_version` (con `hash`), no un fichero, porque
D6 ya ponía texto y hash en la BD y tenerlo también en ficheros eran dos fuentes del mismo
texto.

**Coste.** Se pierden los diffs de git sobre la prosa y las herramientas del harness
genérico sobre `manuscript/`. A cambio, `checkpoint` escribe texto y checkpoint en una
transacción (regla CE1 de TLC), cosa imposible entre un fichero y una fila.

## Modelo de lectura

**Opciones.** (a) Solo PDF interactivo. (b) Lector web. (c) Web + exportación a PDF.

**Criterios.** Índice navegable, fichas enlazadas a capítulos, marca de capítulos
cambiados, selector de versión, pedir un cambio seleccionando un fragmento; poder regalarlo
como fichero; validación visual con browser MCP.

**Elección: (c)** (D8). El lector React (`frontend/src/reader`, `cover`, `bible`) es donde
se piden cambios y se ven versiones; el PDF (`backend/app/export`, reportlab) es el objeto
regalable. Un PDF solo no permite pedir cambios ni marcar versiones, y la validación visual
con Playwright MCP necesita páginas web.

## Integración de TLA+ con el flujo real

**Opciones.** (a) Modelar el turno de escritura genérico (lo previsto en `docs/`). (b)
Modelar el pipeline de la novela-regalo después de escribirlo. (c) Modelarlo **antes**, en
paralelo, con los nombres fijados por el plan, y mapear después acción a función.

**Criterios.** Que TLC encuentre errores de diseño cuando aún son baratos; que cada acción
tenga una función real; que los contraejemplos cambien el código, no solo el modelo.

**Elección: (c).** B9 escribió `formal/tla/GiftNovelHarness.tla` en la oleada A, a partir
de los contratos K1/K4, con crash y reanudación explícitos y variables durables separadas
de las volátiles. TLC encontró **cuatro contraejemplos** (CE1–CE4,
[`COUNTEREXAMPLES.md`](../../formal/tla/COUNTEREXAMPLES.md)) *antes* de que existiera el
pipeline; B1 revisó su spec y su esquema (commit `d42b8a0`, migración `1001_tlc_rules.sql`)
y B3 los aplicó (docstring de `pipeline.py`). La tabla acción → código está confirmada en
[`formal/tla/README.md`](../../formal/tla/README.md#mapping-tla-action--code). TLC corre en
desarrollo, no por generación (5 capítulos × 2 reintentos, ~1 min).

**Coste.** El modelo abstrae la prosa y los validadores (resultado no determinista); el
contador de reintentos de escena vive en memoria en el código (ver divergencias en el
README de TLA+).

## Invariantes de Lean priorizados

**Opciones.** Muchos candidatos: orden temporal, edades, bilocación, apariciones tras
muerte/partida, duración de viajes, estaciones, coherencia de relaciones, parentescos.

**Criterios.** (1) Errores que un LLM comete de verdad en una novela sobre una vida real
(edades en recuerdos, saltos atrás sin marcar, mascotas que reaparecen). (2) Que otros
validadores no los vean (un juez LLM lee 10 capítulos y se le escapan fechas). (3)
Decidibles sobre datos que ya tenemos en `chronology_event`/`event_participant`/`character`.
(4) Coste de build acotado.

**Elección: cuatro** (`formal/lean/Chronology/Basic.lean`): `temporalOrder`,
`agesCoherent`, `noBilocation`, `noAfterExit`, cada uno como `Bool` + `Prop` + teorema de
corrección, así que un `lake build` verde **es** una prueba. Solo core Lean, **sin
Mathlib**: el toolchain fijado basta, no hay descarga de gigas ni caché que invalidar, y
las pruebas son por cómputo. `decide +kernel` en lugar de `decide`: el `decide` normal
reduce en el elaborador y revienta `maxRecDepth` hacia los ~100 eventos; `native_decide`
se descartó porque confía en el compilador y no en el kernel. Coste medido: 100 eventos 3 s,
300 eventos 17 s (`noBilocation` es cuadrático).

## `claude -p` frente a API key

**Opciones.** (a) SDK de Anthropic con `ANTHROPIC_API_KEY`. (b) CLI de Claude Code
(`claude -p`) con el login del usuario.

**Criterios.** Ninguna clave en el repo ni en el entorno (E04); aislamiento del rol (que no
lea el árbol ni el `CLAUDE.md`); salida estructurada validada; coste dentro de la
suscripción del usuario.

**Elección: (b).** `backend/app/commons/llm/claude_code_client.py` lanza un subproceso por
llamada con `--tools ""`, `--setting-sources ""`, `--strict-mcp-config` sin servidores, un
directorio temporal vacío y el esquema JSON de salida; elimina `ANTHROPIC_API_KEY` del
entorno del hijo.

**Coste.** Latencia de arranque por llamada y dependencia de las políticas de la sesión del
CLI: en la primera llamada real el modelo **anonimizó los nombres** del brief por RGPD (ver
[iteraciones](./iteraciones.md#anonimización-de-nombres-por-claude--p)), lo que obligó a
declarar en los prompts que los nombres son ficción encargada y a añadir el validador
`no_placeholders`.

## Haiku 4.5 para todos los roles

**Opciones.** Sonnet/Opus para escritor y juez, Haiku para el resto; o Haiku para todo.

**Criterios.** Dos novelas de 10 capítulos en una noche; ~30 escenas y ~70 llamadas por
novela; coste por novela visible en Langfuse; calidad mínima medida por el juez.

**Elección: `claude-haiku-4-5` para todos** (plan 004), con subida por rol vía
`MODEL_<ROLE>` solo si un rol falla repetidamente, registrada en
[iteraciones](./iteraciones.md). Smoke de 1 capítulo: publicado, 1.067 palabras, 0,30 USD,
7 llamadas, ~6,5 min (`7fbc8b0`).

## Tres escenas por capítulo

**Opciones.** 4–7 escenas (spec original), 3–5 (D3), 3 fijas por defecto (V5).

**Criterios.** 1.000–1.500 palabras por capítulo; coste y latencia lineales en escenas;
continuidad entre escenas (la cola literal de la escena previa).

**Elección: 3 por defecto** (V5). Con ~400 palabras por escena la cola de 500 palabras
dejaba de caber en una escena corta; el planner reparte presupuestos que
`_repair_plan` reescala a 1.100–1.350 por capítulo, y el editor une y pule. El editor tiene
orden explícita de **no condensar** (tendía a resumir y dejar el capítulo por debajo de
1.000; `7fbc8b0`), más un ajuste de longitud acotado a una llamada.

## Severidad del juez frente a bucles de reescritura

**Opciones.** Juez consultivo (solo puntúa); juez bloqueante estricto; juez bloqueante con
umbral moderado y presupuesto de reintentos.

**Criterios.** D11 exige que calidad y personalización bloqueen; pero cada fallo cuesta una
reescritura del editor y el presupuesto es `MAX_CHAPTER_RETRIES = 2` por capítulo.

**Elección:** bloqueante con umbral **cada criterio ≥ 3 y media ≥ 3,5, sin defecto
bloqueante** (`backend/app/judge/rubric.py`); en la novela, una contradicción entre
capítulos es bloqueante. Evidencia por criterio (`continuidad: n/5 — …`) que vuelve al
editor como feedback. Comprobación en vivo: un capítulo bueno 5/5/5/5, uno deliberadamente
malo 1/1/1/1 con 3 defectos bloqueantes (`35d3a83`). En la iteración de tuning 1 los umbrales
no cambiaron (D11); cambió qué bloquea: solo un defecto `alta` concreto con capítulo citado
([iteraciones](./iteraciones.md#iteración-de-tuning-1)).

## Normalización de términos prohibidos

**Opciones.** Subcadena sin mayúsculas (lo previo); regex por término; normalizador
compartido texto/término.

**Criterios.** Detectar mayúsculas, tildes, plurales, leetspeak y letras estiradas
(`c4br0n`, `tontooo`) sin falsos positivos en español (`culo` no está en `ridículo`, `y a`
no es una palabra partida).

**Elección:** un único plegado para texto y término (`backend/app/policy/normalise.py`):
NFKD sin marcas, tokens, leetspeak solo dentro de tokens con letras, estiramiento, plurales
por candidatos singulares, palabras completas y frases. Tres niveles: global (migración
`1300`), novela (brief) y léxico. Un acierto vuelve al escritor, como mucho
`MAX_FORBIDDEN_REWRITES = 2`, y agotado termina en `forbidden_word_limit`.

## Verificación ligera (V3)

**Opciones.** Puerta completa de `AGENTS.md` (ruff, mypy --strict, bandit, pytest completo,
schemathesis, hypothesis) en cada bloque; o puerta ligera en código nuevo.

**Criterios.** Una noche de reloj; doce bloques en paralelo; el usuario pidió verificadores
ligeros.

**Elección: ligera** — ruff + `mypy --strict` del paquete nuevo + 1–3 tests enfocados por
bloque; sin schemathesis/hypothesis para código nuevo; registrado como **U** en el registro
de riesgos aceptados. Se compensa con lo que no es test: TLC, Lean, el juez y ejecuciones
en vivo con resultado pegado en el commit. Aun así schemathesis (heredado en la API) cazó un
500 real (ver [iteraciones](./iteraciones.md#tests-de-contrato)).

## Paralelismo con un worktree por agente (V1)

**Opciones.** Una rama por bloque y PR (spec 004 § 5); una sola rama compartida; un worktree
por agente con fusión por el orquestador.

**Criterios.** La sesión solo puede empujar a `proyecto-desde-cero`; bloques con ficheros
disjuntos; ficheros compartidos (`main.py`, `config.py`, `pyproject.toml`, `openapi.json`)
con conflictos previsibles.

**Elección: worktree por agente** (V1). Cada agente trabaja aislado en
`.claude/worktrees/agent-*`; el orquestador fusiona (ver
[subagentes](./subagentes-comandos-skills.md)). Los ficheros compartidos se editan en
commits pequeños y separados, y `openapi.json` se regenera en vez de fusionarse. El coste
fue la coordinación: fusiones intermedias de una rama en otra (`5be6525`, `eb0a48e`) para
que B3 viera a B4 y B2, y tests de B1 que hubo que relajar cuando B5 sembró términos
globales (`4357184`, `5ce641a`).

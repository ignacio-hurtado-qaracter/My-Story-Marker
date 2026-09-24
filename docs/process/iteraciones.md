# Registro de iteraciones

> Registro (spec 004, D10). No es un diario: cada entrada es **causa → efecto**, con el
> artefacto que la prueba. Las entradas van por origen: model checking, ejecuciones en
> vivo, Lean, tests de contrato, y (pendiente) evals y tuning.

| # | Origen | Causa observada | Efecto (cambio) | Evidencia |
|---|---|---|---|---|
| 1 | TLC | CE1: crash entre fila de capítulo y checkpoint → capítulo duplicado | Texto + checkpoint en una transacción | `save_chapter_and_checkpoint`, `d42b8a0` |
| 2 | TLC | CE2: contador de reintentos de capítulo en memoria, un crash lo reinicia | Presupuesto leído de `validator_result` | `count_chapter_attempts`, `_chapter_close_runs` |
| 3 | TLC | CE3: la ronda de reparación inserta una segunda fila | Upsert por `(version, chapter)`; versión publicada congelada; rechazados a `chapter_attempt` | `1001_tlc_rules.sql` |
| 4 | TLC | CE4: contador de rondas de reparación en memoria | `novel_version.repair_rounds` junto con `blocked`, en una transacción | `block_version`, `publish_version` |
| 5 | B2 en vivo | `claude -p` anonimizó los nombres del brief (RGPD) | Prompts declaran los nombres ficción encargada; validador `no_placeholders` | `96ae126`, `967902f` |
| 6 | B3 en vivo | `brief_coverage` fallaba por redacción literal ("un faro" / "el faro") → rondas de reparación | El editor recibe la orden de conservar la expresión literal de cada hecho planificado | `ab4731f`, `app/novel/roles.py` |
| 7 | B3 en vivo | Tras `change_fact`, el juez suspendía: un recuerdo seguía nombrando a la mascota antigua | El renombrado se propaga a hechos derivados, brief, plan, reparto y todo capítulo que mencione el nombre | `ab4731f` |
| 8 | B3 en vivo | El editor condensaba las 3 escenas y dejaba el capítulo < 1.000 palabras | Orden de no condensar + un ajuste de longitud acotado; español peninsular | `7fbc8b0` |
| 9 | Lean | `decide` superaba `maxRecDepth` con ~100 eventos | `decide +kernel` en los teoremas generados | `8f4a431`, `formal/lean/README.md` |
| 10 | Lean / plan | La prosa no puede reparar filas de cronología | La cronología del plan se hace Lean-válida antes de escribir; un proyecto Lean por novela | `2df3c74`, `bce0907` |
| 11 | Schemathesis | Un entero > 64 bits en la URL daba 500 (`OverflowError`) | Versión y capítulo acotados a 1..2³¹−1 → 422 | `312b142` |
| 12 | B7 en vivo | El juez devolvió `comentario_general` como cadena JSON anidada | El prompt exige texto plano en español | `35d3a83`, `app/prompts/judge_*.md` |
| 13 | Revisión B12 | El código diverge del modelo y de la Figura 5 en tres puntos | 1 aceptada (segura); 2 y 3 corregidas (filas 15 y 16) | [abajo](#divergencias-encontradas-al-mapear-tla-a-código) |
| 14 | Browser MCP | `GET /novels/{id}` daba 500 intermitente: conexión SQLite abierta en un hilo del threadpool y usada en otro (12/20 concurrentes) | Repositorio por petición con `check_same_thread=False` (lector y entrevista); test de 20 peticiones concurrentes | `b612d34`, [log](./browser-mcp-log.md) |
| 15 | Revisión TLA+ | `change_fact` confirmaba el hecho antes de crear v+1: un crash perdía el cambio en silencio | Todo `change_fact` en una `repo.transaction()`; `transaction` usa SAVEPOINT si ya hay una abierta | `772f846`, `formal/tla/README.md` |
| 16 | Revisión Figura 5 | La Figura 5 decía "reescribe la escena señalada" y "conserva escenas aceptadas" | La figura y su prosa siguen al código: el editor reescribe el capítulo (rechazado a `chapter_attempt`); reanudar reinicia el capítulo desde la escena 1 | `2c6edf8` |
| 17 | Red-team R2 | El `free_text` crudo llegaba al planner (brief completo) y al juez (`brief_summary`) | Ambos lo reciben filtrado; solo hechos `source = free_text` | `a721bc7`, [R2](./red-team-log.md#r2--b3-injection) |
| 18 | Browser MCP | Las fichas de `?v=1` mostraban el nombre nuevo de la mascota | `story_bible` deshace los renombrados de las notas `change` posteriores a v; reparto sin versionar como limitación conocida | `ed58daa`, spec 014 |
| 19 | Evals `before` | `brief_coverage` paraba `b2` y `b3`: un título de recuerdo de ≤ 3 palabras exigía la frase exacta ("El caracol campeón") aunque el capítulo contaba el recuerdo | Recuerdos por palabras de contenido normalizadas (mitad del título o 30 % de la descripción; tildes y plurales con `app.policy.normalise`; sin nombres del brief) | `bff00df`, spec 008, [tuning](#iteración-de-tuning-1) |
| 20 | Evals `before` | `b4` se paraba en el plan: el espejo Python de `noAfterExit` daba por "salido" a todo participante de una muerte (Andrés entierra a Trueno) y Lean ordenaba por `seq` | `noAfterExit` en el eje de la historia (fecha), solo el primer participante sale; Lean y Python iguales | `e3942f1`, spec 012 |
| 21 | Novela de 10 cap. en vivo | `judge_novel` suspendía por capítulos solapados (1 y 2, "la última clase"), saltos de tiempo vagos y defectos "posibles"; la única ronda de reparación rehízo capítulos que el juez no pedía | Plan con `time_marker` y chequeo de solape; sinopsis vecinas a escritor/editor; solo bloquea un defecto `alta` concreto; se reparan `capitulos_a_reparar`; `MAX_REPAIR_ROUNDS = 2` (TLC OK) | `fecf6ba`, `8beec13`, `1a39e7c` |
| 22 | PDF | "Novedades" imprimía la nota JSON cruda | "Cambio: clave: «antes» → «después»" y capítulos cambiados con enlace | `bacc93a`, spec 014 |
| 23 | L04 | ¿Atrapa Lean algo que no vea nadie más? | Experimento con el prechequeo desactivado: Lean y `judge_novel` sí, `judge_chapter` y los programáticos no | `91f8cdd`, [lean-caso-real](./lean-caso-real.md) |

---

## Contraejemplos de TLC (CE1–CE4)

El modelo de B9 se escribió **antes** que el pipeline, leyendo el esquema K1 y el plan 004
tal cual: `chapter_version` y `checkpoint` como dos tablas, contadores de reintento como
variables del bucle. TLC (N = 5, 3 escenas, reintentos 2/2, una ronda de reparación, un
crash, un cambio) encontró cuatro trazas mínimas; el quinto borrador pasa con 696.062
estados distintos. Detalle y trazas: [`formal/tla/COUNTEREXAMPLES.md`](../../formal/tla/COUNTEREXAMPLES.md).

| CE | Invariante | Traza | Regla para el código | Dónde quedó |
|---|---|---|---|---|
| CE1 | `ResumeNoDupNoLoss` | 18 estados | Texto de capítulo y checkpoint en la misma transacción | `BibleRepository.save_chapter_and_checkpoint` ← `pipeline.checkpoint` |
| CE2 | `RetriesBounded` | 21 estados | Reintentos de capítulo contados desde resultados persistidos | `count_chapter_attempts` + `_chapter_close_runs` (descuenta las ejecuciones previas a la última ronda de reparación) |
| CE3 | `ResumeNoDupNoLoss` | 46 estados | Upsert por clave; nunca escribir una versión publicada; los textos rechazados se guardan aparte | PK `(novel_id, version, chapter)`, tabla `chapter_attempt`, `record_chapter_attempt` |
| CE4 | `RetriesBounded` | 50 estados | Ronda de reparación persistida con el estado `blocked` | columna `repair_rounds`, `block_version(…, repair_rounds=+1)` + reapertura de checkpoints en una transacción |

Efecto en el proceso: la spec 005 volvió a `draft` y se reaprobó (`62038fe`) antes de que B3
empezara, así que el pipeline nació con las cuatro reglas en su docstring.

## Ejecuciones en vivo

### Anonimización de nombres por `claude -p`

- **Causa.** Primera llamada real del extractor de texto libre (B2, Haiku 4.5): devolvió
  las personas como `[NOMBRE_ANONIMIZADO_…]`. La sesión del CLI aplica una política de
  privacidad y trató el brief como datos personales reales.
- **Efecto.** (1) Los prompts de extractor, planner, writer y editor declaran que todos
  los nombres son personajes de ficción de una novela encargada y deben copiarse letra por
  letra (`backend/app/prompts/*.md`). (2) Validador propio del pipeline `no_placeholders`
  en `scene_accept` y `chapter_close` (`backend/app/novel/placeholders.py`): un texto con
  `[MAYÚSCULAS_…]` se rechaza y vuelve con feedback. (3) Los recipients de todos los briefs
  son ficticios (plan 004).
- **Resultado.** Repetida la llamada: personas, mascota, lugares y recuerdos extraídos
  literalmente; 3.849 tokens de entrada, 8.694 de salida, 0,047 USD, 81 s (`96ae126`).

### Redacción literal de hechos y rondas de reparación

- **Causa.** En las primeras novelas de B3, `brief_coverage` (pre_publish) fallaba sobre
  hechos que el texto sí contaba, pero con otra forma ("el faro" cuando el hecho era "un
  faro"). Cada fallo gastaba la única ronda de reparación.
- **Efecto.** La instrucción del editor exige que cada hecho planificado aparezca al menos
  una vez con su expresión literal (`app/novel/roles.py`, "si el hecho es «un faro», el
  texto contiene «un faro»"). Se prefirió eso a relajar la coincidencia del validador, que
  dejaría pasar hechos ausentes.

### `change_fact` y el nombre antiguo

- **Causa.** Cambio en vivo de la mascota (`pet.toby.name` → `Nala`): el hecho del nombre
  cambió, pero un recuerdo ("El rescate de …") y capítulos que no "usaban" el hecho del
  nombre seguían con el antiguo; el juez de la versión nueva lo marcó como incoherencia.
- **Efecto.** Si el hecho es un nombre, `change_fact` busca el nombre antiguo como palabra
  completa en los demás hechos, en el brief, en el plan y en el texto de los capítulos
  publicados; todos esos capítulos entran en el conjunto afectado, y reparto, hechos
  derivados y brief se renombran (`pipeline.change_fact`, `_bible_ext.rename_cast`).
- **Resultado.** Novela de 2 capítulos → versión 2 publicada, 0 apariciones del nombre
  antiguo y 16 del nuevo, versión 1 intacta (`ab4731f`).

### Longitud y variante del español

- **Causa.** Smoke de 1 capítulo: el editor resumía al unir escenas y a veces usaba
  variantes no peninsulares.
- **Efecto.** Prompts de writer/editor en español peninsular; el editor recibe el número de
  palabras de las escenas y la orden de no condensar; un solo ajuste de longitud antes de
  `chapter_close`. Resultado: publicado, 1.067 palabras, 0,30 USD, 7 llamadas, ~6,5 min
  (`7fbc8b0`).

### Comentario del juez como JSON

- **Causa.** El juez devolvió el comentario general como una cadena que contenía otro
  objeto JSON, que acababa tal cual en la evidencia.
- **Efecto.** Los prompts `judge_chapter.md` y `judge_novel.md` dicen que
  `comentario_general` es texto plano en español, no un objeto JSON. Comprobación en vivo
  posterior: esquema validado en las dos llamadas (5/5/5/5 al capítulo bueno, 1/1/1/1 al
  malo) (`35d3a83`).

## Lean

- **`decide` → `decide +kernel`.** Con el `decide` normal, la reducción en el elaborador
  superaba `maxRecDepth` hacia los ~100 eventos; `+kernel` delega en el kernel y aguanta 300
  eventos en 17 s. `native_decide` se descartó (confía en el compilador).
- **Cronología válida antes de escribir.** Un fallo de Lean en `pre_publish` señala
  eventos, pero reescribir prosa no cambia filas de `chronology_event`; por eso el plan pasa
  `chronology_problems` (el mismo diagnóstico que B4) con un replan antes del primer
  capítulo.
- **Un proyecto Lean por novela.** Dos novelas simultáneas escribían el mismo `Story.lean`;
  `register_lean_for` copia `formal/lean` a `<dir de HARNESS_DB>/lean/<novel_id>`.
- **Caso real (L04):** Trueno en la boda de 2008 tras morir en 2005 (`b4-temporal`, plan
  sin prechequeo). Lo vieron Lean y `judge_novel`; `judge_chapter` y los validadores
  programáticos no. Detalle en [lean-caso-real](./lean-caso-real.md).
- **`noAfterExit` al eje de la historia** (tuning 1): comparaba `seq`; ahora la fecha, y el
  espejo Python solo da por salido al primer participante, como Lean (fila 20).

## Tests de contrato

- **Schemathesis y enteros enormes.** Un entero mayor de 64 bits en la ruta del lector
  provocaba `OverflowError` en SQLite y un 500. Las rutas acotan versión y capítulo a
  1..2³¹−1 y devuelven 422 (`312b142`; `openapi.json` regenerado en `e7b00b9`).

## Divergencias encontradas al mapear TLA+ a código

Al confirmar la tabla acción → código de [`formal/tla/README.md`](../../formal/tla/README.md#mapping-tla-action--code)
(esta rama) aparecieron tres diferencias. Estado: la 1 se acepta; la 2 y la 3 se
corrigieron en `fix/review-findings` (filas 15 y 16 de la tabla):

1. **Contador de reintentos de escena en memoria.** `write_scene` usa un bucle local
   (`MAX_SCENE_RETRIES = 2`). Un crash reinicia el capítulo desde la escena 1 con
   presupuesto nuevo. Es seguro porque las escenas no se guardan (V4) y el modelo tiene
   `sceneTry` como volátil; el `RetriesBounded` que protege el coste entre crashes es el de
   capítulo y el de reparación. Coste acotado por `MaxCrashes`.
2. **`change_fact` no es atómico.** El modelo trata `ChangeFact` como un paso atómico
   (regla 5 del README). En el código, `update_fact_value`, el renombrado y `save_brief` se
   confirman **antes** de `create_version_from` (que sí es una transacción). Un crash entre
   ambos deja el hecho con el valor nuevo y ninguna versión v+1; al reanudar, la última
   versión está publicada y el cambio se pierde en silencio. Propuesta: envolver todo en una
   transacción del repositorio. **Resuelto en `772f846`.**
3. **Figura 5 frente al código.** `docs/architecture.md` dice que un fallo de
   `chapter_close` "reescribe la escena señalada" y que al reanudar se conservan las
   escenas aceptadas; el código reescribe el **capítulo** con el editor y no conserva
   escenas (V4). El modelo TLA+ ya sigue al código. El documento de diseño es de B0: se
   notifica al orquestador para un `docs:`. **Resuelto en `2c6edf8`.**

## Evals y tuning

Tablas completas: [`evals/results.md`](../../evals/results.md) (antes y después) y
[`evals/results/tuning.md`](../../evals/results/tuning.md) (`compare_iterations.py`).
Todos los roles en Haiku 4.5; ningún rol subió de modelo.

### Iteración de tuning 1

**Antes** (`evals/results/before/`, 3 capítulos; y la novela de 10 capítulos de `ejemplo`
en `data/harness.sqlite`):

- `b2-infantil` y `b3-injection` → `blocked`: `brief_coverage` no reconocía recuerdos que
  el texto contaba ("El caracol campeón", "La primera inmersión", "La cámara perdida"). El
  resto de validadores ✅.
- `b4-temporal` → parado en el plan tras 2 intentos por `noAfterExit` sobre el
  protagonista (falso positivo, fila 20).
- `ejemplo` (10 cap.) → los 10 capítulos escritos y `judge_novel` suspendido dos veces:
  caps. 1 y 2 contaban ambos la última clase, el cap. 6 saltaba a "tercera semana" sin
  anclaje, y bloqueos "posibles" que el juez no podía citar; la ronda de reparación única
  reabrió casi todos los capítulos mencionados en las justificaciones.

**Cambio** (un commit por pieza, specs revisadas en su sitio con aprobación delegada):

| Pieza | Qué | Versión de prompt (Langfuse, `llm_call.prompt_version`) |
|---|---|---|
| Validador `brief_coverage` | recuerdos por palabras de contenido normalizadas (spec 008) | — |
| Lean + `diagnose` | `noAfterExit` por fecha de la historia, solo el primer participante (spec 012) | — |
| Planner | `time_marker` / `flashback` por capítulo; rechazo de marcas ausentes o que retroceden y de capítulos con el mismo núcleo; `MAX_REPLANS = 2` | `planner` 2 → 3 / 4 (mismo fichero; dos números porque otro worktree publicó en el mismo proyecto de Langfuse durante el run) |
| Writer | lista de hechos `plan/facts-checklist.txt` con detalles reconocibles; abrir cada capítulo anclando el salto temporal; no adelantar el siguiente | `writer` 3 → 4 |
| Editor | lo mismo, sinopsis del capítulo anterior y siguiente, resumen que empieza por la marca temporal | `editor` 3 → 4 |
| Juez | `Issue {descripcion, capitulos, severidad}`; solo bloquea `alta` concreto; umbrales D11 iguales | `judge_chapter` 1 → 2, `judge_novel` 1 → 2 |
| Reparación | se reabren `capitulos_a_reparar` (y los de defectos `alta`), con resúmenes vecinos; `MAX_REPAIR_ROUNDS` 1 → 2, TLC re-ejecutado sin error (5.492.531 estados distintos) | — |

**Después** (`evals/results/after/`):

| Brief | Antes | Después | Validador decisivo |
|---|---|---|---|
| `b2-infantil` | blocked (`brief_coverage` ❌) | **published** v1, 0,97 USD | todos ✅ |
| `b3-injection` | blocked (`brief_coverage` ❌) | **published** v1, 1,02 USD | inyección ⚑ (prescan + extractor), `forbidden_words_*` ✅ |
| `b4-temporal` | pipeline_error (plan) | **blocked** v1 (timeout de 45 min en la 1.ª ronda de reparación), 1,93 USD | plan: `noAfterExit` real (Trueno en la boda) → replan; escritura: `judge_chapter` y `judge_novel` ❌ por la edad contradictoria del propio brief |
| `b5-contradiction` | rechazado | rechazado | `brief_schema` |

Métrica: novelas publicadas 0/3 → 2/3 entre las generables; `b4` pasa de un falso positivo
en el plan a un bloqueo por una contradicción que sí existe en el brief (resultado esperado
en `evals/README.md`). Coste medio por novela publicada ~1,0 USD (antes ~1,2 USD por
novela bloqueada).

**Qué sigue fallando.** `b4`: la trampa de edad ("con 10 años" en 1994, nacido en 1980) no
tiene lectura coherente; el juez rechaza tanto "diez" como "catorce años", así que agota
reparaciones — correcto como bloqueo, caro en tiempo (la segunda ronda no cabe en los
45 min del harness). Julia, emigrada "y no ha vuelto", aparece en 2015 sin que nadie lo
señale (el planner no crea evento `departure`; [L04](./lean-caso-real.md)). La novela de
10 capítulos de `ejemplo` no se ha regenerado en esta iteración. No se hizo `after2`: lo
que falla en `b4` es del brief, no de un prompt o un validador.

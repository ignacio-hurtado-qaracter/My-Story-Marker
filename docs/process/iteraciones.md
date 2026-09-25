# Registro de iteraciones

> Registro (spec 004, D10). No es un diario: cada entrada es **causa → efecto**, con el
> artefacto que la prueba. Las entradas van por origen: model checking, ejecuciones en
> vivo, Lean, tests de contrato, evals y tuning.

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
| 24 | Novela de 10 cap. en vivo | `judge_novel` bloqueó `novela-ejemplo-final` tras 2 rondas: días de la semana que contradicen su fecha (21, 23 y 24 de junio de 2026) y «treinta años» de una carrera 1992–2026; el propio plan decía «El domingo de mañana, veintitrés de junio» (martes) | Días de la semana y cifras calculados en Python (`calendar_facts.py`, `plan/calendar.txt`); validador `calendar_consistency` en `chapter_close`; el editor puede quitar el día | spec 007 AC 8, spec 008 AC 8, [tuning 2](#iteración-de-tuning-2) |
| 25 | Novela de 10 cap. en vivo (tras tuning 2) | Mismo brief `ejemplo`, código de `81e1518` | `novela-ejemplo-a` **publicada v1 en el primer `pre_publish`**, 0 rondas de reparación; `calendar_consistency` 11/11; `judge_novel` 0,88 | `data/logs/novela-ejemplo-a.log`, [`ejemplos/novela-ejemplo.pdf`](../../ejemplos/novela-ejemplo.pdf), [tuning 2](#iteración-de-tuning-2) |
| 26 | Cambio del lector en vivo | `change-fact pet.canela.name Nala` sobre `novela-ejemplo-a` v1 | v2 publicada: capítulos 1 y 3–10 regenerados, el 2 copiado; v1 intacta (Canela 44 / Nala 0 en v1; Canela 0 / Nala 45 en v2) | `data/logs/change-nala.log`, `0e8118c`, [`ejemplos/novela-ejemplo-v2-cambio-nala.pdf`](../../ejemplos/novela-ejemplo-v2-cambio-nala.pdf) |
| 27 | Novela de 10 cap. en vivo (paralela) | `novela-ejemplo-b`, mismo código: un evento del plan sin lugar (`place_id` nulo) pasa el chequeo del plan, pero la exportación a Lean lo rechaza en `pre_publish` | Parada con `repair_limit` tras 2 rondas inútiles (6,05 USD): la reparación reescribe prosa, no el plan. Corregido en la fila 28 | `data/logs/novela-ejemplo-b.log`, `validator_result` de `lean_chronology` |
| 28 | Novela de 10 cap. en vivo (fila 27) | Un evento del plan sin lugar conocido llega a Lean como `place_id` nulo; la exportación falla y ninguna reescritura de prosa lo arregla, así que las rondas de reparación se gastan en vano | El chequeo del plan rechaza todo evento cuyo lugar no resuelva a un lugar del plan o de la biblia («El evento eN del capítulo C no tiene lugar») → replan; el evento sin lugar hereda el de su escena; la exportación sigue estricta y, si falla, la ejecución para con `chronology_export_error` (error de datos del plan) sin gastar rondas | spec 007 AC 9, `test_event_without_place_is_rejected_or_inherits_the_scene_place` |

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

### Iteración de tuning 2

**Antes** (`novela-ejemplo-final` en `data/harness.sqlite`, brief `evals/briefs/ejemplo.json`,
log `data/logs/novela-ejemplo-final.log`): los 10 capítulos escritos y bloqueada con
`repair_limit` tras 2 rondas de reparación. `judge_novel`: «[alta; cap. 4, 5, 6]
Contradicción temporal verificable: cap. 4 sitúa el 21 de junio como domingo; cap. 5 … el
23 como martes; cap. 6 asigna al 24 de junio la etiqueta "lunes"»; en la ronda anterior,
«el 21 de junio como sábado; … el 23 como domingo». Además, «treinta años» frente a los 34
de carrera que dan las fechas del brief (1992–2026).

**Causa.** Nadie calcula el calendario: el writer inventa el día de la semana de cada fecha
y cada reescritura de reparación inventa otro, así que las rondas no convergen. El error
nacía ya en el plan: la marca temporal del cap. 5 era «El domingo de mañana, veintitrés de
junio», y el 23 de junio de 2026 es martes. Las duraciones salen igual: el brief dice
«treinta años» en la descripción de Valdelosa, el recuerdo más antiguo es de 1992 y el
presente de la historia es 2026; el writer usaba «treinta y cuatro» o «treinta» según el
capítulo. Ningún validador programático miraba fechas en la prosa: solo el juez, una
llamada cara por ronda.

**Cambio** (deterministas; specs 007 y 008 revisadas en su sitio con aprobación delegada):

| Pieza | Qué |
|---|---|
| Plan (`app/novel/calendar_facts.py`) | Tras pasar `check_plan`, `enrich_plan_calendar` corrige en Python todo día de la semana que el planner escribió junto a una fecha y añade a cada `time_marker` sus fechas reales (`[fechas: domingo 21 de junio de 2026]`). `ctx.extra["plan"]` da a cada capítulo su `calendar`. El prompt del planner ya no pide días de la semana |
| Writer y editor | Documento `plan/calendar.txt`: «Fecha: domingo 21 de junio de 2026 (usa exactamente este día de la semana si lo nombras)» por escena y un bloque de **cifras canónicas** calculado solo de fechas del brief con los dos extremos conocidos: presente de la historia, edades, años cumplidos desde cada recuerdo fechado y edades entonces. Una cifra redonda del brief se sustituye por la calculada o por una expresión compatible («más de treinta años») |
| Validador `calendar_consistency` | `chapter_close`, bloqueante, `app/validators/programmatic/calendar.py`: «<día> [,] [el] <n> de <mes> [de <año>]» y «el <n> de <mes>, <día>», con el número en cifras o en letras; año explícito, o el del plan. Falla con «El capítulo dice «…», pero el 23 de junio de 2026 es martes. Corrige el día de la semana o elimínalo» |
| Reparación | La tarea de reescritura del editor dice que un fallo de `calendar_consistency` se arregla con el día que da el feedback o, más sencillo, quitando el nombre del día |

Comprobación sobre la novela bloqueada (solo lectura): `enrich_plan_calendar` corrige la
marca del cap. 5 a «El martes de mañana, veintitrés de junio»; el validador acepta los
textos finales de los caps. 4 y 5 («Domingo por la mañana, el veintiuno de junio»,
«martes veintitrés de junio»). El «lunes» del cap. 6 que citó el juez no va junto a una
fecha en el texto final: es el hueco que queda (días sin fecha, abajo).

**Efecto esperado.** Ninguna contradicción de día de la semana llega a `judge_novel`: la del
plan se corrige antes de escribir y la de la prosa se para en `chapter_close` con una
corrección mecánica (sin gastar ronda de reparación). Las cifras de años y edades son las
mismas en los 10 capítulos. Métrica: `novela-ejemplo-final` (o su repetición) publicada, o
bloqueada por un motivo distinto del calendario.

**Límites conocidos.** No se validan días de la semana sin fecha al lado («aquel lunes»)
ni duraciones en la prosa («treinta años»): las cifras van por el prompt. El plan de
`novela-ejemplo-final` también encadena el cap. 6 («al atardecer del mismo día») con una
fecha distinta a la del cap. 5; eso es del chequeo de marcas temporales, fuera de esta
iteración.

**Después** (causa → cambio → efecto, medido).

- **Causa**: días de la semana y cifras inventados por el writer en cada reescritura; las
  rondas de reparación no convergían (`novela-ejemplo-final`, bloqueada tras 2 rondas,
  4,61 USD).
- **Cambio**: calendario y cifras canónicas calculados en Python y validador
  `calendar_consistency` (tabla de arriba), en el código de `81e1518`.
- **Efecto**: `novela-ejemplo-a` (mismo brief `evals/briefs/ejemplo.json`) **publicada v1
  en el primer `pre_publish`, con 0 rondas de reparación**. 10 capítulos de 1.006 a
  1.170 palabras (10.645 en total), 55 llamadas, 3,10 USD, ~69 min (23:47 → 00:56 UTC).
  Validadores: `scene_accept` 30/30 en sus 3 validadores; `chapter_close` todo en verde,
  incluido `calendar_consistency` 11/11; `judge_chapter` 10 aprobados y 1 suspenso que se
  resolvió con la reescritura del editor; `pre_publish`: `brief_coverage`,
  `lean_chronology` y `schema_brief` ✅, `judge_novel` ✅ 0,88 (5/4/4/4), `visual_check`
  omitido (`VISUAL_CHECK` sin activar). PDF:
  [`ejemplos/novela-ejemplo.pdf`](../../ejemplos/novela-ejemplo.pdf).

| Intento (brief `ejemplo`, 10 cap.) | Código | Resultado | Rondas | Coste |
|---|---|---|---|---|
| `novela-ejemplo` | antes del tuning 1 | bloqueada por `judge_novel` (saltos de tiempo, solape) | 1 | 3,68 USD |
| `novela-ejemplo-final` | tuning 1 | bloqueada por `judge_novel` (día de la semana ≠ fecha) | 2 | 4,61 USD |
| `novela-ejemplo-a` | tuning 2 (`81e1518`) | **publicada v1** | 0 | 3,10 USD |
| `novela-ejemplo-b` | tuning 2 (`81e1518`) | parada con `repair_limit` por `lean_chronology` (exportación, abajo); `judge_novel` aprobado 0,88 | 2 | 6,05 USD |

Métrica de la iteración: la contradicción de calendario desapareció de `judge_novel` en las
dos ejecuciones con el código nuevo (ninguna la citó); el juez de novela acabó aprobando en
las dos (0,88).

**Demostración del cambio del lector sobre la novela publicada.** `change-fact
pet.canela.name Nala` sobre `novela-ejemplo-a`: v2 publicada con los capítulos
[1, 3, 4, 5, 6, 7, 8, 9, 10] regenerados y el 2 copiado (no nombra a la mascota); v1 se
conserva intacta: «Canela» aparece 44 veces en v1 y 0 en v2, «Nala» 0 en v1 y 45 en v2.
~27 min, ~0,94 USD. PDF con la página «Novedades»:
[`ejemplos/novela-ejemplo-v2-cambio-nala.pdf`](../../ejemplos/novela-ejemplo-v2-cambio-nala.pdf)
(`0e8118c`).

**Qué sigue fallando: `novela-ejemplo-b`** (ejecución paralela con el mismo código, log
`data/logs/novela-ejemplo-b.log`, terminada a las 02:16 UTC del 25-09). Necesitó 3 planes: el
chequeo de cronología rechazó el primero (`agesCoherent`: un personaje en un evento
anterior a su nacimiento) y el segundo (11 × `noAfterExit`: un personaje que reaparece
tras su salida). Escribió los 10 capítulos y falló el primer `pre_publish` por
`judge_novel` (dos capítulos contaban «la última clase» en fechas distintas) y por
`lean_chronology`: «chronology export failed: events[21].place_id: unknown id None». La
1.ª ronda (caps. 3, 4 y 6) arregló al juez (aprobado, media 4,20), pero `lean_chronology`
volvió a fallar igual y abrió la 2.ª ronda sobre los 10 capítulos. Tras ella, el tercer
`pre_publish` aprobó todo menos Lean (`judge_novel` 0,88, media 4,40) y la ejecución terminó
en `stopped_error` con `repair_limit`: 91 llamadas, 6,05 USD, ~2 h 28 min. El fallo de Lean
no es de la prosa: un evento del plan no tiene lugar (1 de 30 con `place_id` nulo) y la
exportación lo exige, así que ninguna reescritura lo podía arreglar y las dos rondas se
gastaron en vano. **Arreglado después de esta ejecución** (fila 28, spec 007 AC 9): el
chequeo del plan rechaza los eventos sin lugar conocido y pide un replan, un evento sin
lugar hereda el de su escena, y si aun así la exportación a Lean falla la ejecución para
enseguida con `chronology_export_error` («error de datos del plan») en vez de gastar
rondas de reparación en la prosa. La exportación sigue exigiendo un lugar por evento.

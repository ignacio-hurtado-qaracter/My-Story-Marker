# Proceso 0 · Ronda 2 · Reencuadre al producto de novelas personalizadas

Rama `exam/rescope`. Preparado el 2026-09-23, tras las respuestas a las preguntas 5, 6, 7,
8 y 9 de la [ronda 1](./round-1-rescope.md).

Igual que en la ronda 1: número y "ok" acepta la recomendación; número y alternativa la
cambia. Nada de `docs/`, `AGENTS.md` ni specs nuevas se edita hasta confirmar el resumen.

---

## Hechos nuevos desde la ronda 1

- La sesión del backend ha avanzado la spec 001 hasta el paso 16: índice derivado,
  `dossier`, `select_entities`, `assemble_context`, cliente `claude -p`, auditoría
  mecánica, `promote`/`rule`/`reconcile` y tool sets derivados de la tabla de permisos.
- `specs/` ahora usa **una carpeta por spec** (`specs/NNN-slug/NNN-slug.md` y su `-plan.md`),
  y `AGENTS.md` lo recoge (commit `5b9bf5d`).
- El número **002 ya está usado**: `specs/002-frontend-foundation/` está aprobada y tiene
  plan en borrador, en un tercer worktree (`My-Story-Marker-frontend/`, rama
  `spec/002-frontend-foundation`). Construye la base del frontend y una "semilla" de
  lector: índice por capítulo desde `GET /structure/chapters` y una página por escena.
  Deja fuera de su alcance la entrevista, la dedicatoria, las fichas y el resto de
  pantallas de producto, que remite a specs propias.
- `exam/rescope` ya incluye todo eso por merge en un solo sentido (commit `c8c38fa`).

---

## Preguntas nuevas, derivadas de tus respuestas

### De la 7: un capítulo tiene varias escenas

**20. Escenas por capítulo.** El planner decide entre 2 y 4 escenas por capítulo y reparte
el rango de 1.000-1.500 palabras del capítulo en presupuestos por escena que suman el total.
*Recomendación:* sí. El número de escenas no es fijo para no forzar la estructura, y el
presupuesto por escena reutiliza el campo `budget` que ya tiene el registro de escena.

**21. Dónde corre cada validador.** Dos puntos, porque ahora escena y capítulo no coinciden.
- **Al aceptar cada escena** (dentro del turno de la Figura 4): auditoría mecánica, guardrail
  de palabras prohibidas y schema de la salida.
- **Al cerrar el capítulo**: longitud del capítulo en rango, nombres exactos, cobertura de
  los elementos obligatorios del brief hasta ese capítulo, y el juez con rúbrica.

Un fallo de capítulo se devuelve a la escena donde está la evidencia. Si no se puede
localizar, como una longitud corta, el planner reajusta los presupuestos y el writer amplía
la última escena.
*Recomendación:* sí. El enunciado pide el guardrail "sobre cada capítulo antes de
aceptarlo"; aplicarlo por escena y repetirlo al cerrar el capítulo lo cumple de sobra.

**22. Checkpoint y reanudación.** Un capítulo está completo cuando todas sus escenas están
aceptadas, su resumen de capítulo está escrito y sus validadores de cierre pasan. Tras un
fallo, se reanuda en el primer capítulo incompleto y se conservan sus escenas ya aceptadas.
*Recomendación:* sí. En TLA+ el modelo razona por capítulos, como pide el enunciado, con
las escenas como un contador dentro de cada capítulo para que el espacio de estados siga
siendo pequeño.

**23. Granularidad del uso de hechos.** La tabla de uso registra hecho → **escena**; los
capítulos que usan un hecho se derivan. Un cambio del lector regenera solo las escenas que
usan el hecho y marca sus capítulos como cambiados.
*Recomendación:* sí. Regenerar por escena rompe menos continuidad que regenerar capítulos
enteros, y es lo que `reconcile` ya sabe hacer.

### De la 6: SQLite autoritativo

**24. Varias novelas.** Hoy un árbol de stores (`STORY_ROOT`) es una novela. El producto
genera muchas, cada una con versiones.
- **a)** Un árbol de stores por novela (`NOVELS_ROOT/<novel_id>/canon/ … manuscript/`) y
  **una** base SQLite autoritativa con `novel_id` en cada tabla, que también guarda las
  listas globales de palabras prohibidas y el audit log.
- **b)** Un árbol y una base SQLite por novela, más una base global aparte.

*Recomendación:* **a**. Una sola base facilita las listas globales, el audit log, la
consulta de versiones y el `list_novels` del servidor MCP opcional. Obliga a cambiar
`STORY_ROOT` por una raíz de novelas en el backend, y eso irá en una spec de implementación.

**25. Dónde vive esa base.** No puede ir en `.index/`, que es derivado, reconstruible e
ignorado por git.
*Recomendación:* un fichero propio, por ejemplo `data/harness.sqlite`, con su ruta en una
variable de entorno y sus migraciones separadas de las del índice derivado. El índice
derivado sigue igual.

**26. Hechos del brief frente a los ficheros de canon y cast.** Un hecho como "el perro se
llama Nala" podría acabar en SQLite y en `cast/`.
*Recomendación:* la tabla de hechos de SQLite es la autoridad de todo hecho que viene del
brief. Los ficheros que escribe el planner citan el id del hecho. Un cambio del lector
actualiza el hecho, `reconcile` encuentra las escenas afectadas, y el rol dueño reescribe
el fichero. Así un hecho nunca tiene dos versiones.

**27. Versiones de la novela.** Tabla de versiones más una fila por capítulo y versión con
su texto y su hash. Publicar crea una versión nueva y ninguna se borra. "Capítulos
cambiados" es comparar hashes entre versiones.
*Recomendación:* sí, en lugar de commits de git hechos por el backend, que la spec 001
dejó fuera.

### De la 9: lector web

**28. Quién redacta las specs del lector.** Portada con dedicatoria, fichas de personajes y
lugares, cambio desde la página y marcado de capítulos cambiados.
*Recomendación:* esta sesión las redacta cuando el reencuadre esté aprobado, porque
dependen de las decisiones 6, 23 y 27. La sesión del frontend las implementa sobre la base
de la spec 002.

---

## Preguntas de la ronda 1 que siguen abiertas

Resumidas; el razonamiento completo está en la [ronda 1](./round-1-rescope.md).

| # | Pregunta | Recomendación |
|---|---|---|
| 1 | Intención: cumplir el enunciado reencuadrando `docs/` y reutilizando la spec 001 | Sí, sin reescribir desde cero |
| 2 | Fuera de alcance: pagos, cuentas, impresión, ilustraciones, audio, despliegue; opcionales al final | Sí; el primer opcional, el servidor MCP de solo lectura |
| 3 | Ramas: `exam/rescope` recibe merges de `spec/001-backend` **y ahora también de `spec/002-frontend-foundation`**, en un solo sentido; `main` nuevo al final; tag `legacy-story-creator` | Sí; mover `main` solo con tu confirmación en ese momento |
| 4 | Capa y orden: spec de reencuadre antes que los commits `docs:`. **Como 002 está usado, la spec de reencuadre toma el 003**, y las otras sesiones empiezan en 004 | Sí; avisa a las otras sesiones de que 003 está reservado |
| 10 | Idioma: novela, README y presentación en español; `docs/`, specs y código en inglés; `EMBED_MODEL` multilingüe antes del primer `rebuild()` real | Sí |
| 11 | Langfuse en el backend con su SDK y claves en `backend/.env` | Sí; el `TurnRecord` pasa a ser el payload de los spans |
| 12 | Dos hooks: un código en el backend y dos disparadores (orquestador y `.claude/settings.json`) | Sí |
| 13 | Tools con schema | (b) dos tools de lectura, `query_story_bible` y `get_chapter_summary`, por un MCP local |
| 14 | Herramientas formales: `elan` y JRE con `tla2tools.jar` fijado; `formal/lean/`, `formal/tla/` | Sí; Docker como alternativa |
| 15 | Invariantes: Lean, orden temporal y edad; TLA+, publicación solo validada, reanudación sin duplicar ni perder, reintentos acotados, y terminación | Sí |
| 16 | Verificación del reencuadre: **A** (`exam/check.py`, enlaces, Mermaid) e **I** (tu revisión) | Sí |
| 17 | Memoria en `.claude/memory/`, copia curada sin rutas personales ni credenciales | Sí |
| 18 | ¿Dónde está MyFactory? Ruta local o URL | Necesito el dato |
| 19 | Rotar la clave de Langfuse que está en claro fuera del repo | Hoy |

---

## Respuestas del usuario (2026-09-23)

| # | Respuesta |
|---|---|
| 4 | **Numeración.** Las specs de esta rama empiezan en 003 y siguen sumando; si otra rama crea más specs antes, se toma el siguiente número libre. No hace falta reservar nada con las otras sesiones. |
| 20 | **Entre 4 y 7 escenas por capítulo**, no entre 2 y 4. |
| 21 | Recomendación: validadores al aceptar cada escena y al cerrar el capítulo. |
| 22 | Recomendación: se reanuda en el primer capítulo incompleto, conservando sus escenas aceptadas. |
| 23 | Recomendación: uso de hechos por escena; capítulos derivados. |
| 24 | Recomendación (a): un árbol de stores por novela y una base SQLite autoritativa con `novel_id`. |
| 25 | Recomendación: base propia (p. ej. `data/harness.sqlite`), fuera de `.index/`, con migraciones separadas. |
| 27 | Recomendación: versiones en SQLite con texto y hash por capítulo. |

**Consecuencia de la 20, para la spec del bloque de generación.** Con 1.000-1.500 palabras
por capítulo, de 4 a 7 escenas dan escenas de unas 150 a 375 palabras, y una novela pasa a
tener de 40 a 70 turnos de la Figura 4. Hay que resolver dos cosas allí: el `literal_tail`
de 500 palabras es más largo que una escena, y el coste y la latencia por novela crecen con
el número de turnos.

**Cambio de enfoque propuesto por el usuario.** En lugar de un único reencuadre, una spec
general de brechas y hoja de ruta por bloques (003) y una spec por bloque después. Las
preguntas de detalle que quedan abiertas (11-17) pasan al Proceso 0 de la spec de su
bloque. La spec 003 solo necesita cerrar las transversales: 1, 2, 3, 10, 26 y 28.

## Lo que ya está decidido y entrará en el resumen

- `docs/process/` como área de registro (5).
- SQLite autoritativo para lo nuevo; prosa, canon y cast en ficheros (6).
- Capítulos compuestos por varias escenas (7).
- Roles: entrevistador, planner, writer, editor y juez, sin ampliar ningún permiso (8).
  El entrevistador escribe solo el brief y no lee stores; el juez lee manuscrito, brief y
  story bible y escribe solo resultados de validación.
- Lector web y exportación a PDF (9).

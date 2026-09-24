# Proceso 0 · Ronda 4 · Qué ha corregido ya la rama del backend

Rama `exam/rescope`. Preparado el 2026-09-24.

Revisión **en solo lectura** de `spec/001-backend` en el commit `ce1362c`, frente a lo que
`exam/rescope` tenía del backend (hasta `9f184f9`). El objetivo es saber qué huecos y
contradicciones de las rondas anteriores se han resuelto ya mientras se seguía trabajando,
para no pedir a la spec 004 que decida lo que ya está hecho.

Método: lista de commits y de ficheros cambiados; el comprobador `exam/check.py` sobre una
copia exportada de la rama, en un directorio temporal; y lectura del código detrás de cada
requisito que el comprobador daba por cumplido. Después, `spec/001-backend` se trajo a
`exam/rescope` con un merge en un solo sentido (`7aa9bbf`), sin conflictos.

---

## Resumen

- **`docs/` y `AGENTS.md` no han cambiado.** Las once contradicciones y ausencias del
  adelanto de la [ronda 3](./round-3-rescope.md) siguen todas en pie.
- **El código ha avanzado mucho:** orquestador del turno completo, roles invocados por
  modelo, pruebas en vivo, integración continua, base del frontend y la spec 003 de
  identidad visual.
- **Cumplimiento:** de 13 a **17 de 72** obligatorios comprobables. Con los criterios
  anteriores el comprobador habría marcado 21; cuatro eran falsos positivos y se han
  corregido sus criterios (`cdf7504` y el commit de esta ronda).

---

## Lo que ya está resuelto o avanzado

| Requisito del enunciado | Qué hay ahora en `spec/001-backend` | Veredicto |
|---|---|---|
| **Retries con límite** (H06) | El turno revisa como mucho `TURN_MAX_REVISIONS` veces y escala; una salida con schema inválido se reintenta una vez y falla; los rechazos del modelo escalan con su categoría; una revisión que reescribe demasiado se rechaza (`agents/turn.py`, `agents/service.py`) | **Resuelto a nivel de escena.** Falta aplicarlo al guardrail de palabras prohibidas y al cierre de capítulo |
| **Orquestador** (base de TLA+) | Máquina de estados de la Figura 4 con resultados `merged`, `escalated` y `awaiting_ruling`, cerrojo, registros por paso, reanudación, fallos humanos y SSE (`agents/turn.py`, `agents/router.py`) | **Resuelto para una escena.** Da estados y transiciones reales para mapear la especificación TLA+ |
| **Resúmenes por capítulo** (M03) | Resumen por escena y agregado por capítulo y arco (`POST /agents/digests/rollup`); el ensamblado carga los resúmenes de capítulo | **Resuelto** |
| **Checkpoint y reanudación** (M04) | `POST /agents/turns/{id}/resume` continúa un turno interrumpido sin repetir la escritura | **Parcial.** Reanuda un turno, no una novela desde el último capítulo completo (decisión 22) |
| **Roles** (H01) | Writer (`write`, `revise`, `digest`, `rollup`), style editor (`polish`), auditor mecánico y semántico, canoniser (`extract`) | **Parcial.** Faltan planner, entrevistador y juez (decisión 8) |
| **Salida de cada rol validada** (V04, mitad) | Pydantic estricto, sin reparar; reintento único | **Resuelto.** Falta el schema del brief |
| **Tools con schema** (H05) | Tool sets derivados de la tabla de permisos (`commons/permissions/toolsets.py`); el modelo sigue sin tools | **Parcial.** Depende de la pregunta 13 |
| **Tokens por llamada** (observabilidad) | El registro del turno guarda modelo, `prompt_version` (hash del prompt) y tokens, incluidas lecturas de caché | **Base lista.** Ni Langfuse ni coste todavía; volcarlo a spans es directo |
| **Lector** (R01, R02) | Frontend con índice por capítulos y escenas, página de escena y escena 3D bajo demanda; spec 003 le da la identidad visual del sitio antiguo | **Parcial.** Sin portada con dedicatoria, fichas ni cambios del lector |
| **Integración continua** | `.github/workflows/backend.yml` y `frontend.yml` | **Resuelto.** En el análisis inicial no existía |
| **Contrato de la API** | `openapi.json` regenerado y `schemathesis` sobre todas las rutas | **Resuelto en el commit.** Los dos tests de contrato que fallaban al empezar deberían pasar; no se han vuelto a ejecutar aquí |

## Falsos positivos corregidos en el comprobador

| Requisito | Por qué saltaba | Estado real |
|---|---|---|
| V01 Longitud de capítulo | Un límite de palabras del **campo de idioma** (`LANGUAGE_MAX_WORDS`) | No existe validador de longitud de capítulo |
| G02 Normalización | `unicodedata` en el canoniser, para **deduplicar hechos** | El guardrail de palabras prohibidas no normaliza acentos ni plurales |
| H01 Planner | `plan_rollup`, que planifica un **resumen** | No hay planner |
| M04 Checkpoint | Reanudación de **un turno** | No hay checkpoint por capítulo |

---

## Hallazgos del backend que tocan el enunciado

La spec 001 dejó anotados, el 2026-09-24, varios hallazgos para más adelante. Tres afectan
a requisitos del examen y conviene que la spec 004 los recoja como filas:

- **`literal_tail` por orden de discurso.** Una analepsis recibe el final de una escena
  posterior en tiempo de historia. Con 4-7 escenas por capítulo (decisión 20) la escena es
  más corta que ese fragmento, así que el problema crece. Toca continuidad y saltos
  temporales, que el examen prohíbe.
- **La procedencia no lleva id de escena ni de turno** en las escrituras del borrador, el
  resumen, la propuesta y la auditoría. Toca el audit log y la trazabilidad por capítulo que
  pide el examen.
- **La explicación de una violación semántica no se guarda.** El examen pide que cada
  validador dé una justificación.

Y uno del frontend: la spec 003 deja fuera, **"cada uno candidato a su propia spec"**, una
vista de personajes, una de resúmenes y una **vista de lectura de la novela completa**. Son
justo piezas del lector que exige el examen (fichas y lectura), así que la spec del bloque
de lectura debería reclamarlas.

---

## Preguntas

**32. Hallazgos aplazados del backend.** ¿Entran en la spec 004 como filas de la
confrontación los tres que tocan requisitos del examen (`literal_tail`, procedencia sin id,
explicación no guardada)?
*Recomendación:* sí, con la resolución "lo decide la spec del bloque X". Los demás se
quedan en la spec 001.

**33. Vistas que la spec 003 deja fuera.** ¿La spec del bloque de lectura reclama la vista
de personajes y la de lectura completa como parte de las fichas y del lector del examen?
*Recomendación:* sí. Se anota en la spec 004 para que la sesión del frontend no las
diseñe por su cuenta con otra forma.

**34. Sincronización.** Se ha hecho un merge de `spec/001-backend` en `exam/rescope`
(`7aa9bbf`) para que la spec 004 cite el código actual. ¿Se mantiene como regla repetirlo
antes de redactar cada spec de esta rama?
*Recomendación:* sí, siempre en un solo sentido y solo con la carpeta limpia.

---

## Respuestas del usuario (2026-09-24)

Tras leer el borrador de la spec 004: **"ok a todo"** a los valores por defecto de las preguntas 2, 10,
26 y 29-37, con un cambio: la decisión 20 pasa a **3-5 escenas por capítulo** (antes 4-7). Con ello el
Proceso 0 de la spec 004 queda cerrado.

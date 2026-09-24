# Proceso 0 · Ronda 1 · Reencuadre al producto de novelas personalizadas

Rama `exam/rescope`, worktree `My-Story-Marker-docs/`. Preparado el 2026-09-23.

Este documento es la primera ronda de preguntas de `AGENTS.md`, Proceso 0, para el
cambio más grande que queda: pasar de un harness genérico de novela larga a un producto
que genera novelas de regalo desde un brief. Cada pregunta trae una respuesta
recomendada. Hasta que el resumen final esté confirmado no se edita `docs/`, `AGENTS.md`,
`CLAUDE.md` ni se redacta ninguna spec nueva.

**Cómo contestar.** Basta con el número y "ok" para aceptar la recomendación, o el
número y la alternativa. Las preguntas marcadas *(depende de N)* pueden cambiar según
la respuesta a N y se reabren en la ronda 2.

---

## Hechos comprobados en el repositorio

Estos no se preguntan; se han mirado.

- `docs/` describe un harness de novela larga por escenas, con seis roles, stores en
  ficheros YAML/Markdown y SQLite como índice derivado y reconstruible
  (`architecture.md`, "Storage layout" y "Memory and context budget").
- La spec 001 está aprobada y su plan también. Los pasos 1-15 están hechos o en curso en
  la otra sesión. Deja fuera Langfuse, el frontend, las evals, el LLM-as-judge y los
  roles architect y world builder invocados por modelo (spec 001, "Out" y Decisión 5).
- El modelo se llama con `claude -p` y `--setting-sources ""` (plan 001, P14). Por eso
  los hooks de `.claude/settings.json` **no** se ejecutan dentro de las llamadas de rol.
- El modelo no recibe tools: la salida es estructurada y el orquestador escribe
  (spec 001, FR-PERM-06 y FR-AGENT-09).
- En la máquina hay Node 24, Python 3.12 y Docker. No hay Java, Lean ni TLC.
- El historial de git no contiene claves (escaneo de patrones de Langfuse, Anthropic,
  GitHub y AWS: 0 coincidencias). Hay una clave real de Langfuse en un fichero de notas
  **fuera** del repo, en la carpeta padre.
- `main` es el proyecto anterior (Story Creator: tres agentes, cuatro novelas, web
  estática) y no comparte ancestro con `spec/001-backend`.
- No se ha encontrado el repositorio MyFactory en esta máquina.

---

## Preguntas

### Intención y alcance

**1. Intención.** Lo que quieres que sea cierto al final, tal como lo entiendo: el
repositorio cumple el enunciado del examen, con el diseño de `docs/` reencuadrado al
producto de novelas de regalo, conservando lo construido en la spec 001 (stores,
permisos, índice, auditoría mecánica) como cimiento y no tirándolo.
*Recomendación:* sí, reencuadrar y reutilizar; no reescribir desde cero.

**2. Qué queda fuera.** Pagos, cuentas de usuario, impresión, ilustraciones, audio y
despliegue (fuera de alcance del enunciado). Los opcionales (servidor MCP, login, linters
de prosa, agente de seguridad) quedan para después de cumplir los obligatorios.
*Recomendación:* sí. Si sobra tiempo, el primer opcional es el servidor MCP de solo
lectura con FastMCP, porque reutiliza el backend y suma nota con poco coste.

**3. Estrategia de ramas.** `exam/rescope` recibe merges de `spec/001-backend` en un solo
sentido; nunca al revés hasta que el plan 001 termine. Al final, un `main` nuevo recibe
las dos ramas. El `main` actual se conserva con un tag `legacy-story-creator` antes de
moverlo.
*Recomendación:* sí. Mover `main` es irreversible en el remoto; se hará solo con tu
confirmación explícita en ese momento.

### Capa y orden

**4. Capa.** El reencuadre cambia invariantes (personalización, longitud), permisos (un
rol entrevistador nuevo) y la disposición de los stores (SQLite pasa a ser autoritativo).
`AGENTS.md`, Proceso 1, paso 3, exige una spec antes de editar docs cuando se toca
cualquiera de las tres.
*Recomendación:* redactar primero una spec **002 "Reencuadre: novelas personalizadas"**
que recoja las decisiones de esta ronda; tras tu aprobación, los commits `docs:`; después
las specs de implementación 003 en adelante.

**5. Dónde vive la documentación de proceso.** El enunciado pide en `/docs` la spec
inicial, trade-offs, explainers, diagramas, registro de iteraciones y red-team log. En
este repo `docs/` es la capa de diseño, la de más autoridad.
*Recomendación:* `docs/process/` como área de **registro**, que nunca define diseño y
solo cita a `docs/`. Se añade al mapa de `AGENTS.md` con una regla: se edita sin Proceso 1
salvo que afirme algo sobre cómo funciona el sistema, y sus commits usan `docs(process):`.

### Diseño del producto

**6. Autoridad de la story bible.** El enunciado exige SQLite para la story bible, con
uso por capítulo de cada hecho y tabla de cronología.
- **a)** SQLite autoritativo para lo nuevo: brief, hechos y su uso por capítulo,
  cronología, listas de palabras prohibidas, audit log de policy, versiones de la
  novela. La prosa sigue en `manuscript/` y canon y cast en ficheros.
- **b)** Migrar todos los stores a SQLite.
- **c)** Ficheros autoritativos y SQLite derivado, como hoy.

*Recomendación:* **a**. Cumple el enunciado sin deshacer la spec 001; la **c** arriesga
que un evaluador lea "SQLite derivado" como incumplimiento, y la **b** tira trabajo hecho.

**7. Unidad de generación.** El diseño actual escribe escenas; el producto escribe 10
capítulos.
*Recomendación:* un capítulo es un registro de escena (`scenes/NNN.yaml` ↔ capítulo NN,
1:1). Se reutilizan `assemble_context`, la auditoría y el turno sin cambios de forma, y el
presupuesto de palabras de la escena pasa a ser el rango 1.000-1.500.

**8. Roles.** El enunciado pide entrevistador, planner, writer y editor/critic.
*Recomendación:*
- **Entrevistador** nuevo. Escribe solo el brief. No lee canon.
- **Planner** es el architect invocado por modelo. Revoca la Decisión 5 de la spec 001.
  Su salida estructurada la escribe el orquestador bajo world builder para `canon/` y
  bajo architect para `structure/` y `scenes/`, de modo que ningún rol amplía permisos.
- **Writer** sin cambios.
- **Editor** es el style editor más el auditor.
- **Juez** nuevo, de solo lectura, que puntúa con la rúbrica y escribe solo scores.

*(Depende de 6.)*

**9. Formato de lectura.**
- **a)** Lector web en React con cambio desde la página, y exportación a PDF desde el
  backend.
- **b)** Solo PDF, con cambios por formulario o CLI y página de novedades.

*Recomendación:* **a**. El PDF de ejemplo es obligatorio igualmente, así que la
exportación se construye en ambos casos. El frontend ya está en el stack de `AGENTS.md`.
Si el calendario aprieta, **b** es la vía de escape y se decide en la ronda 2.

**10. Idioma.** La novela, el README raíz y la presentación en español; `docs/`, specs y
código en inglés, como hasta ahora.
*Recomendación:* sí. Consecuencia: `EMBED_MODEL` pasa al MiniLM multilingüe de 384
dimensiones **antes** del primer `rebuild()` real (Decisión R2-3 de la spec 001).

### Harness y observabilidad

**11. Langfuse en el backend.** La spec 001 lo dejó fuera. El enunciado lo exige: una
sesión por novela, spans por rol y tool, scores de todos los validadores y prompts
versionados. Hace falta el SDK de Langfuse en el backend y sus claves en `backend/.env`,
con marcadores en `.env.example`. No es una clave de Anthropic, así que no contradice la
Decisión R3-1.
*Recomendación:* sí. El `TurnRecord` que ya se persiste en `.index/` pasa a ser también
el payload de los spans, y el riesgo aceptado "`.index/` no reconstruible" se cierra.

**12. Los dos hooks del enunciado.** Los hooks de Claude Code no se ejecutan dentro de
`claude -p` con `--setting-sources ""`.
*Recomendación:* un solo código y dos disparadores. La validación de capítulo y la policy
viven en el backend como puntos de hook con nombre del orquestador, antes de aceptar un
capítulo y antes de cada escritura. Además, `.claude/settings.json` los expone como hooks
de Claude Code (`PostToolUse` sobre `manuscript/` y `PreToolUse` de policy) que llaman al
mismo código cuando una persona o Claude Code edita la novela a mano.

**13. "Tools con schema validado".** Hoy el modelo no tiene tools, por diseño.
- **a)** Mantenerlo y documentarlo como trade-off. Las entradas y salidas validadas son
  las operaciones del orquestador y el servidor MCP.
- **b)** Dar al planner y al editor tools de solo lectura (`query_story_bible`,
  `get_chapter_summary`) servidas por un MCP local, con JSON Schema.

*Recomendación:* **b** limitado a esas dos tools de lectura. Cumple el enunciado sin dar
al modelo ninguna escritura, y el mismo servidor MCP sirve para el opcional.

### Verificación formal y evals

**14. Herramientas formales.** Lean 4 con `elan` instalado en local, y TLC con un JRE y
`tla2tools.jar` en una versión fijada, descargado por un script y no commiteado. Carpeta
`formal/lean/` y `formal/tla/`.
*Recomendación:* sí. Docker queda como alternativa si la instalación local falla.

**15. Invariantes a priorizar.**
- **Lean:** orden temporal de eventos, y edad coherente con la fecha de nacimiento.
  Son las dos que más probablemente rompe un brief real ("mi abuela a los 20 años en
  1990" frente a su fecha de nacimiento).
- **TLA+:** nunca se publica un capítulo sin pasar todos los validadores; la reanudación
  no duplica ni pierde capítulos; los reintentos nunca superan el límite. Liveness: toda
  generación termina publicada o detenida con error.

*Recomendación:* esas.

**16. Verificación de este reencuadre.** Cómo sabrás que salió bien, en letras de la
Trust Spec.
*Recomendación:*
- **A:** `exam/check.py` sin regresiones y enlaces y Mermaid válidos (pasos 9-10 del
  Proceso 1).
- **I:** tu revisión de la spec 002 y de cada commit `docs:`.

### Logística

**17. Memoria de Claude Code en el repo.** El enunciado pide `.claude/` con memoria. La
memoria automática vive en tu perfil de usuario, fuera del repo.
*Recomendación:* una copia curada en `.claude/memory/`, sin rutas personales ni
referencias a credenciales, actualizada a mano cuando cambie algo relevante.

**18. MyFactory.** Necesito saber dónde está: ruta local o URL del remoto. Su commit final
va en el email de entrega.

**19. Clave de Langfuse fuera del repo.** Está en claro en un fichero de notas de la
carpeta padre.
*Recomendación:* rotarla hoy en Langfuse y borrar la línea del fichero. Añadir la regla
de "sin secretos" al gate del backend, igual que ya hace `exam/check.py`.

---

## Respuestas del usuario (2026-09-23)

| # | Respuesta |
|---|---|
| 5 | **Recomendación.** La documentación de proceso vive en `docs/process/`, área de registro. |
| 6 | **Recomendación (a).** SQLite autoritativo para brief, hechos y su uso, cronología, palabras prohibidas, audit log de policy y versiones. Prosa, canon y cast siguen en ficheros. |
| 7 | **Rechazada.** Un capítulo tiene **varias escenas**; no hay correspondencia 1:1. |
| 8 | **Recomendación.** Entrevistador nuevo, planner = architect invocado por modelo con escrituras bajo world builder y architect, writer, editor = style editor + auditor, juez de solo lectura. |
| 9 | **(a).** Lector web en React con cambio desde la página y exportación a PDF desde el backend. |

Las demás siguen abiertas y pasan a la [ronda 2](./round-2-rescope.md), junto con lo que se
deriva de estas respuestas.

## Qué pasa después

Con tus respuestas redacto el resumen de entendimiento compartido: intención, capa,
alcance dentro y fuera, ficheros a tocar y verificación. Si alguna respuesta abre
preguntas nuevas, habrá una ronda 2. Con el resumen confirmado, el siguiente artefacto es
el borrador de la spec 002.

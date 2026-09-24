# Punto de situación · sesión "Examen final storyMaker" · actualizado 2026-09-24

Documento de trabajo para retomar desde otro dispositivo. **No forma parte de `docs/`** ni
del diseño: es un traspaso de contexto. Recoge dónde estamos, qué se habló y decidió en la
sesión, las respuestas que se dieron y el enunciado completo del examen.

---

## 0. Cómo retomar en otro dispositivo

1. Clona el repositorio y cambia a la rama:

   ```bash
   git clone <URL del remoto origin>
   cd My-Story-Marker
   git switch exam/rescope
   ```

2. Abre Claude Code en esa carpeta y empieza con este mensaje:

   > Lee `ignore.md` y todos los ficheros de `.claude/memory/`. Después lee todas las rondas
   > de `exam/process-0/` y la spec 004, ejecuta `python exam/check.py` y dime qué queda
   > abierto antes de aprobarla.

3. La memoria automática de Claude Code **no viaja**: vive en el perfil de usuario de cada
   máquina. Por eso hay una copia curada en `.claude/memory/`, que Claude no carga solo;
   el paso 2 se la hace leer.

4. En el otro dispositivo **no** corre la sesión del backend. Aun así, en esta rama no se
   edita `backend/`, `frontend/`, `specs/001-*` ni `specs/002-*`: son de las otras
   sesiones y se editarían dos veces.

5. Cuando vuelvas a la máquina original, antes de seguir allí:

   ```bash
   cd My-Story-Marker-docs
   git pull
   ```

---

## 1. Dónde estamos, en un párrafo

El enunciado del examen llegó con la spec 001 del backend a medio implementar. Se analizó
qué falta frente al enunciado y se montó un espacio de trabajo paralelo (worktree
`My-Story-Marker-docs`, rama `exam/rescope`) para refactorizar documentación y todo lo que
no es código sin pisar a la sesión del backend. Ya existe un comprobador automático de
cumplimiento, el andamiaje de entregables, cuatro rondas del Proceso 0 y la **spec 004 en
borrador**, que confronta `docs/` con el enunciado y reparte el resto en bloques paralelos.
El usuario aceptó todos sus valores por defecto y bajó a 3-5 escenas por capítulo, así que el
Proceso 0 está cerrado. **El siguiente paso es la aprobación explícita de la spec 004.**
Después: bloque B0 (docs) y specs de bloque.

---

## 2. Estado del repositorio

### Ramas

| Rama | Qué es | Quién trabaja |
|---|---|---|
| `main` | El proyecto anterior (Story Creator: tres agentes, cuatro novelas, web estática). Sin ancestro común con las ramas nuevas | Nadie; se conservará con un tag `legacy-story-creator` |
| `spec/001-backend` | Backend de la spec 001, spec 002 de frontend y, desde el 2026-09-24, spec 003 de rediseño visual del frontend | Sesiones del backend y del frontend |
| `spec/002-frontend-foundation` | Plan 002 del frontend | Sesión del frontend |
| `exam/rescope` | Esta rama: reencuadre para el examen | Esta sesión |

### Carpetas en la máquina original

| Carpeta | Rama |
|---|---|
| `My-Story-Marker/` | `spec/001-backend` (backend y frontend) |
| `My-Story-Marker-docs/` | `exam/rescope` |
| `My-Story-Marker-frontend/` y otros temporales | worktrees de las otras sesiones |

### Qué hay en `exam/rescope` que no está en el backend

```bash
git log --oneline --no-merges spec/001-backend..exam/rescope
git diff --stat spec/001-backend...exam/rescope
```

| Fichero | Qué es |
|---|---|
| `exam/requirements.toml` | El enunciado convertido en 72 requisitos obligatorios comprobables y 4 opcionales |
| `exam/check.py` | Comprobador sin dependencias; escribe `exam/compliance.md` |
| `exam/compliance.md` | Informe generado: 17 de 72 obligatorios comprobables cumplidos (2026-09-24) |
| `exam/process-0/round-1-rescope.md` | Ronda 1 del Proceso 0, con respuestas |
| `exam/process-0/round-2-rescope.md` | Ronda 2 del Proceso 0, con respuestas |
| `exam/process-0/round-3-rescope.md` | Ronda 3: la spec pasa a 004 y se centra en confrontar `docs/` con el enunciado |
| `exam/process-0/round-4-rescope.md` | Ronda 4: qué ha resuelto ya la rama del backend (revisión en solo lectura) |
| `specs/004-exam-refactor-programme/004-exam-refactor-programme.md` | **Spec 004 en borrador**: confrontación de `docs/` con el enunciado, decisiones, 12 bloques paralelos con dueños de ficheros, contratos entre bloques, protocolo y plantilla de spec de bloque |
| `.claude/commands/exam-gap.md` | Comando `/exam-gap`: regenera el informe y propone el siguiente bloque |
| `.claude/memory/` | Copia curada de la memoria de Claude Code |
| `.mcp.json` | Servidor Playwright MCP fijado a 0.0.82, para inspección visual |
| `README.md` | README raíz, honesto sobre el estado |
| `presentacion/README.md`, `ejemplos/README.md` | Esqueletos de entregables |
| `ignore.md` | Este documento |

---

## 3. Qué se hizo en la sesión, en orden

1. **Análisis exhaustivo** del repositorio frente al enunciado (sección 6). Conclusión:
   base de ingeniería sólida (docs, proceso, permisos, más de 900 tests), pero cubre en
   torno a un 15-20 % del enunciado, y el dominio es distinto (novela larga genérica frente
   a novela de regalo desde un brief).
2. **Propuesta de trabajo en paralelo:** un git worktree con rama propia, reparto de
   ficheros por rama y sincronización en un solo sentido.
3. **Pregunta del usuario: "¿has cambiado algo del plan 001?"** No. El cambio que se veía
   era un commit de la sesión del backend (`9949d87`); esta sesión solo había leído.
4. **Creación del worktree** `My-Story-Marker-docs` con la rama `exam/rescope`, sin tocar
   la carpeta, el índice ni la rama del backend.
5. **Protección local:** un hook `PreToolUse` no versionado bloquea, en sesiones abiertas
   en el worktree, las escrituras en `backend/`, `specs/001-*` y las otras carpetas, y los
   comandos git que mueven ramas compartidas. Probado con 11 casos; falla en modo cerrado.
6. **Comprobador de cumplimiento** y comando `/exam-gap`. Se corrigieron siete falsos
   positivos y negativos para que el informe no infle nada.
7. **Andamiaje:** README raíz, `.mcp.json`, `presentacion/`, `ejemplos/`.
8. **Ronda 1 del Proceso 0** (19 preguntas). El usuario respondió 5, 6, 7, 8 y 9.
9. **Merge en un solo sentido** de `spec/001-backend` en `exam/rescope`: trajo la nueva
   estructura de `specs/` (una carpeta por spec) y la spec 002 de frontend.
10. **Ronda 2 del Proceso 0** (9 preguntas nuevas y las abiertas de la ronda 1). El usuario
    respondió 4, 20-25 y 27.
11. **Nuevo enfoque del usuario:** spec general de brechas y hoja de ruta, y una spec por
    bloque.
12. **Publicación** de `exam/rescope` en GitHub, copia de la memoria y este documento.
13. **2026-09-24.** La sesión del frontend toma la spec 003 (rediseño visual). A las 09:12
    UTC alguien, probablemente el usuario para ver la interfaz antigua, hizo `checkout` de
    `main` en la carpeta del worktree. No se perdió nada; la carpeta volvió a
    `exam/rescope` y la protección local ahora bloquea cualquier cambio de rama allí.
14. **Reenfoque del usuario:** la spec pasa a ser la **004** y se centra en **confrontar
    `docs/` con el enunciado**. Ronda 3 del Proceso 0.
15. **Ronda 4:** revisión en solo lectura de `spec/001-backend`. `docs/` no ha cambiado,
    así que las contradicciones de la ronda 3 siguen en pie. El código sí ha avanzado:
    retries con límite, orquestador, resúmenes por capítulo, reanudación de turno, CI,
    contrato y base del frontend. Se corrigieron cuatro falsos positivos del comprobador y
    se hizo merge de la rama del backend en `exam/rescope`. Cumplimiento: 17 de 72.
16. **Spec 004 redactada en borrador** a petición del usuario, antes de cerrar el Proceso 0: las preguntas abiertas van con su respuesta por defecto en sus Open questions (2, 10, 26, 29-37). Pensada para lanzarse en `spec/001-backend` y generar desde ella las specs de bloque en paralelo.
17. **2026-09-24.** El usuario acepta todos los valores por defecto de la spec 004 y cambia la
    decisión 20 a **3-5 escenas por capítulo**. Proceso 0 cerrado; falta la aprobación explícita.

---

## 4. Decisiones tomadas

| # | Decisión | Ronda |
|---|---|---|
| 5 | La documentación de proceso que pide el examen vive en `docs/process/`, un área de **registro** que cita a `docs/` y nunca define diseño | 1 |
| 6 | **SQLite autoritativo** para lo nuevo: brief, hechos y su uso, cronología, listas de palabras prohibidas, audit log de policy y versiones. La prosa, el canon y el cast siguen en ficheros | 1 |
| 7 | Un capítulo tiene **varias escenas** (se rechazó la correspondencia 1:1) | 1 |
| 8 | Roles: **entrevistador** nuevo (escribe solo el brief), **planner** = architect invocado por modelo (escribe bajo world builder y architect, sin ampliar permisos), **writer**, **editor** = style editor + auditor, **juez** de solo lectura que escribe solo resultados | 1 |
| 9 | **Lector web en React** con cambio desde la página, y **exportación a PDF** desde el backend | 1 |
| 4 | Las specs de esta rama toman siempre el siguiente número libre. La 003 es del frontend, así que la primera de esta rama es la **004** | 2, 3 |
| 1 | Intención: la spec 004 **confronta `docs/` con el enunciado** requisito a requisito, decide cómo resolver cada contradicción o ausencia y lista las ediciones de `docs/`. Los huecos solo de código van a las specs de bloque | 3 |
| 20 | **Entre 3 y 5 escenas por capítulo** (primero 4-7; cambiado por el usuario el 2026-09-24) | 2, spec 004 |
| 21 | Validadores en dos puntos: **al aceptar cada escena** (auditoría mecánica, palabras prohibidas, schema) y **al cerrar el capítulo** (longitud, nombres exactos, cobertura del brief, juez). Un fallo de capítulo vuelve a la escena con la evidencia | 2 |
| 22 | Un capítulo está completo cuando sus escenas están aceptadas, su resumen escrito y sus validadores de cierre pasan. Se reanuda en el primer capítulo incompleto conservando sus escenas aceptadas. En TLA+, capítulos con las escenas como contador | 2 |
| 23 | El uso de hechos se registra **por escena**; los capítulos se derivan. Un cambio del lector regenera solo las escenas afectadas y marca sus capítulos | 2 |
| 24 | **Un árbol de stores por novela** y **una base SQLite autoritativa** con `novel_id` en cada tabla, que guarda también las listas globales y el audit log | 2 |
| 25 | Esa base es un fichero propio (p. ej. `data/harness.sqlite`), **fuera de `.index/`**, con migraciones separadas del índice derivado | 2 |
| 27 | **Versiones en SQLite**: una fila por capítulo y versión con texto y hash; publicar crea versión nueva; nada se borra; "capítulos cambiados" = comparar hashes | 2 |

**Consecuencia de la 20, a resolver en la spec del bloque de generación.** Con 1.000-1.500
palabras por capítulo y 3-5 escenas, cada escena tiene unas 200-500 palabras y la novela
pasa a 30-50 turnos. El `literal_tail` de 500 palabras puede ser más largo que una escena corta, y el
coste y la latencia por novela crecen con el número de turnos.

---

## 5. Lo que queda abierto

### Para cerrar la spec 004 (ronda 3)

La ronda 3 trae además un adelanto con once contradicciones y ausencias ya localizadas
entre `docs/` y el enunciado.

| # | Pregunta | Recomendación |
|---|---|---|
| 2 | Fuera de alcance: pagos, cuentas, impresión, ilustraciones, audio, despliegue; opcionales al final | Sí; el primer opcional, el servidor MCP de solo lectura |
| 10 | Idioma: novela, README y presentación en español; `docs/`, specs y código en inglés; `EMBED_MODEL` multilingüe antes del primer `rebuild()` real | Sí |
| 26 | Los hechos del brief tienen su autoridad en SQLite; los ficheros del planner citan su id; un cambio actualiza el hecho y el rol dueño reescribe el fichero | Sí |
| 29 | Forma: una tabla por bloque del enunciado; por requisito, qué dice `docs/`, veredicto (cubierto, parcial, contradice, ausente, solo código), resolución y doc a editar. Ids iguales a los de `exam/requirements.toml` | Sí |
| 30 | Alcance: confrontación, decisiones y lista de ediciones de `docs/`, cumplida con los commits `docs:` tras aprobarla; el código va a las specs de bloque | (a) |
| 31 | ¿Es ese el tipo de confrontación que esperas? | Sí, con todas las filas del enunciado |

De la ronda 4 (revisión de la rama del backend):

| # | Pregunta | Recomendación |
|---|---|---|
| 32 | Los tres hallazgos aplazados del backend que tocan el examen (`literal_tail` por orden de discurso, procedencia sin id de turno, explicación semántica no guardada) entran como filas de la spec 004 | Sí, resueltos por la spec de su bloque |
| 33 | La spec del bloque de lectura reclama la vista de personajes y la de lectura completa que la spec 003 deja fuera | Sí |
| 34 | Repetir el merge en un solo sentido de `spec/001-backend` antes de redactar cada spec de esta rama | Sí, solo con la carpeta limpia |

**Salen de la spec 004:** la 3 (ramas) es logística y se sigue aplicando como regla de
trabajo; la 28 (quién redacta las specs del lector) pasa a la spec del bloque de lectura.

### Datos que solo tiene el usuario

- **18.** Dónde está el repositorio **MyFactory** (su commit final va en el email).
- **19.** Rotar la **clave de Langfuse** que está en claro en un fichero de notas de la
  carpeta padre del repo, fuera de git. No se ha copiado a ningún sitio.

### Pasan al Proceso 0 de la spec de su bloque

11 Langfuse en el backend · 12 los dos hooks · 13 tools con schema · 14 herramientas
formales · 15 invariantes de Lean y TLA+ · 16 verificación · 17 memoria (ya resuelta: se
copió a `.claude/memory/`). Sus recomendaciones están en la ronda 1.

### Próximos pasos

1. Responder las rondas 3 y 4: 2, 10, 26 y 29-34.
2. Redactar el **resumen de entendimiento compartido** y confirmarlo.
3. Redactar la **spec 004**, la confrontación de `docs/` con el enunciado, en
   `specs/004-<slug>/004-<slug>.md`.
4. Tras aprobarla, los commits `docs:` que resuelven cada contradicción y ausencia.
5. Una spec por bloque para el código, con el siguiente número libre, cada una con su
   Proceso 0 corto.

---

## 6. Análisis de brechas inicial

Hecho al empezar la sesión, cruzando el repositorio con el enunciado.

| Bloque | Estado | Qué hay | Qué falta |
|---|---|---|---|
| 1. Configuración / entrevista | ❌ | Patrón Pydantic + JSON Schema; contenido de stores tratado como datos | Rol entrevistador, schema de brief, datos faltantes y contradicciones, texto libre no confiable |
| 2. Lectura web/PDF | 🟡 | Spec 002 de frontend aprobada con un lector semilla | Índice, fichas con enlaces, portada con dedicatoria, cambio del lector, marcado, versión anterior, PDF |
| 3. Harness | 🟡 | Seis roles; skills; cap de 100k; cliente `claude -p`; tool sets | Orquestador completo; retries en uso; hooks; `CLAUDE.md` cuidado; tools con schema |
| 4. Memoria | 🟡 | SQLite como índice derivado; digests diseñados | Tabla hecho→escena, cronología en SQLite, checkpoint y reanudación |
| 5a. Programáticos | 🟡 | Ocho invariantes mecánicos | Longitud, nombres exactos, cobertura del brief, validación visual, normalización |
| 5b. Semánticos | ❌ | Schemas de salida del juez | LLM-as-judge con rúbrica y revisión humana |
| 5c. Lean 4 | ❌ | — | Todo |
| 5d. TLA+ | ❌ | Model checking previsto en `verification.md` con otro alcance | Máquina de estados, 3 safety + 1 liveness, TLC, mapeo con código |
| Evals | ❌ | Patrón reutilizable en la rama `backup-autoimprove` | 5 briefs, tabla por brief, iteración de tuning |
| 6. Observabilidad | ❌ | Plugin Langfuse en las sesiones de desarrollo | SDK en backend: sesión por novela, spans, scores, prompts versionados |
| 7. Guardrails | 🟡 | `forbidden_variants` en ficheros; log de escrituras | Listas en SQLite por niveles, normalización, reintento con límite, audit log de policy |
| Entregables | 🟡 | README raíz, `.mcp.json`, esqueletos, memoria | `/docs/process`, presentación, novela PDF de ejemplo, vídeo, CI |

El estado exacto y actualizado siempre es `python exam/check.py`.

---

## 7. Preguntas del usuario y respuestas de la sesión

**¿Puedo trabajar en otra rama mientras otra sesión termina el backend?** Sí, con un git
worktree: otra carpeta con su propia rama e índice que comparte el mismo `.git`. Ninguna
sesión ve los cambios sin commitear de la otra y no hay bloqueos de índice compartido.

**¿Has cambiado el plan 001?** No. El cambio era un commit de la sesión del backend.

**¿Qué es `round-x-rescope.md`?** Es el registro del **Proceso 0** de `AGENTS.md`: las rondas
de preguntas con respuesta recomendada que deben cerrarse antes de redactar una spec. No es
una spec: no tiene alcance formal ni criterios de aceptación. Es la materia prima de la
spec, como el registro de decisiones de la spec 001, y queda como evidencia del
razonamiento, que es lo que el examen corrige en `/docs`.

**¿Está bien la idea de una spec general de brechas y una spec por bloque?** Sí, y mejora
el plan:

- La spec general recoge las decisiones transversales y sus criterios de aceptación cubren
  el reencuadre de `docs/`, porque `AGENTS.md` exige una spec antes de tocar invariantes,
  permisos o stores.
- Cada **bloque** tiene después su spec con un Proceso 0 más corto.
- Las preguntas de detalle (Langfuse, hooks, tools, formales, invariantes) pasan a su
  bloque y ya no bloquean la spec general.

*(Refinado el 2026-09-24: la spec general es la 004 y confronta `docs/` con el enunciado.
Ver las dos preguntas siguientes.)*

**¿El `checkout` de `main` en la carpeta del worktree afecta a GitHub?** No. Cambiar de
rama es una operación local: no sube ni modifica nada en el remoto. `origin/exam/rescope` y
`origin/main` siguen en los mismos commits.

**¿La spec planeada confronta `docs/` con el enunciado?** Solo en parte: se había planteado
como "qué le falta al sistema por bloques", mezclando huecos de documentación y de código.
Se reenfocó: la spec 004 confronta cada requisito del enunciado con lo que dice `docs/`,
decide cómo resolver cada contradicción o ausencia y lista las ediciones de `docs/`. Los
huecos que son solo de código se anotan y van a las specs de bloque.

**¿Cómo sigo desde otro dispositivo sin subir lo no commiteado del backend?** Subiendo
`exam/rescope` a GitHub. Lo que el backend no ha commiteado vive solo en su carpeta y nunca
viaja con un push. Ver la sección 0.

**¿Publicar rompe algo del backend o del frontend?** No:

- Crea una rama nueva en GitHub y no modifica ninguna otra, remota o local.
- Publica 16 commits ya hechos del backend que venían con el merge. Son historia fija de
  `spec/001-backend`, que solo avanza por fast-forward, así que cuando esa sesión empuje su
  rama los encontrará ya subidos, sin conflicto.
- El escaneo de secretos de todo lo publicado dio cero coincidencias.

**¿Copiar la memoria a `.claude/memory/` resuelve lo de continuar en otro equipo?** En
parte. La copia viaja con el repo, pero Claude Code no la carga sola: hay que pedirle que la
lea, como indica la sección 0. Por eso existe también este documento.

---

## 8. Avisos

- **Clave de Langfuse en claro** fuera del repo, en las notas de la carpeta padre: rotarla.
- **Reparto de ficheros:** esta rama no toca `backend/`, `frontend/`, `specs/001-*` ni
  `specs/002-*`. Si un doc está mal desde la rama del backend, se anota en su spec.
- **Proceso de `AGENTS.md`:** Proceso 0 → spec aprobada → plan aprobado → código. Nada de
  `docs/` se edita hasta que la spec 004 esté aprobada.
- **La carpeta del worktree debe estar en `exam/rescope`.** Para ver `main` sin moverla:
  `git show main:<ruta>` o `git ls-tree -r --name-only main`.
- **`main`** es el proyecto viejo; moverlo es irreversible en el remoto y requiere
  confirmación explícita.

---

## Anexo · Enunciado completo del examen

Transcrito tal como se recibió. La dirección de correo de entrega se ha sustituido por
una etiqueta por la política de privacidad; está en el enunciado original.

> Examen final · Harness Engineering
> Contexto
> Una empresa quiere vender novelas personalizadas para regalar: a un hijo, a la pareja, para celebrar una boda, un aniversario o una jubilación. Tu tarea es diseñar y construir el sistema agéntico que las genera, y presentarlo como solución técnico-comercial.
>
> El objetivo del cliente tiene dos dimensiones igual de importantes:
>
> Personalización. La novela debe incorporar de forma natural los datos del destinatario: su nombre, su historia, los detalles que el comprador ha aportado. El destinatario debe reconocerse en la novela y sentir que fue escrita para él.
>
> Calidad narrativa mínima. La novela no tiene que ser un best seller, pero debe ser agradable de leer. No se aceptan novelas con problemas narrativos evidentes: inconsistencias de personajes, saltos temporales sin sentido, capítulos que se contradicen, prosa mecánica o repetitiva, o finales abruptos. El lector debe poder leerla de principio a fin sin tropezar. La personalización no justifica una mala escritura.
>
> El sistema no puede optimizar solo para que los datos aparezcan: debe también producir una historia que funcione como historia. Los validadores, el rol de editor y el LLM-as-judge deben reflejar este equilibrio.
>
> Proyecto individual. Novelas de 10 capítulos de unas 1.000–1.500 palabras cada uno. La complejidad está en el harness, no en la extensión.
>
> Entregables
> Repositorio storyMaker — el proyecto de novelas personalizadas: código, README, brief de ejemplo reproducible, .env.example y carpeta /docs con toda la documentación de proceso.
> Repositorio MyFactory — herramientas y utilidades del curso, ya iniciado durante las prácticas.
> La presentación formal y sus anexos en la carpeta /presentacion/, commiteados antes del plazo de entrega del repo storyMaker.
> Formato de los archivos en /presentacion/:
>
> el deck principal en PDF y en el formato original editable (PowerPoint, Keynote o similar);
> los anexos como ficheros individuales nombrados de forma descriptiva (por ejemplo, anexo-tla-spec.pdf, anexo-evals-tabla.pdf);
> un README.md en la misma carpeta que liste el contenido y el idioma elegido.
> Entrega final
> La entrega se hace enviando un email a [EMAIL_ELIMINADO] con el asunto:
>
> [Harness Engineering] Entrega final — <nombre del estudiante>
> El email debe incluir:
>
> el link al commit final del repositorio storyMaker;
> el link al commit final del repositorio MyFactory;
> una frase de no más de tres líneas resumiendo la decisión de diseño más importante que tomaste.
> No se aceptan entregas fuera de plazo. El commit final es el que cuenta, no la hora del email.
>
> Alcance del proyecto
> 1. Configuración
> Un agente entrevistador recoge los datos del destinatario: nombre, edad, rasgos, recuerdos, género, tono y extensión. También recoge las palabras o temas que el cliente no quiere que aparezcan.
> Detecta los datos que faltan y al menos un tipo de contradicción (por ejemplo, edad frente a género o tono).
> El usuario puede pegar texto libre (una anécdota, una carta) del que se extraen hechos. Ese texto se trata como contenido no confiable.
> El resultado de la entrevista es un brief estructurado y validado con schema.
> 2. Lectura interactiva (web o PDF)
> La novela se entrega como web o como PDF interactivo. En ambos casos debe incluir:
>
> un índice de capítulos navegable;
> una ficha de personajes y lugares generada desde la story bible, con enlaces al capítulo donde aparece cada uno;
> una portada con dedicatoria personalizada.
> Si es web, el lector puede seleccionar un fragmento o un hecho y pedir un cambio desde la propia página ("el perro se llama Nala"). El sistema identifica los capítulos que usan ese hecho, regenera solo esos sin romper la continuidad y marca en la lectura qué capítulos han cambiado respecto a la versión anterior.
>
> Si es PDF, el cambio se pide desde fuera del documento (formulario o CLI) y se genera una nueva versión del PDF. Esa versión incluye una página inicial de "novedades" con los capítulos modificados y enlaces internos a cada uno.
>
> En ambas opciones se conserva la versión anterior de la novela.
>
> 3. Harness
> Tres roles como mínimo: planner, writer y editor/critic.
> Un archivo de instrucciones CLAUDE.md, una skill reutilizable y dos hooks: uno de validación del capítulo y otro de policy.
> Tools con schema validado.
> Retries con límite.
> Registro de tokens y coste por novela a través de Langfuse (ver sección de observabilidad).
> 4. Memoria
> Una story bible en SQLite (obligatorio) en la que cada hecho registra en qué capítulos se usa. Incluye una tabla de cronología (eventos, momento, personajes, lugar) que alimenta el validador formal.
> Resúmenes por capítulo para construir el contexto de los siguientes.
> Checkpoint por capítulo: si la generación falla, se reanuda desde el último capítulo completado.
> 5. Validación y evaluación
> El sistema debe incluir validadores de cuatro tipos. Cada validador tiene un nombre, se ejecuta en un punto concreto del harness (hook, rol editor o gate antes de publicar una versión) y envía su resultado a Langfuse como score.
>
> a) Validadores programáticos (deterministas). Mínimo tres, por ejemplo:
>
> el brief y la salida de cada rol cumplen su schema;
> el nombre del destinatario y los personajes aparecen escritos exactamente como en la story bible;
> la longitud de cada capítulo está dentro del rango;
> cada elemento personalizado obligatorio del brief aparece en al menos un capítulo, comprobado contra la tabla de hechos de SQLite;
> el guardrail de palabras prohibidas (ver sección 7);
> validación visual via browser MCP: el agente abre la novela en el browser, navega por los capítulos y verifica que el índice, la ficha de personajes y la portada renderizan correctamente; si detecta un error visual, lo registra como fallo y lo devuelve al writer o al rol correspondiente.
> b) Validadores no programáticos (semánticos). Mínimo dos:
>
> un LLM-as-judge con rúbrica que evalúe continuidad, tono, calidad narrativa (arco de la historia, coherencia de personajes, ritmo entre capítulos) y que la personalización esté integrada de forma natural y no forzada, con una puntuación por criterio y una justificación;
> una revisión humana de al menos una novela completa, con la misma rúbrica, para comparar el juicio humano con el del LLM.
> c) Validador formal de la historia (Lean 4). La cronología de la historia se modela formalmente y se verifica:
>
> a partir de la story bible en SQLite se genera un fichero Lean con los hechos temporales: eventos, momento, personajes presentes, lugar, fechas de nacimiento;
> se definen en Lean al menos dos invariantes, por ejemplo:
> los eventos respetan el orden temporal declarado;
> la edad de un personaje en cada evento es coherente con su fecha de nacimiento;
> un personaje no está en dos lugares en el mismo momento;
> un personaje no aparece después de un evento que lo excluye (muerte, partida definitiva);
> la verificación se ejecuta de forma automática (lake build o lean) y, si falla, la versión de la novela no se publica y el fallo vuelve al editor como feedback;
> debe mostrarse al menos un caso real en el que el validador formal detecta una incoherencia que los otros validadores no detectaron, o justificar por qué no se encontró ninguno.
> d) Validador formal del sistema (TLA+). Mientras Lean verifica la coherencia de la historia, TLA+ verifica el comportamiento del harness. Referencia: learntla.com.
>
> Una especificación en TLA+ o PlusCal del flujo de generación como máquina de estados: configuración → planificación → escritura de capítulo → validación → publicación de versión, incluyendo retries, reanudación desde checkpoint y regeneración por cambio del lector.
> Al menos tres invariantes de seguridad, por ejemplo:
> nunca se publica una versión con un capítulo que no ha pasado todos los validadores;
> la reanudación desde checkpoint no duplica ni pierde capítulos;
> la versión anterior de la novela se conserva siempre tras una regeneración;
> el número de reintentos nunca supera el límite.
> Al menos una propiedad de liveness: toda generación termina publicando una versión o deteniéndose con error; nunca queda en un bucle infinito.
> Verificación con el model checker TLC sobre un modelo pequeño (por ejemplo, 5 capítulos y 2 reintentos), con la configuración incluida en el repo.
> La especificación debe corresponder al código: el README explica qué estado o transición del código implementa cada acción de la especificación.
> Si TLC encontró algún contraejemplo durante el desarrollo, se documenta junto con el cambio que hizo en el código.
> Evaluación del sistema:
>
> Cinco briefs de prueba, incluido al menos uno adversarial (injection en el texto libre) y uno diseñado para provocar una incoherencia temporal.
> Una tabla que muestre, por brief, qué validadores pasaron y cuáles fallaron.
> Una iteración de tuning documentada, con los resultados antes y después.
> 6. Observabilidad
> Cada generación de novela es una traza en Langfuse, agrupada por sesión (una sesión por novela, incluyendo la entrevista y las regeneraciones posteriores).
> Cada rol (entrevistador, planner, writer, editor) y cada llamada a tool aparece como span con nombre identificable.
> Tokens, coste y latencia visibles por llamada, por capítulo y por novela.
> Los resultados de todos los validadores (programáticos, semánticos y Lean) se envían a Langfuse como scores asociados a la traza correspondiente. TLC se ejecuta en desarrollo, no en cada generación.
> Los prompts versionados en Langfuse, de forma que la iteración de tuning muestre qué versión de prompt produjo cada resultado.
> 7. Guardrails
> Un guardrail de palabras prohibidas, aplicado en código sobre cada capítulo antes de aceptarlo:
> listas guardadas en SQLite, en tres niveles: globales (insultos, términos ofensivos) y por novela, definidas por el cliente en la configuración (por ejemplo, el nombre de una expareja o un tema que no quiere que aparezca);
> la detección normaliza el texto antes de comparar: mayúsculas, acentos, plurales y variantes simples;
> si hay coincidencia, el capítulo se devuelve al writer para reescribirlo, con un límite de intentos; si se agota el límite, la generación se detiene y se informa;
> cada coincidencia queda registrada en el audit log y en Langfuse;
> tests que cubran al menos un caso de cada nivel y un caso de variante (acento o plural).
> Un audit log de las decisiones del policy engine.
> Uso de un maximo de 100.000 Tokens Concurrentes.
> Opcional (suma nota)
> Servidor MCP para consultar y descargar novelas. Expone la plataforma como servidor MCP al que conectar cualquier cliente (Claude Desktop, Claude Code o MCP Inspector). Se recomienda implementarlo con FastMCP como plugin del FastAPI que ya tienen, para no añadir infraestructura nueva. Tools sugeridas:
> list_novels: lista las novelas con su estado y versión actual.
> get_chapter: devuelve un capítulo concreto de una versión concreta.
> list_versions: historial de versiones de una novela y qué capítulos cambiaron en cada una.
> query_story_bible: consulta personajes, lugares, hechos y cronología.
> download_novel: devuelve la novela completa en PDF. Requisitos si se implementa: cada tool con schema validado; servidor de solo lectura; cada llamada registrada en Langfuse; el README explica cómo conectarlo a un cliente MCP. Si además tienen login, el servidor respeta la identidad del usuario autenticado.
> Tools de escritura sobre el servidor MCP (pedir un cambio del lector desde un cliente MCP), con permisos y confirmación. Requiere el servidor MCP implementado.
> Nuevos tipos de linters de prosa además de los validadores obligatorios, por ejemplo:
> repeticiones de palabras o muletillas en un mismo párrafo;
> frases demasiado largas o legibilidad inadecuada para el tono del destinatario;
> abuso de adverbios, clichés o expresiones típicas de texto generado por IA;
> consistencia de estilo: tiempo verbal, narrador (primera o tercera persona), tratamiento entre personajes. Pueden basarse en herramientas existentes (como Vale o LanguageTool) con reglas propias, o escribirse desde cero.
> Linter propio para edición manual de la novela: el cliente o un editor humano modifica el texto a mano, y el linter señala los problemas mientras se edita:
> integrado en el editor web, en una extensión de VS Code o como servidor LSP;
> comprueba el texto editado contra la story bible (nombres, hechos, cronología) y contra las palabras prohibidas;
> una edición manual que cambia un hecho actualiza la story bible y vuelve a pasar por los validadores (incluido Lean) antes de publicar la versión.
> Invariantes adicionales en Lean, o demostraciones generales (para cualquier cronología) en lugar de comprobaciones sobre una cronología concreta.
> Especificación TLA+ del servidor MCP o de la concurrencia entre regeneraciones simultáneas.
> Login de usuarios con SQLite. Un sistema de autenticación básico que permita a cada cliente acceder solo a sus propias novelas:
> registro e inicio de sesión con email y contraseña hasheada (bcrypt o similar), almacenados en SQLite;
> sesión gestionada con token (JWT o similar);
> cada novela, configuración y entrada del audit log queda asociada al usuario propietario;
> si se ha implementado el servidor MCP, respeta la identidad del usuario autenticado: list_novels y download_novel solo devuelven las novelas del usuario en sesión;
> tests que verifiquen que un usuario no puede acceder a las novelas de otro. con agentes o skills.** Un agente o skill dedicado que analiza el sistema en busca de vulnerabilidades, ejecutado sobre el propio repo o sobre la API del harness. Ejemplos de lo que puede cubrir:
> prompt injection: intentos de modificar el comportamiento del sistema a través del texto libre aportado por el usuario en la configuración;
> exfiltración de datos: comprueba que un brief no puede extraer información de otra novela o de otro cliente;
> dependencias: análisis de las dependencias del proyecto en busca de paquetes con vulnerabilidades conocidas (por ejemplo, con pip audit o npm audit, orquestado por el agente);
> secrets leak: el agente escanea el historial de commits en busca de API keys o credenciales expuestas accidentalmente;
> los resultados del análisis se guardan en un informe en /docs/security-report.md y las vulnerabilidades encontradas se registran con su severidad y el cambio que se hizo para resolverlas.
> Fuera de alcance
> Pagos, cuentas de usuario, impresión física, ilustraciones, audio y despliegue en producción.
>
> Los repositorios deben incluir también:
>
> Novela de ejemplo generada: el PDF de una novela completa de 10 capítulos, generada con el brief de ejemplo del README, commiteada en /ejemplos/novela-ejemplo.pdf. Es la evidencia de que el sistema funciona de principio a fin. Si el formato de lectura elegido es web, se incluye igualmente el PDF exportado.
> /docs en storyMaker con la documentación de proceso. No se corrige el resultado, se corrige el razonamiento que llevó a él:
> Spec inicial: qué se decidió construir y por qué, antes de escribir código.
> Trade-offs: cada decisión de diseño relevante explicada como decisión: opciones, criterios y elección. Por ejemplo: single-agent vs multi-agent, formato de la story bible, elección del modelo de lectura, integración de TLA+ con el flujo real, invariantes de Lean priorizados.
> Explainers: uno por cada concepto del curso aplicado en el proyecto. Breves. Para demostrar que se entiende lo que se aplica, no para copiar la teoría.
> Diagramas: arquitectura del harness, máquina de estados de TLA+, esquema SQLite, tabla de validadores con su punto de ejecución.
> Registro de iteraciones: qué cambió tras cada eval o contraejemplo de TLC o Lean, y por qué. No un diario, sino un log de decisiones con causa y efecto.
> Red-team log: casos adversariales probados, qué validador los detectó (o no) y cómo se resolvió.
> Vídeo de demo en cualquier formato (Loom, MP4 u otro), de la duración que se considere necesaria para mostrar el sistema con claridad. Debe estar subido al repositorio storyMaker dentro de /presentacion/, o enlazado desde su README.md si el fichero supera el límite de tamaño de GitHub.
> Sin API keys en ningún repo. Usar .env.example.
> Claude Code. Los estudiantes trabajan con Claude Code. El repo debe reflejar ese uso:
> el fichero CLAUDE.md en la raíz del repo (ya obligatorio como archivo de instrucciones del harness) debe estar cuidado y ser legible: es parte del examen;
> la carpeta .claude/ con los ficheros de memoria y comandos personalizados debe estar commiteada;
> el fichero de configuración MCP (.claude/mcp.json o equivalente) debe incluir un servidor MCP de inspección de browser (Chrome MCP, Playwright MCP o similar), de forma que Claude Code pueda abrir la lectura web de la novela y verificar el resultado visualmente;
> el uso real del browser MCP debe estar documentado en /docs: qué inspeccionó el agente, qué detectó y qué cambio provocó en el código o en los prompts;
> los ficheros de skills usados o creados durante el desarrollo deben estar en el repo y referenciados desde /docs;
> si se han usado subagentes o comandos / propios, deben estar documentados en /docs con su propósito y resultado.
> Un proyecto sin evals con resultados medibles, o sin documentación de proceso en /docs, no aprueba.

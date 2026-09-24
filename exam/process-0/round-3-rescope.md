# Proceso 0 · Ronda 3 · La spec 004 confronta `docs/` con el enunciado

Rama `exam/rescope`. Preparado el 2026-09-24, tras las rondas [1](./round-1-rescope.md) y
[2](./round-2-rescope.md).

Igual que antes: número y "ok" acepta la recomendación; número y alternativa la cambia.

---

## Lo que cambia en esta ronda (usuario, 2026-09-24)

**Número.** La spec pasa a ser la **004**. La 003 la ha tomado la sesión del frontend en
`spec/001-backend`, para un rediseño visual de `frontend/`.

**Enfoque.** La spec 004 **confronta lo que dicen `docs/` con el enunciado del examen**.
Hasta ahora se había planteado como "qué le falta al sistema, por bloques", que mezclaba
huecos de documentación y de código. Queda así:

- **Qué es.** Para cada requisito del enunciado: qué dice `docs/`, dónde lo dice, si lo
  cubre, lo cubre a medias, lo contradice o no lo menciona, y cómo se resuelve.
- **Qué produce.** Las decisiones de diseño que resuelven cada contradicción y cada
  ausencia, y la lista de ediciones de `docs/` que las recogen.
- **Qué no es.** No es un plan de código. Los huecos que son solo de implementación se
  anotan como "lo resuelve la spec del bloque X" y nada más.

Esto responde la pregunta **1** (intención) con tus palabras.

---

## Adelanto: contradicciones y ausencias ya localizadas

Para que veas si es el tipo de confrontación que esperas. No es exhaustivo; la spec lo será.

| Tema | Qué dice `docs/` | Qué pide el enunciado | Resolución |
|---|---|---|---|
| Story bible | SQLite es un índice **derivado**, "never a source" (`architecture.md`, Memory and context budget) | Story bible en SQLite, obligatoria | **Contradice.** Decisión 6: SQLite autoritativo para lo nuevo |
| Personalización | No existe brief ni destinatario; la capa 0 es premisa, tesis, género y estilo (`definitions.md`) | Brief validado con datos del destinatario y temas vetados | **Ausente.** Entidad nueva en `definitions.md` |
| Roles | Seis roles; ni entrevistador ni juez (`architecture.md`, Figura 3) | Entrevistador, planner, writer, editor/critic | **Parcial.** Decisión 8 |
| Unidad y extensión | Escenas, "roughly two hundred times over a novel" (Figura 4) | 10 capítulos de 1.000-1.500 palabras | **Contradice.** Decisiones 7 y 20 |
| Versiones | "Versioning is git's, not the record's" (`architecture.md`, Draft) | Conservar la versión anterior y marcar capítulos cambiados | **Contradice.** Decisión 27 |
| Palabras prohibidas | `forbidden_variants` en `canon/lexicon.yaml`, sin normalización (invariante 7) | Listas en SQLite, globales y por novela, con normalización y reintento acotado | **Parcial** |
| Validadores | Invariantes 1-10 y auditor (`definitions.md`, `verification.md`) | Longitud, nombres exactos, cobertura del brief, visual, juez, revisión humana, Lean | **Parcial** |
| Model checking | TLA+ opcional sobre permisos y turno, paso 9 de adopción (`verification.md`) | TLA+ del flujo completo con retries, checkpoint y regeneración; TLC en el repo | **Parcial** |
| Observabilidad | Langfuse como paso 3 de adopción, por turno (`verification.md`) | Obligatorio: sesión por novela, spans por rol y tool, scores, prompts versionados | **Parcial** |
| Calidad narrativa | Riesgo aceptado **U**: "Chapter forty lands" (`verification.md`) | Calidad mínima exigida y medida con juez y revisión humana | **Contradice.** El riesgo pasa a tener verificación **I** |
| Lectura | El frontend es para navegar canon, grafo y cronología (`architecture.md`) | Lector con índice, fichas, portada con dedicatoria y cambios | **Ausente** |

---

## Preguntas

**29. Forma de la confrontación.** Una tabla por bloque del enunciado, con una fila por
requisito y cinco columnas: id del requisito (el mismo de `exam/requirements.toml`, para
que la spec y el comprobador se crucen), qué dice `docs/` con enlace, veredicto, resolución
y doc que se edita.

Los veredictos posibles son: cubierto, parcial, contradice, ausente y solo código.
*Recomendación:* sí.

**30. Alcance de la spec 004.**
- **a)** Confrontación, decisiones y lista de ediciones de `docs/`. Sus criterios de
  aceptación se cumplen con los commits `docs:` que siguen a su aprobación.
- **b)** Solo la confrontación. Cada bloque edita sus docs en su propia spec.

*Recomendación:* **a**. `docs/` es una sola capa y sus ficheros se citan entre sí;
editarlos a trozos desde varias specs deja incoherencias entre ellos durante semanas. Las
specs de bloque se quedan con el código.

**31. ¿Es este el tipo de confrontación que esperas?** Mira el adelanto de arriba.
*Recomendación:* sí, con todas las filas del enunciado y no solo estas.

### Siguen abiertas de rondas anteriores

| # | Pregunta | Recomendación |
|---|---|---|
| 2 | Fuera de alcance: pagos, cuentas, impresión, ilustraciones, audio, despliegue; opcionales al final | Sí |
| 10 | Novela, README y presentación en español; `docs/`, specs y código en inglés | Sí |
| 26 | Los hechos del brief tienen su autoridad en SQLite; los ficheros citan su id | Sí |

### Salen de esta spec

- **3** (estrategia de ramas) es logística, no diseño. Se sigue aplicando la
  recomendación como regla de trabajo.
- **28** (quién redacta las specs del lector) pasa a la spec del bloque de lectura.

---
name: exam-worktree-partition
description: Desde 2026-09-23 varias sesiones trabajan en paralelo; exam/rescope no toca backend/ ni specs/001-* ni specs/002-*
metadata:
  type: project
---

El 2026-09-23 llegó el enunciado del examen final (novelas personalizadas de regalo) con
la spec 001 del backend a medias. Desde entonces se trabaja en paralelo, en la máquina
original:

- **Carpeta principal `My-Story-Marker/`, rama `spec/001-backend`:** la sesión del backend
  y, por decisión del usuario, también la del frontend. Dueñas de `backend/**`,
  `frontend/**`, `specs/001-*`, `specs/002-*` y `.github/workflows/`. La sesión del backend
  monta sus commits en un worktree temporal y avanza la rama solo por fast-forward.
- **Worktree `My-Story-Marker-docs/`, rama `exam/rescope`:** la sesión que el usuario llama
  "Examen final storyMaker". Dueña de `docs/`, specs 003 en adelante, `README.md`,
  `ignore.md`, `.claude/memory/`, `.claude/commands/`, `.mcp.json`, `exam/`,
  `presentacion/`, `ejemplos/` y, más adelante, `formal/` y `evals/`.
- **Sincronización en un solo sentido:** `exam/rescope` hace merge de `spec/001-backend`;
  nunca al revés hasta que el plan 001 termine. `main` no se mueve sin confirmación.
- **`AGENTS.md` y `CLAUDE.md`:** la sesión del backend ya editó `AGENTS.md` para pasar a una
  carpeta por spec. El usuario acepta resolver esos cruces al refactorizar.
- **Protección local:** en la máquina original, un hook no versionado bloquea en el worktree
  las escrituras en `backend/`, `specs/001-*` y las otras carpetas, y los comandos git que
  mueven ramas compartidas. En otro dispositivo no existe y no hace falta si allí no corre
  la sesión del backend.

**Numeración de specs:** las de `exam/rescope` empiezan en 003 y siempre toman el
siguiente número libre, contando las que creen otras ramas.

**Estado del reencuadre:** rondas 1 y 2 del Proceso 0 respondidas
(`exam/process-0/`). Enfoque del usuario: una spec 003 general de brechas y hoja de ruta
por bloques, y después una spec por bloque. El punto de situación completo está en
`ignore.md`, en la raíz del repositorio.

**Why:** varias sesiones sobre el mismo repo se pisan si comparten carpeta, rama o ficheros.

**How to apply:** antes de editar, comprobar carpeta, rama y dueño del fichero. Si desde la
rama del backend un doc resulta estar mal, se anota en las preguntas abiertas de su spec,
no se edita `docs/`. Ver [[windows-python3-stub-gotcha]].

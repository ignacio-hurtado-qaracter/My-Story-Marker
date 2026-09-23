---
description: Regenera el informe de cumplimiento del examen y propone el siguiente bloque de trabajo
allowed-tools: Bash(python exam/check.py:*), Read, Grep, Glob
---

Mide cuánto le falta al repositorio para cumplir el enunciado del examen y di qué hacer
después. No edites nada salvo `exam/compliance.md`, que genera el script.

1. Ejecuta `python exam/check.py` desde la raíz del repo. Escribe `exam/compliance.md`.
2. Lee `exam/compliance.md`. Agrupa lo que está en ❌ y 🟡 por bloque.
3. Lee `specs/` y di qué requisitos pendientes ya cubre una spec abierta y cuáles no tienen
   ninguna. Un requisito sin spec es una spec por escribir, no código por escribir.
4. Propón el siguiente bloque con este orden de prioridad:
   - lo que bloquea a otros bloques (esquema SQLite, brief, orquestador);
   - lo obligatorio antes que lo opcional;
   - lo que se puede avanzar sin tocar `backend/` mientras la sesión del backend trabaja.
5. Recuerda que el orden de `AGENTS.md` no se salta: Proceso 0, spec aprobada, plan
   aprobado, código. Si el siguiente paso es una spec, prepara su ronda de preguntas.

Responde en español, con una tabla corta de pendientes por bloque y una recomendación.
Argumento opcional: $ARGUMENTS limita el análisis a un bloque (por ejemplo `5d` o `Lean`).

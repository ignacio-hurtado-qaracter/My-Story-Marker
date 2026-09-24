# Multi-agente: roles y permisos

**Qué es.** Separar el trabajo en roles con un prompt, una salida tipada y un conjunto cerrado de escrituras. La separación no es por estética: permite validar, reintentar y atribuir cada escritura.

**Cómo lo aplicamos aquí.** Roles `interviewer`, `planner`, `writer`, `editor`, `judge` (y `canoniser`, heredado) en `AgentRole` ([`backend/app/commons/permissions/roles.py`](../../../backend/app/commons/permissions/roles.py)); las llamadas de la novela-regalo en [`backend/app/novel/roles.py`](../../../backend/app/novel/roles.py). Ningún modelo escribe: el orquestador escribe en su nombre según la [Figura 3](../../../docs/architecture.md#figure-3--agents-and-write-permissions). Las dos únicas escrituras nuevas del programa fueron el brief (entrevistador) y los resultados de validador (juez).

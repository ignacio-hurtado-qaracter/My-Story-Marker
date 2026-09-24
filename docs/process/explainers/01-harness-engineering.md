# Harness engineering

**Qué es.** El harness es todo lo que rodea al modelo para que una tarea larga salga bien: qué contexto ve, qué puede hacer, cómo se valida su salida, qué pasa cuando falla y cómo se observa. El modelo es un componente; la fiabilidad la pone el harness.

**Cómo lo aplicamos aquí.** Un orquestador determinista ([`backend/app/novel/pipeline.py`](../../../backend/app/novel/pipeline.py)) recorre plan → escenas → editor → cierre de capítulo → checkpoint → pre-publicación → publicación. Cada llamada al modelo va por `traced_complete` con esquema de salida, reintento acotado y traza; cada paso tiene validadores en un punto con nombre (K4). El flujo es el que TLC comprueba ([`formal/tla/`](../../../formal/tla/README.md)) y el de la [Figura 5](../../../docs/architecture.md#figure-5--one-novel-generation).

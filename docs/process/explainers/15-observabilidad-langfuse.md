# Observabilidad con Langfuse

**Qué es.** Ver qué hizo cada llamada, cuánto costó y con qué versión de prompt, para depurar y para comparar iteraciones.

**Cómo lo aplicamos aquí.** [`backend/app/commons/observability/`](../../../backend/app/commons/observability/traced.py) (K2): **sesión** = novela; **traza** = una generación o regeneración (`generate`, `change_fact`); **spans** `phase:*`, `chapter:<n>`, `role:<rol>`, `tool:<nombre>`; generaciones con tokens, coste (tabla de precios fijada en `pricing.py`) y latencia; **scores** de cada validador, guardrail y criterio del juez, y `novel_cost_usd`/`novel_tokens` al final. Los prompts de `backend/app/prompts/*.md` se publican en la gestión de prompts de Langfuse y cada llamada registra `prompt_version`. Sin claves, un `NoopObserver`.

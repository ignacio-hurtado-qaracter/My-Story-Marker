# Evals y tuning

**Qué es.** Medir el sistema contra un conjunto fijo de entradas con resultado esperado, y cambiar una sola cosa cada vez comparando antes y después.

**Cómo lo aplicamos aquí.** Cinco briefs en [`evals/briefs/`](../../../evals/README.md) (ejemplo reproducible, infantil, inyección, trampas temporales, contradicción que debe rechazarse), `run_evals.py` produce la tabla validador × brief desde `validator_result`, y `compare_iterations.py` compara dos iteraciones ligadas a versiones de prompt en Langfuse. Resultados y tuning: pendientes de la ejecución de B11 ([iteraciones](../iteraciones.md#evals-y-tuning-pendiente-de-resultados)).

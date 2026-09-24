# Reintentos con límite

**Qué es.** Todo bucle de reparación tiene presupuesto y un final explícito; sin límite, un validador que nunca pasa es un gasto infinito.

**Cómo lo aplicamos aquí.** En [`pipeline.py`](../../../backend/app/novel/pipeline.py): `MAX_SCENE_RETRIES = 2` por escena, `MAX_CHAPTER_RETRIES = 2` por capítulo, `MAX_REPAIR_ROUNDS = 1` tras un `pre_publish` fallido, `MAX_REPLANS = 1`; guardrail `MAX_FORBIDDEN_REWRITES = 2`. Agotado → `StopRunError` y la ejecución termina en `stopped_error` con motivo (`scene_retry_limit`, `chapter_retry_limit`, `forbidden_word_limit`, `repair_limit`). TLC demostró que los contadores deben ser **durables** (CE2, CE4): el de capítulo se cuenta desde `validator_result`, el de reparación está en `novel_version.repair_rounds`.

# LLM-as-judge

**Qué es.** Un modelo evalúa la salida de otro con una rúbrica fija, dando puntuación **y** justificación por criterio; útil para lo que un programa no mide (tono, naturalidad), pero es juicio (**I**), no prueba.

**Cómo lo aplicamos aquí.** [`backend/app/judge/`](../../../backend/app/judge/rubric.py): criterios `continuidad`, `tono`, `calidad_narrativa`, `personalizacion_natural` (+ `final_satisfactorio` en la novela), anclas 1–5, pasa si todos ≥ 3, media ≥ 3,5 y sin defecto bloqueante. `judge_chapter` en `chapter_close`, `judge_novel` en `pre_publish`; cada criterio es un score `judge:<criterio>` en Langfuse. La misma rúbrica sirve a la revisión humana ([`evals/human-review/`](../../../evals/human-review/)) para comparar juez y humano.

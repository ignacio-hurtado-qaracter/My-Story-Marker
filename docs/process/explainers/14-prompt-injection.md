# Prompt injection y datos no confiables

**Qué es.** Texto que viene de fuera (el comprador, un documento) puede contener instrucciones; se trata siempre como **dato**, nunca como orden.

**Cómo lo aplicamos aquí.** El texto libre del brief pasa por un prescan determinista ([`backend/app/interview/extract.py`](../../../backend/app/interview/extract.py), `prescan_injection`) que registra `free_text_injection` antes de llamar al modelo; el extractor recibe el texto delimitado, devuelve solo hechos candidatos y su propio indicador `injection_suspected`. Solo los hechos extraídos (con `source = free_text`) llegan a la bible, y el escritor y el editor ven el brief sin el texto libre (`brief_summary_document`). El planner y el juez sí reciben el texto crudo, marcado en su prompt como DATOS que no se obedecen: esa exposición es solo defensa de prompt (ver R2 en el log). Probado en vivo y en el eval `b3-injection` ([red-team](../red-team-log.md)).

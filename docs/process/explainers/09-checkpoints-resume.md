# Checkpoints y reanudación

**Qué es.** Guardar el progreso en unidades completas para que un fallo no obligue a empezar de cero, y que reanudar no duplique ni pierda trabajo.

**Cómo lo aplicamos aquí.** Un capítulo cuenta como hecho cuando `checkpoint` llama a `save_chapter_and_checkpoint`, que escribe el texto (`chapter_version`) y el checkpoint en **una transacción** (CE1) y hace upsert por `(version, chapter)` (CE3) ([`backend/app/bible/repository.py`](../../../backend/app/bible/repository.py)). `generate` vuelve a entrar por `first_incomplete_chapter`; relanzar el mismo comando reanuda. Las escenas no se guardan (V4): un capítulo interrumpido se reescribe desde la escena 1.

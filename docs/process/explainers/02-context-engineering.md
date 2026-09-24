# Context engineering, tope de 100k y resúmenes

**Qué es.** Decidir qué entra en la ventana de cada llamada: lo mínimo suficiente, ordenado, delimitado como datos y medido. Más contexto no es mejor: diluye instrucciones y encarece.

**Cómo lo aplicamos aquí.** Cada rol recibe *documentos* con ruta y texto, montados en [`backend/app/novel/context.py`](../../../backend/app/novel/context.py): resumen del brief, sinopsis, **resúmenes de capítulos anteriores** (~120 palabras que escribe el editor), el plan del capítulo, la cola de la escena previa en orden de *historia* (`previous_scene_tail`, ~250 palabras), términos prohibidos y nombres exactos. Nunca la novela entera. El cliente estima los tokens y rechaza antes de lanzar si se supera `CONTEXT_TOKEN_CAP = 100_000` ([`backend/app/commons/config.py`](../../../backend/app/commons/config.py)).

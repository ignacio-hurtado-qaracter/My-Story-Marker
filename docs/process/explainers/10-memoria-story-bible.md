# Memoria: la story bible

**Qué es.** Memoria externa y estructurada del sistema: lo que no cabe ni debe vivir en la ventana del modelo, consultable por código.

**Cómo lo aplicamos aquí.** Una SQLite autoritativa (`HARNESS_DB`) con brief, hechos (`source` = interview · free_text · planner; `mandatory`), `fact_usage` por escena y versión, personajes con fecha de nacimiento, lugares, `chronology_event` + `event_participant`, versiones y capítulos ([esquema](../diagramas.md#esquema-sqlite)). La memoria de trabajo entre capítulos son los resúmenes. Sirve a tres consumidores a la vez: validadores (cobertura), `change_fact` (qué capítulos usan un hecho) y Lean (cronología). Para Claude Code hay además memoria de proyecto en [`.claude/memory/`](../../../.claude/memory/project.md).

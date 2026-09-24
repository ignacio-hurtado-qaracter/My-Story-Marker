# Hooks

**Qué es.** Código que el entorno ejecuta automáticamente en un evento (antes o después de una herramienta), no el modelo. Sirve para imponer reglas que un prompt no garantiza.

**Cómo lo aplicamos aquí.** Dos niveles. En el pipeline, los puntos `before_scene_accept`, `before_chapter_close` y `before_publish` (K4) ejecutan los validadores registrados. En Claude Code, [`.claude/settings.json`](../../../.claude/settings.json) registra `policy_guard.py` (PreToolUse: bloquea `.env`, claves con forma real, escrituras directas a `data/harness.sqlite` y términos prohibidos en capítulos) y `validate_chapter.py` (PostToolUse: longitud y guardrail en capítulos exportados), que llaman **al mismo código** del backend ([`.claude/hooks/`](../../../.claude/hooks/README.md)). Una implementación, dos disparadores.

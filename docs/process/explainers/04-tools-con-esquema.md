# Tools y salidas con esquema validado

**Qué es.** Todo lo que el modelo devuelve (o pide) se describe con un JSON Schema y se valida antes de usarse; lo inválido no se "arregla", se rechaza o se reintenta.

**Cómo lo aplicamos aquí.** Cada rol llama a `claude -p` con el esquema de su modelo pydantic (`NovelPlan`, `SceneDraft`, `ChapterEdit`, el veredicto del juez) y `traced_complete` valida y reintenta una vez ([`backend/app/commons/observability/traced.py`](../../../backend/app/commons/observability/traced.py)). Los validadores `schema_role_output` (scene_accept) y `schema_brief` (pre_publish) lo registran como resultado; el brief tiene su esquema exportado en [`backend/schemas/brief.v1.json`](../../../backend/schemas/brief.v1.json). Los modelos no tienen herramientas (`--tools ""`); las tools MCP de solo lectura (H05) quedaron diferidas (spec 007, preguntas abiertas).

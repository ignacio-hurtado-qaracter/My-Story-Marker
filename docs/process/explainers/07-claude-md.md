# CLAUDE.md

**Qué es.** El fichero de instrucciones que Claude Code lee al abrir el proyecto: qué es, cómo se ejecuta, dónde están las reglas. Es contexto permanente, así que debe ser corto y cierto.

**Cómo lo aplicamos aquí.** [`CLAUDE.md`](../../../CLAUDE.md) importa [`AGENTS.md`](../../../AGENTS.md) (procesos 0–3, protocolo de trabajo en paralelo) y añade lo propio de Claude Code: qué hace el sistema, cómo lanzar una generación, modelos, Langfuse, skills, comandos, memoria, MCP y hooks. Se reescribió en B0 para que se entienda solo (E06). Deliberadamente **no** llega a los roles: `claude -p` corre en un directorio vacío con `--setting-sources ""`, así ningún rol lee reglas de desarrollo.

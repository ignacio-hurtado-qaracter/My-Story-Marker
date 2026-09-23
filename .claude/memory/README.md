# Memoria del proyecto para Claude Code

Copia curada de la memoria automática de Claude Code de este proyecto. La memoria
automática vive en el perfil del usuario de cada máquina y no viaja con el repositorio;
esta carpeta sí. Se versiona para que el contexto se conserve entre dispositivos y porque
el examen pide `.claude/` con memoria.

**Claude Code no carga esta carpeta sola.** Al abrir el proyecto en otra máquina, pide a
Claude que lea `ignore.md` en la raíz y los ficheros de esta carpeta antes de trabajar.

La copia no lleva rutas personales, identificadores de sesión ni referencias a dónde se
guardan credenciales. Se actualiza a mano cuando cambia algo relevante.

| Fichero | Contenido |
|---|---|
| [exam-worktree-partition.md](exam-worktree-partition.md) | Cómo se reparten las sesiones paralelas y las ramas desde que llegó el enunciado |
| [langfuse-claude-code-observability.md](langfuse-claude-code-observability.md) | Las sesiones de Claude Code se trazan a Langfuse con un plugin |
| [windows-python3-stub-gotcha.md](windows-python3-stub-gotcha.md) | En la máquina Windows original, `python3` era el stub de la Microsoft Store |

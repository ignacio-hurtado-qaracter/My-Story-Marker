---
name: langfuse-claude-code-observability
description: El plugin langfuse-observability traza las sesiones de Claude Code a Langfuse Cloud EU desde 2026-09-16
metadata:
  type: project
---

El plugin `langfuse-observability@langfuse-observability` (v1.2.0) está instalado y
operativo en la máquina original desde el 2026-09-16. Envía cada sesión de Claude Code
(prompts, respuestas, tool calls) a Langfuse Cloud EU.

Es configuración de la máquina, no del repositorio: en otro dispositivo hay que instalar
y configurar el plugin de nuevo si se quieren trazas. Las claves nunca van al repo.

Esto traza las **sesiones de desarrollo**. No traza el backend: el backend llama al modelo
con `claude -p --setting-sources ""`, que no carga plugins, y el enunciado exige además
trazas propias del backend (sesión por novela, spans por rol, scores). Eso queda para la
spec del bloque de observabilidad.

**Why:** todo lo que se trabaja en este repo queda registrado en un servicio externo.

**How to apply:** reconfigurar con
`claude plugin install langfuse-observability@langfuse-observability --config KEY=VALUE`
y recargar la ventana. Si deja de trazar en Windows, revisar antes
[[windows-python3-stub-gotcha]].

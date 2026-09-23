---
name: windows-python3-stub-gotcha
description: En la máquina Windows original, `python3` era el stub de Microsoft Store; los hooks que lo llamaban fallaban en silencio
metadata:
  type: project
---

En la máquina Windows original, `python3` resolvía al stub de la Microsoft Store, que
imprime "Python was not found" y sale sin error. Python real (3.12) solo respondía como
`python`. El 2026-09-16 se arregló creando un `python3.exe` junto al `python.exe` real, en
una carpeta que va antes que WindowsApps en el PATH.

El backend usa `uv run` o `py -3.12`, nunca `python3` a secas.

**Why:** cualquier hook o script que invoque `python3` fallaba en silencio, sin log.

**How to apply:** si un hook o herramienta externa "no hace nada" en Windows, comprobar
primero que `python3 --version` responde de verdad. Ver
[[langfuse-claude-code-observability]].

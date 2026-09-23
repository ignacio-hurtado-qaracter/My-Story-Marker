# My-Story-Marker

Sistema agéntico que genera novelas personalizadas para regalar: 10 capítulos de unas
1.000–1.500 palabras, escritos a partir de un brief sobre el destinatario, con una story
bible que mantiene la historia coherente de principio a fin.

> **Estado:** en construcción. El backend base (stores, permisos, índice, auditoría
> mecánica) está en marcha bajo la [spec 001](specs/001-backend-foundation.md). El
> reencuadre al producto de novelas personalizadas está en su ronda de preguntas
> (`exam/process-0/`). El informe de cumplimiento del enunciado está en
> [`exam/compliance.md`](exam/compliance.md).

## Estructura del repositorio

| Ruta | Contenido |
|---|---|
| [`AGENTS.md`](AGENTS.md) | Reglas del repositorio y los procesos para editar docs, specs y código |
| [`CLAUDE.md`](CLAUDE.md) | Instrucciones específicas de Claude Code |
| [`docs/`](docs/) | El diseño: vocabulario, dominio, arquitectura y verificación |
| [`specs/`](specs/) | Una spec por cambio, con su plan de implementación |
| [`backend/`](backend/) | FastAPI y Python. Ver [`backend/README.md`](backend/README.md) |
| `frontend/` | React y three.js. Aún vacío |
| [`exam/`](exam/) | Requisitos del examen como datos y el comprobador de cumplimiento |
| [`presentacion/`](presentacion/) | Presentación formal y anexos |
| [`ejemplos/`](ejemplos/) | Brief de ejemplo y novela de ejemplo en PDF |
| [`.claude/`](.claude/) | Skills y comandos de Claude Code |
| [`.mcp.json`](.mcp.json) | Servidores MCP del proyecto, incluido Playwright para inspección visual |

## Puesta en marcha

El backend se arranca con `uv`; los pasos y la configuración están en
[`backend/README.md`](backend/README.md). Las variables de entorno están documentadas en
[`backend/.env.example`](backend/.env.example). No se usa ninguna API key de Anthropic:
las llamadas al modelo pasan por la CLI de Claude Code con tu propia sesión.

## Comprobar el cumplimiento del enunciado

```bash
python exam/check.py            # regenera exam/compliance.md
python exam/check.py --strict   # falla si falta algo obligatorio
```

En Claude Code, el comando `/exam-gap` hace lo mismo y propone el siguiente bloque.

## Inspección visual con Playwright MCP

[`.mcp.json`](.mcp.json) declara el servidor `playwright` a nivel de proyecto. Claude Code
pide aprobarlo la primera vez que se abre el repositorio. Con él, el agente puede abrir
la lectura web de la novela, navegar por los capítulos y comprobar que el índice, la
ficha de personajes y la portada se ven bien.

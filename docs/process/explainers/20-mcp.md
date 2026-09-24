# MCP (Model Context Protocol)

**Qué es.** Protocolo estándar (JSON-RPC) para que un cliente de IA use herramientas y datos de un servidor externo con esquemas declarados.

**Cómo lo aplicamos aquí.** [`.mcp.json`](../../../.mcp.json) declara el servidor **Playwright MCP** (`npx @playwright/mcp@latest --headless --isolated --browser chromium`) para que Claude Code abra el lector y lo inspeccione. Se usó de verdad por stdio con un cliente propio ([`docs/process/tools/mcp_browser_probe.py`](../tools/mcp_browser_probe.py)): `initialize`, `tools/list`, `browser_navigate`, `browser_snapshot`, `browser_evaluate`, `browser_take_screenshot`, `browser_console_messages`. Hallazgos en el [log del browser MCP](../browser-mcp-log.md). El servidor MCP propio de solo lectura (X01) es opcional y no se ha construido.

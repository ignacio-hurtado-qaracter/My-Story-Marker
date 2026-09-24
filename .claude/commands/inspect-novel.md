---
description: Open the web reader with Playwright MCP and check that cover, chapter index and character sheet render; log findings
argument-hint: [novel_id] [reader URL, default http://localhost:5173]
---

Visual check of the web reader (exam § 5a, visual validator; spec 004 D4 `pre_publish`).
Arguments: `$ARGUMENTS`.

1. Make sure the backend and the reader are running (`cd backend && uv run uvicorn
   app.main:app` and `cd frontend && npm run dev`). If not, start them in the background.
2. With the `playwright` MCP server (`.mcp.json`), open the reader for the novel and check,
   taking a snapshot of each:
   - **Cover**: title, recipient name exactly as in the story bible, personalised dedication.
   - **Index**: all 10 chapters listed; each link opens its chapter; chapters changed in
     the latest version are marked.
   - **Character and place sheet**: every entry links to at least one chapter where it
     appears, and the link lands there.
   - Walk every chapter once: no empty page, no raw markdown or JSON, no console errors.
3. For each failure record: page, what was expected, what was seen, and which role owns
   the fix (writer for prose, planner for structure, reader code for rendering).
4. Append an entry to `docs/process/browser-mcp-log.md` (create it if missing) with: date,
   novel id and version, what was inspected, what was detected, and what change it caused
   in code or prompts (or "none"). This log is exam evidence (K06): write what really
   happened, including clean runs.
5. Report pass/fail per check. Do not fix code from this command; propose the fix.

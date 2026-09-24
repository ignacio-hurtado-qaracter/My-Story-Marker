---
name: security-review-harness
description: Re-run the harness's security review (exam X04) — secrets leak in the whole git history, known-vulnerable dependencies (pip-audit, npm audit), prompt injection through the brief's free text and the reader's change requests, exfiltration between novels/clients through the reader API, the tools and the MCP server, the Claude Code policy hooks, and a quick API-hardening pass — and update docs/security-report.md. Use when asked for a security review, a vulnerability scan, a secrets/dependency audit, or to check that a change did not reopen a finding.
---

# Security review of the gift-novel harness

This skill re-runs the analysis recorded in [`docs/security-report.md`](../../../docs/security-report.md)
and keeps that report current. It **measures**; it does not widen anything. A fix to a
high or medium finding is a small `backend:` / `chore:` commit with a test that fails
without it (`AGENTS.md`, Process 3 rules 10 and 15); a design change (for example adding
login) goes through a spec.

## Ground rules

- **Never open the real `HARNESS_DB`** (`data/harness.sqlite`, or wherever the env points)
  for writing: a novel may be generating against it. Every probe below builds a temporary
  database; export `HARNESS_DB=/nonexistent/x.sqlite` while running them so nothing falls
  back to the real one (the Claude Code hooks log denials only to a DB file that exists).
- **Never print a secret.** Report commit, file and a masked prefix (`sk-ant****`, length)
  only. A real leaked key is flagged for the user to **rotate**; history is not rewritten.
- No live model calls are needed. The probes use the deterministic defences only.

## Steps

Run from the repository root unless a step says `backend/`. Record each command and a
summary of its output in the report's "Método" section.

1. **Set up.** `cd backend && uv sync`; `cd frontend && npm ci --engine-strict=false`.
2. **Secrets leak (history).**
   - `python3 security/scan_secrets.py --verbose` — every added line of `git log -p --all`
     against Anthropic/Langfuse/OpenAI/AWS/GitHub/Slack/JWT/private-key/generic patterns,
     masked. Exit 1 on a non-allowlisted hit.
   - `uvx detect-secrets scan --exclude-files '(\.venv|node_modules|uv\.lock|package-lock\.json|\.claude/worktrees)' .`
     for the working tree; triage each hit (test dummies, doc examples, checksums).
   - `git log --all --name-only --format= | sort -u | grep -iE '(^|/)\.env|\.pem$|\.key$'`
     — only `.env.example` files may ever have been committed; `git check-ignore -v .env
     frontend/.env backend/.env` must show all three ignored (SEC-02).
3. **Dependencies.**
   - `cd backend && uv export --no-hashes --frozen --no-emit-project -o /tmp/req.txt`
     then `uvx pip-audit -r /tmp/req.txt --disable-pip --no-deps`.
   - `cd frontend && npm audit --omit=dev` and `npm audit` (dev included).
   - Also look at unpinned runners: `.mcp.json` (`npx -y …@latest`).
   - Bump a pin only for a patch release that fixes a listed CVE, and only if the gate
     stays green.
4. **Prompt injection.** `cd backend && uv run python ../security/injection_probe.py`.
   Reports, per corpus string (ES/EN, leetspeak, split words, hyphens, zero-width, code
   fences, role tags, `=== END DOCUMENT …` forgery, cross-novel and secret requests), which
   of `app.interview.extract.prescan_injection` and `app.policy.PolicyEngine.check_free_text`
   flag it, plus the boundary checks of `app.commons.llm.protocol.render_prompt`. Any
   `MISS` or `FALSO POSITIVO` is a finding. Then confirm the containment tests still exist
   and pass: `app/novel/tests/test_pipeline.py::test_free_text_not_in_role_documents` and
   `app/judge/tests/test_judge.py::test_brief_summary_drops_free_text`.
5. **Exfiltration between novels.** `cd backend && uv run python ../security/exfiltration_probe.py`.
   Two novels in a temp DB; every reader route, every tool and the MCP wrapper with hostile
   `novel_id`s and `query`s; a change job of another novel; a change aimed at the internal
   `plan` fact; the MCP connection must refuse writes. `no-auth` (SEC-01) was corrected by spec 018 (login); only an unauthenticated local run (AUTH_REQUIRED=0) may
   remain.
6. **Hooks.** `bash security/hooks_probe.sh` — `.claude/hooks/policy_guard.py` must block
   `.env` writes, key-shaped values and direct writes to `harness.sqlite`, and allow code
   edits, placeholders and read-only `select`s.
7. **API hardening.** `cd backend && uv run python ../security/api_hardening_probe.py` —
   CORS preflight not granted, `text/plain` POST not parsed, error bodies without paths or
   tracebacks, `/health` contents, PDF route with a traversal id. Also
   `uv run bandit -r app -q -ll -x '*/tests/*'`.
8. **Gate on touched code.** `cd backend && uv run pytest -q app/interview app/policy
   app/reader app/tools app/mcp_server tests/test_api_contract.py`, `uv run ruff check`,
   `uv run mypy --strict` on the touched packages, `uv run lint-imports`.
9. **Report.** Update `docs/security-report.md` (Spanish): date, commit, the commands and
   their summarised output, the findings table (id, área, descripción, severidad
   crítica/alta/media/baja/info, estado corregido (commit) / aceptado (motivo) /
   pendiente), one detail section per finding. Keep finding ids stable across runs; a new
   finding takes the next free `SEC-NN`.

## Severity scale

- **crítica** — remote, unauthenticated compromise of data or secrets beyond the local demo.
- **alta** — a real secret exposed, or one novel's data readable/writable by a brief of another.
- **media** — a defence that is bypassable or missing on an input that reaches a model or a store.
- **baja** — hardening gaps with no demonstrated impact in the local, single-user setting.
- **info** — observations and confirmed-good controls.

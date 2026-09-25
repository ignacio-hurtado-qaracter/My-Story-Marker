"""Build the presentation annexes (presentacion/anexo-*.pdf) from the repository.

    uvx --with markdown python presentacion/build/build_annexes.py

Each annex is assembled from repository files (Markdown, TLA+, Lean, YAML, eval JSON),
converted to HTML with python-markdown, with every Mermaid block replaced by its PNG
rendered by common.render_mermaid, and printed to PDF with headless Chromium. Re-run it
after the final novel run: the eval tables, costs and TLC numbers are read live.

Options: --only tla,lean,evals,revision,arquitectura · --keep-html (debug).
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
body { font-family: Carlito, Calibri, 'Liberation Sans', Arial, sans-serif; font-size: 10.5pt;
       color: #1F2933; line-height: 1.42; }
h1 { font-family: Caladea, Cambria, Georgia, serif; font-size: 22pt; margin: 0 0 4pt; }
h2 { font-family: Caladea, Cambria, Georgia, serif; font-size: 15pt; color: #1F2933;
     margin: 18pt 0 6pt; border-bottom: 1px solid #D9DEE3; padding-bottom: 3pt; }
h3 { font-size: 12pt; margin: 12pt 0 4pt; }
h4 { font-size: 11pt; margin: 10pt 0 4pt; }
.kicker { color: #C2551F; font-weight: bold; letter-spacing: .06em; font-size: 9pt;
          text-transform: uppercase; }
.lead { color: #52606D; font-size: 11.5pt; margin: 4pt 0 10pt; }
.src { color: #7B8794; font-size: 8.5pt; margin: -2pt 0 6pt; }
.part { page-break-before: always; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt;
        page-break-inside: auto; }
th { background: #1F2933; color: #fff; text-align: left; padding: 4pt 5pt; }
th, td { overflow-wrap: break-word; }
td code { white-space: nowrap; }
td { border-bottom: 1px solid #E4E7EB; padding: 3pt 5pt; vertical-align: top; }
tr:nth-child(even) td { background: #F6F7F9; }
tr { page-break-inside: avoid; }
code { font-family: 'Liberation Mono', 'Courier New', monospace; font-size: 8.6pt;
       background: #F3F5F7; padding: 0 2pt; border-radius: 2pt; }
pre { background: #F3F5F7; border: 1px solid #E4E7EB; border-radius: 4pt; padding: 7pt;
      white-space: pre-wrap; word-break: break-word; font-size: 7.8pt; line-height: 1.3; }
pre code { background: none; padding: 0; font-size: inherit; }
th code { background: none; color: #fff; }
img.diagram { display: block; max-width: 100%; max-height: 235mm; margin: 6pt auto 10pt;
              object-fit: contain; }
blockquote { border-left: 3px solid #C2551F; margin: 6pt 0; padding: 2pt 10pt;
             color: #52606D; background: #FBF4F0; }
.note { background: #FBE9DF; border-radius: 4pt; padding: 8pt 10pt; margin: 8pt 0; }
.pending { background: #FDF3D8; border-radius: 4pt; padding: 8pt 10pt; margin: 8pt 0; }
.meta { color: #7B8794; font-size: 8.5pt; margin-top: 16pt; }
"""


# ----------------------------------------------------------------------------- markdown

def _mermaid_to_img(md_text: str) -> str:
    """Replace ```mermaid blocks with the PNG rendered for the same source, if any."""
    known: dict[str, str] = {}
    for name, (src_file, idx) in C.DIAGRAMS.items():
        blocks = C.mermaid_blocks(src_file)
        if idx < len(blocks):
            png = C.render_mermaid(name)
            if png:
                known[blocks[idx].strip()] = png.resolve().as_uri()

    def repl(m: re.Match[str]) -> str:
        uri = known.get(m.group(1).strip())
        if uri:
            return f'\n<img class="diagram" src="{uri}" alt="diagrama"/>\n'
        return "\n```\n" + m.group(1) + "```\n"

    return re.sub(r"```mermaid\n(.*?)```", repl, md_text, flags=re.S)


def _unlink(md_text: str) -> str:
    """Relative links do not work inside a PDF: keep their text; keep absolute URLs."""
    return re.sub(r"\[([^\]]+)\]\((?!https?://)[^)]+\)", r"\1", md_text)


def md(text: str, demote: int = 0) -> str:
    text = _unlink(_mermaid_to_img(text))
    if demote:
        text = re.sub(r"^(#{1,5}) ", lambda m: "#" * min(6, len(m.group(1)) + demote) + " ",
                      text, flags=re.M)
    out = markdown.markdown(text, extensions=["tables", "fenced_code", "sane_lists"])
    # let long snake_case headers wrap so wide tables fit the page
    return re.sub(r"<th>(.*?)</th>", lambda m: "<th>" + m.group(1).replace("_", "_<wbr>")
                  + "</th>", out)


def code(text: str, lang: str = "") -> str:
    return f'<pre><code class="{lang}">{html.escape(text)}</code></pre>'


def src(rel: str) -> str:
    return f'<p class="src">Fuente: <code>{html.escape(rel)}</code></p>'


def part(title: str, rel: str | None, body: str, first: bool = False) -> str:
    cls = "" if first else ' class="part"'
    return f"<section{cls}><h2>{html.escape(title)}</h2>{src(rel) if rel else ''}{body}</section>"


def page(title: str, kicker: str, lead: str, parts: list[str]) -> str:
    meta = (f'<p class="meta">Generado por presentacion/build/build_annexes.py el '
            f"{date.today().isoformat()} desde el commit {C.git_head()}. Idioma: español; los "
            "ficheros fuente en inglés (código, specs y README técnicos) se reproducen tal "
            "cual.</p>")
    return (f"<!doctype html><html lang='es'><head><meta charset='utf-8'><title>{title}</title>"
            f"<style>{CSS}</style></head><body><div class='kicker'>{kicker}</div>"
            f"<h1>{html.escape(title)}</h1><p class='lead'>{lead}</p>{meta}"
            + "".join(parts) + "</body></html>")


def to_pdf(html_text: str, out: Path, keep: bool) -> None:
    chrome = C.chrome_path()
    if not chrome:
        raise SystemExit("Chromium not found: set CHROME_PATH")
    tmp = C.HERE / ".html"
    tmp.mkdir(exist_ok=True)
    hp = tmp / (out.stem + ".html")
    hp.write_text(html_text, encoding="utf-8")
    cmd = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
           "--allow-file-access-from-files", "--no-pdf-header-footer",
           "--print-to-pdf-no-header", f"--print-to-pdf={out}", hp.resolve().as_uri()]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180)
    if not keep:
        hp.unlink()
    print(f"wrote {out.relative_to(C.ROOT)} ({out.stat().st_size / 1e3:.0f} kB)")


# ----------------------------------------------------------------------------- annexes

def annex_tla() -> tuple[str, str]:
    t = C.tlc()
    cfg = C.tla_config()
    summary = f"""
| Dato | Valor |
|---|---|
| Resultado | {"Model checking completed. No error has been found." if t.ok else "con errores"} |
| Estados generados | {t.generated} |
| Estados distintos | {t.distinct} |
| Profundidad | {t.depth} |
| Duración | {t.duration} |
| TLC | {t.version} |
| Constantes | {", ".join(f"{k} = {v}" for k, v in cfg.items())} |
"""
    tlc_txt = C.read("formal/tla/tlc-output.txt")
    tlc_txt = "\n".join(ln for ln in tlc_txt.splitlines()
                        if not ln.startswith(("Parsing file", "Semantic processing",
                                              "Linting of module")))
    parts = [
        part("Resumen de la última ejecución de TLC", "formal/tla/tlc-output.txt",
             md(summary) + md("Los cuatro contraejemplos CE1–CE4 (sección 5) aparecieron en "
                              "borradores anteriores del modelo y cada uno produjo una regla "
                              "para el código; la tabla acción → código está en la sección 2."),
             first=True),
        part("Qué se modela, propiedades y correspondencia con el código",
             "formal/tla/README.md", md(C.read("formal/tla/README.md"), demote=1)),
        part("Especificación TLA+", "formal/tla/GiftNovelHarness.tla",
             code(C.read("formal/tla/GiftNovelHarness.tla"), "tla")),
        part("Configuración de TLC", "formal/tla/GiftNovelHarness.cfg",
             code(C.read("formal/tla/GiftNovelHarness.cfg"))
             + "<h3>Salida de TLC (sin las líneas de parseo)</h3>" + code(tlc_txt)),
        part("Contraejemplos encontrados", "formal/tla/COUNTEREXAMPLES.md",
             md(C.read("formal/tla/COUNTEREXAMPLES.md"), demote=1)),
    ]
    return "anexo-tla-spec.pdf", page(
        "Especificación TLA+ del harness", "Anexo · verificación formal",
        "Máquina de estados de una novela (configuración → planificación → escritura → "
        "validación → publicación, con reintentos, crash, reanudación y cambio de un hecho), "
        "sus invariantes y propiedades de vivacidad, el resultado de TLC y los contraejemplos "
        "que cambiaron el código.", parts)


def annex_lean() -> tuple[str, str]:
    real = C.lean_real_case()
    if real:
        real_html = md(real, demote=1)
    else:
        log = C.read("evals/results/before/logs/b4-temporal.log")
        lines = [ln for ln in log.splitlines() if "chronology" in ln][:8]
        real_html = (
            "<div class='pending'><b>Pendiente.</b> Todavía no hay un caso real que Lean haya "
            "cazado en <code>pre_publish</code> y ningún otro validador (requisito L04). Cuando "
            "exista, se documenta en <code>docs/process/lean-caso-real.md</code> y este anexo "
            "lo incluye al reconstruirse.</div>"
            + md("**Lo más cercano observado.** En el eval `b4-temporal` (trampas temporales "
                 "plantadas: edades imposibles, una mascota que muere y reaparece, una persona "
                 "que emigra y vuelve, bilocación), el diagnóstico de cronología del plan "
                 "(`chronology_problems`, los mismos cuatro invariantes que el modelo Lean, "
                 "ejecutado antes de escribir) detectó las apariciones tras la muerte "
                 "(`noAfterExit`); tras un replan el pipeline se detuvo con `plan_limit` sin "
                 "escribir ningún capítulo. Extracto del log:")
            + code("\n".join(lines))
            + md(C.read("docs/process/red-team-log.md").split("## R3")[1].split("\n## ")[0]
                 if "## R3" in C.read("docs/process/red-team-log.md") else "", demote=1))
    parts = [
        part("Modelo, invariantes y cómo lo usa el harness", "formal/lean/README.md",
             md(C.read("formal/lean/README.md"), demote=1), first=True),
        part("Caso real (L04)", "docs/process/lean-caso-real.md · evals/results", real_html),
        part("Modelo e invariantes en Lean 4", "formal/lean/Chronology/Basic.lean",
             code(C.read("formal/lean/Chronology/Basic.lean"), "lean")),
        part("Cronologías de ejemplo", "formal/lean/examples/",
             "<h3>ok.json (pasa)</h3>" + code(C.read("formal/lean/examples/ok.json"))
             + "<h3>incoherent.json (falla agesCoherent y noBilocation)</h3>"
             + code(C.read("formal/lean/examples/incoherent.json"))),
    ]
    return "anexo-lean-invariantes.pdf", page(
        "Invariantes Lean 4 de la cronología", "Anexo · verificación formal",
        "Modelo Lean 4 de la cronología de la historia (eventos, fechas, lugares, personajes y "
        "fechas de nacimiento) generado desde la story bible; cuatro invariantes con prueba de "
        "corrección, y el caso real del eval temporal.", parts)


def _drop_column(md_text: str, header: str) -> str:
    """Remove one column (by header) from every pipe table that has it."""
    out, idx = [], None
    for ln in md_text.splitlines():
        s = ln.strip()
        if s.startswith("|") and s.endswith("|"):
            cells = s.strip("|").split("|")
            if idx is None and header in [c.strip() for c in cells]:
                idx = [c.strip() for c in cells].index(header)
            if idx is not None and idx < len(cells):
                cells.pop(idx)
            out.append("|" + "|".join(cells) + "|")
        else:
            idx = None
            out.append(ln)
    return "\n".join(out)


def annex_evals() -> tuple[str, str]:
    runs = C.eval_runs()
    rows = ["| Brief | Iteración | Resultado | Capítulos | Llamadas | Coste USD | Tiempo de "
            "modelo | Versión final | Tokens in/out |", "|---|---|---|---|---|---|---|---|---|"]
    import json
    tok: dict[tuple[str, str], str] = {}
    for f in sorted((C.ROOT / "evals/results").glob("*/*.json")):
        try:
            c = json.loads(f.read_text(encoding="utf-8")).get("cost") or {}
        except (OSError, ValueError):
            continue
        if c:
            tok[(f.stem, f.parent.name)] = f"{c.get('input_tokens')}/{c.get('output_tokens')}"
    for r in runs:
        fin = r.final or {}
        rows.append(
            f"| `{r.brief}` | {r.label} | {r.outcome} | {r.chapters or '—'} | "
            f"{r.calls or '—'} | {f'{r.cost:.4f}' if r.cost else '—'} | "
            f"{f'{r.latency_s / 60:.1f} min' if r.latency_s else '—'} | "
            f"{('v' + str(fin.get('version')) + ' ' + str(fin.get('status'))) if fin else '—'} | "
            f"{tok.get((r.brief, r.label), '—')} |")
    chap = ["| Brief | Iteración | Capítulo | Llamadas | Coste USD | Tiempo |",
            "|---|---|---|---|---|---|"]
    for r in runs:
        for c in r.by_chapter:
            chap.append(f"| `{r.brief}` | {r.label} | {c.get('chapter') or 'plan / novela'} | "
                        f"{c.get('calls')} | {c.get('cost_usd', 0):.4f} | "
                        f"{c.get('latency_s', 0) / 60:.1f} min |")
    tuning = C.tuning_md()
    tuning_html = md(tuning, demote=1) if tuning else (
        "<div class='pending'><b>Pendiente.</b> La iteración de tuning se registra con "
        "<code>evals/run_evals.py --label after</code> tras un cambio de prompt y "
        "<code>evals/compare_iterations.py before after --change \"…\"</code>, que escribe "
        "<code>evals/results/tuning.md</code>. Este anexo la incluye al reconstruirse.</div>"
        + md("**Lectura del `before`:** el validador que bloquea la publicación es "
             "`brief_coverage` (recuerdos obligatorios del brief que no aparecen en el texto), "
             "en `b2-infantil` y `b3-injection`; `b3` marca la inyección (⚑) y no la sigue; "
             "`b4-temporal` se detiene en la planificación por la cronología; `b5` se rechaza "
             "en la validación del brief, como se esperaba."))
    r = C.runs()
    nov = ["| Novela | Momento | Estado | Motivo | Capítulos | Rondas de reparación | Llamadas "
           "| Coste USD | Minutos |", "|---|---|---|---|---|---|---|---|---|"]
    three = r.get("three_chapter_novel") or {}
    if three:
        nov.append(f"| `{three.get('novel_id')}` (3 cap.) | — | {three.get('status')} | — | "
                   f"{three.get('chapters')} | {three.get('repair_rounds')} | "
                   f"{three.get('calls')} | {three.get('cost_usd')} | {three.get('minutes')} |")
    for a in r.get("ten_chapter_attempts") or []:
        nov.append(f"| `{a.get('novel_id')}` | {a.get('when')} | {a.get('status')} | "
                   f"{a.get('validator')}: {a.get('why')} | {a.get('chapters_written')} | "
                   f"{a.get('repair_rounds')} | {a.get('calls')} | {a.get('cost_usd')} | "
                   f"{a.get('minutes')} |")
    fin = r.get("final_novel") or {}
    nov.append(f"| `{fin.get('novel_id') or '—'}` (final) | después del tuning 2 | "
               f"{fin.get('status') or 'pendiente'} | {fin.get('judge_novel') or '—'} | "
               f"{fin.get('chapters') or '—'} | {fin.get('repair_rounds') if fin.get('repair_rounds') is not None else '—'} | "
               f"{fin.get('calls') or '—'} | {fin.get('cost_usd') or '—'} | "
               f"{fin.get('minutes') or '—'} |")
    t2 = C.iteration_section("Iteración de tuning 2")
    tuning2_html = (md(t2, demote=2) if t2 else "<div class='pending'><b>Pendiente.</b></div>")
    labels = C.eval_labels()
    per_label = "".join(
        f"<h3>Iteración «{lab}»</h3>" + md(_drop_column(re.sub(
            r"^# .*\n", "", C.read(f"evals/results/{lab}/table.md")), "tokens in/out"),
            demote=2)
        for lab in labels if C.read(f"evals/results/{lab}/table.md"))
    parts = [
        part("Tabla validador × brief (última iteración)", "evals/results.md",
             md(_drop_column(re.sub(r"^# .*\n", "", C.read("evals/results.md")),
                             "tokens in/out"), demote=1)
             + "<p class='src'>Tokens por ejecución en la sección 3.</p>", first=True),
        part("Iteración de tuning: antes / después", "evals/results/tuning.md", tuning_html),
        part("Novelas completas y tuning 2", "presentacion/build/data/runs.json · "
             "docs/process/iteraciones.md", md("\n".join(nov)) + tuning2_html),
        part("Coste y latencia por ejecución", "evals/results/*/*.json",
             md("\n".join(rows)) + "<h3>Por capítulo</h3>" + md("\n".join(chap))),
        part("Tablas por iteración", "evals/results/<iteración>/table.md", per_label or
             "<p>—</p>"),
        part("Los cinco briefs y cómo se ejecutan", "evals/README.md",
             md(C.read("evals/README.md"), demote=1)),
    ]
    return "anexo-evals-tabla.pdf", page(
        "Evals: briefs × validadores", "Anexo · evaluación",
        f"Cinco briefs de prueba (uno de ejemplo, uno infantil, uno con inyección, uno con "
        f"incoherencias temporales y uno contradictorio) contra todos los validadores. "
        f"Iteraciones disponibles: {', '.join(labels) or '—'}.", parts)


def annex_review() -> tuple[str, str]:
    reviews = sorted((C.ROOT / "evals/human-review").glob("review-*.yaml"))
    comps = sorted((C.ROOT / "evals/human-review").glob("comparison-*.md"))
    status = ("<div class='pending'><b>Estado: pendiente.</b> La revisión humana de una novela "
              "completa la hace el autor con la rúbrica y la plantilla de este anexo; "
              "<code>compare.py</code> la compara después con las notas del juez LLM.</div>"
              if not reviews else
              f"<div class='note'><b>Revisiones rellenadas:</b> "
              f"{', '.join(p.name for p in reviews)}.</div>")
    parts = [part("Estado y protocolo", "evals/human-review/README.md",
                  status + md(C.read("evals/human-review/README.md"), demote=1), first=True),
             part("Rúbrica (la misma que usa el juez)", "evals/human-review/rubrica.md",
                  md(C.read("evals/human-review/rubrica.md"), demote=1))]
    for c in comps:
        parts.append(part(f"Comparación humano vs. juez · {c.stem}",
                          str(c.relative_to(C.ROOT)), md(c.read_text(encoding="utf-8"), 1)))
    parts.append(part("Plantilla en blanco", "evals/human-review/review-template.yaml",
                      code(C.read("evals/human-review/review-template.yaml"), "yaml")))
    return "anexo-revision-humana.pdf", page(
        "Revisión humana con la rúbrica del juez", "Anexo · evaluación semántica",
        "Segundo validador semántico: una persona lee una novela completa y la puntúa con la "
        "misma rúbrica que el juez LLM, para calibrarlo.", parts)


def annex_arch() -> tuple[str, str]:
    diag = C.read("docs/process/diagramas.md")
    diag = re.sub(r"^# .*\n", "", diag)
    parts = [
        part("Arquitectura en resumen", "README.md",
             md("```mermaid\n" + C.mermaid_blocks("README.md")[0] + "```\n"
                if C.mermaid_blocks("README.md") else "")
             + md("Roles: entrevistador, planner, writer, editor, juez (y canonizador heredado), "
                  "todos con Claude Haiku 4.5 vía la CLI de Claude Code, sin herramientas; el "
                  "orquestador escribe en la BD en su nombre. Memoria: una SQLite autoritativa "
                  "(story bible). Observabilidad: Langfuse (sesión por novela, spans por rol y "
                  "tool, coste, scores y prompts versionados)."), first=True),
        part("Diagramas: arquitectura, máquina de estados, esquema SQLite y validadores",
             "docs/process/diagramas.md", md(diag, demote=1)),
        part("Cómo se construyó: oleadas de bloques", "docs/process/spec-inicial.md",
             md("```mermaid\n" + C.mermaid_blocks("docs/process/spec-inicial.md")[0] + "```\n")
             + md("```mermaid\n"
                  + C.mermaid_blocks("docs/process/subagentes-comandos-skills.md")[0]
                  + "```\n")),
    ]
    return "anexo-arquitectura.pdf", page(
        "Arquitectura del harness", "Anexo · arquitectura",
        "Roles, validadores y su punto de ejecución, esquema de la story bible en SQLite, "
        "máquina de estados y observabilidad. Los diagramas son Mermaid renderizados desde "
        "docs/process/diagramas.md.", parts)


ANNEXES = {"tla": annex_tla, "lean": annex_lean, "evals": annex_evals,
           "revision": annex_review, "arquitectura": annex_arch}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--keep-html", action="store_true")
    ap.add_argument("--render", action="store_true", help="force Mermaid re-render")
    a = ap.parse_args()
    C.render_all(force=a.render)
    names = [n for n in a.only.split(",") if n] or list(ANNEXES)
    for n in names:
        fname, doc = ANNEXES[n]()
        to_pdf(doc, C.PRES / fname, a.keep_html)


if __name__ == "__main__":
    main()

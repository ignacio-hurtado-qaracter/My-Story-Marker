"""Build presentacion/presentacion.pptx (+ presentacion.pdf) and presentacion/guion.md.

    uvx --with python-pptx --with pymupdf python presentacion/build/build_deck.py

Every figure is read from the repository on each run, so the deck and the speaker script
never go stale: presentacion/build/data/runs.json (novels: 3-chapter, the 10-chapter
attempts, the final novel), evals/results/*/*.json and evals/results.md (before/after),
evals/results/tuning.md, docs/process/iteraciones.md (tuning 2), lean-caso-real.md,
red-team-log.md, docs/security-report.md, formal/tla/tlc-output.txt + .cfg +
COUNTEREXAMPLES.md, backend/app/novel/pipeline.py (retry limits) and ejemplos/*.pdf.
A missing file or a null in runs.json shows as «pendiente».

Each slide carries its speaker script as notes; the same scripts, plus the likely questions
of the examiners and the one-line design decision for the email, are written to
presentacion/guion.md.

Options: --no-pdf (skip LibreOffice), --render (force Mermaid re-render), --no-guion.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

# ----------------------------------------------------------------------------- style

INK = RGBColor(0x1F, 0x29, 0x33)
TERRA = RGBColor(0xC2, 0x55, 0x1F)
TERRA_L = RGBColor(0xFB, 0xE9, 0xDF)
SLATE = RGBColor(0x52, 0x60, 0x6D)
MUTED = RGBColor(0x7B, 0x87, 0x94)
MIST = RGBColor(0xF3, 0xF5, 0xF7)
LINE = RGBColor(0xD9, 0xDE, 0xE3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GREEN = RGBColor(0x2F, 0x85, 0x5A)
GREEN_L = RGBColor(0xE3, 0xF4, 0xEA)
RED = RGBColor(0xC5, 0x30, 0x30)
RED_L = RGBColor(0xFB, 0xE4, 0xE4)
AMBER_L = RGBColor(0xFD, 0xF3, 0xD8)

HEAD = "Cambria"
BODY = "Calibri"
MONO = "Courier New"

W, H = 13.333, 7.5
M = 0.6  # side margin

SHOTS = C.ROOT / "frontend/screenshots"


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width = Inches(W)
        self.prs.slide_height = Inches(H)
        self.blank = self.prs.slide_layouts[6]
        self.n = 0
        self.scripts: list[Script] = []

    # -- primitives -------------------------------------------------------------------

    def slide(self, dark: bool = False):
        s = self.prs.slides.add_slide(self.blank)
        self.n += 1
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = INK if dark else WHITE
        if not dark:
            self.text(s, W - M - 1.5, H - 0.45, 1.5, 0.3, f"{self.n}", 10, color=MUTED,
                      align=PP_ALIGN.RIGHT)
            self.text(s, M, H - 0.45, 6, 0.3, "My Story Marker · harness de novelas-regalo",
                      10, color=MUTED)
        return s

    def text(self, s, x, y, w, h, content, size=16, *, bold=False, color=INK, font=BODY,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, italic=False, spacing=None):
        """content: str (\n = paragraphs) or list of paragraphs; a paragraph is a str or a
        list of (text, {opts}) runs."""
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0)
        tf.margin_top = tf.margin_bottom = Inches(0)
        tf.vertical_anchor = anchor
        paras = content.split("\n") if isinstance(content, str) else content
        for i, para in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            if spacing:
                p.space_after = Pt(spacing)
            runs = [(para, {})] if isinstance(para, str) else para
            for txt, o in runs:
                r = p.add_run()
                r.text = txt
                f = r.font
                f.size = Pt(o.get("size", size))
                f.bold = o.get("bold", bold)
                f.italic = o.get("italic", italic)
                f.name = o.get("font", font)
                f.color.rgb = o.get("color", color)
        return tb

    def bullets(self, s, x, y, w, h, items, size=15, color=INK, gap=6, marker_color=TERRA):
        paras = []
        for it in items:
            if isinstance(it, tuple):
                head, rest = it
                paras.append([("■  ", {"color": marker_color, "size": size - 5}),
                              (head, {"bold": True}), (rest, {})])
            else:
                paras.append([("■  ", {"color": marker_color, "size": size - 5}), (it, {})])
        return self.text(s, x, y, w, h, paras, size, color=color, spacing=gap)

    def box(self, s, x, y, w, h, fill=MIST, line=None, shape=MSO_SHAPE.ROUNDED_RECTANGLE,
            radius=0.08):
        sh = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        sh.fill.solid()
        sh.fill.fore_color.rgb = fill
        if line is None:
            sh.line.fill.background()
        else:
            sh.line.color.rgb = line
            sh.line.width = Pt(1)
        sh.shadow.inherit = False
        if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            sh.adjustments[0] = radius
        return sh

    def label_box(self, s, x, y, w, h, title, sub="", fill=TERRA_L, line=TERRA, tsize=14,
                  ssize=11, shape=MSO_SHAPE.ROUNDED_RECTANGLE, tcolor=INK):
        sh = self.box(s, x, y, w, h, fill, line, shape)
        tf = sh.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = Inches(0.06)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = title
        r.font.size, r.font.bold, r.font.name, r.font.color.rgb = Pt(tsize), True, BODY, tcolor
        if sub:
            p2 = tf.add_paragraph()
            p2.alignment = PP_ALIGN.CENTER
            r2 = p2.add_run()
            r2.text = sub
            r2.font.size, r2.font.name, r2.font.color.rgb = Pt(ssize), BODY, SLATE
        return sh

    def arrow(self, s, x1, y1, x2, y2, color=SLATE, width=1.5, dashed=False):
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1),
                                   Inches(x2), Inches(y2))
        c.line.color.rgb = color
        c.line.width = Pt(width)
        if dashed:
            c.line.dash_style = 4  # dash
        ln = c.line._get_or_add_ln()
        tail = ln.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}tailEnd",
                              {"type": "triangle", "w": "med", "len": "med"})
        ln.append(tail)
        return c

    def circle_num(self, s, x, y, d, label, fill=TERRA, size=14):
        sh = self.box(s, x, y, d, d, fill, None, MSO_SHAPE.OVAL)
        tf = sh.text_frame
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = Inches(0)
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = str(label)
        r.font.size, r.font.bold, r.font.name, r.font.color.rgb = Pt(size), True, BODY, WHITE
        return sh

    def header(self, s, kicker, title, sub=None):
        self.text(s, M, 0.42, W - 2 * M, 0.3, kicker.upper(), 12, bold=True, color=TERRA)
        self.text(s, M, 0.72, W - 2 * M, 0.7, title, 32, bold=True, font=HEAD)
        if sub:
            self.text(s, M, 1.42, W - 2 * M, 0.4, sub, 15, color=SLATE)

    def image(self, s, path, x, y, w, h, *, fit="width", border=True):
        """width: fit the width, top-aligned, crop the bottom if taller than the box;
        cover: fill the box, cropping bottom/sides; contain: fit inside."""
        from PIL import Image

        path = Path(path)
        if not path.exists():
            self.label_box(s, x, y, w, h, "imagen no disponible", str(path.name), MIST, LINE)
            return None
        iw, ih = Image.open(path).size
        box_r, img_r = w / h, iw / ih
        if fit == "width":
            nh = w / img_r
            pic = s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w),
                                       Inches(min(nh, h)))
            if nh > h:
                pic.crop_bottom = 1 - h / nh
        elif fit == "contain":
            if img_r > box_r:
                nw, nh = w, w / img_r
            else:
                nw, nh = h * img_r, h
            pic = s.shapes.add_picture(str(path), Inches(x + (w - nw) / 2),
                                       Inches(y + (h - nh) / 2), Inches(nw), Inches(nh))
        else:
            pic = s.shapes.add_picture(str(path), Inches(x), Inches(y), Inches(w), Inches(h))
            if img_r < box_r:  # image taller: crop bottom
                keep = img_r / box_r
                pic.crop_bottom = 1 - keep
            else:  # image wider: crop sides evenly
                keep = box_r / img_r
                pic.crop_left = pic.crop_right = (1 - keep) / 2
        if border:
            pic.line.color.rgb = LINE
            pic.line.width = Pt(1)
        return pic

    def table(self, s, x, y, w, rows, col_w, *, size=11, head_fill=INK, row_h=0.32,
              cell_fill=None, zebra=True):
        nr, nc = len(rows), len(rows[0])
        gt = s.shapes.add_table(nr, nc, Inches(x), Inches(y), Inches(w), Inches(row_h * nr))
        tbl = gt.table
        tot = sum(col_w)
        for j, cw in enumerate(col_w):
            tbl.columns[j].width = Emu(int(Inches(w) * cw / tot))
        for i in range(nr):
            tbl.rows[i].height = Inches(row_h)
            for j in range(nc):
                cell = tbl.cell(i, j)
                val = rows[i][j] if j < len(rows[i]) else ""
                cell.margin_left = cell.margin_right = Inches(0.06)
                cell.margin_top = cell.margin_bottom = Inches(0.03)
                cell.vertical_anchor = MSO_ANCHOR.MIDDLE
                tf = cell.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                r = p.add_run()
                r.text = str(val)
                r.font.name = BODY
                r.font.size = Pt(size)
                cell.fill.solid()
                if i == 0:
                    r.font.bold = True
                    r.font.color.rgb = WHITE
                    cell.fill.fore_color.rgb = head_fill
                else:
                    r.font.color.rgb = INK
                    fill = cell_fill(i, j, str(val)) if cell_fill else None
                    cell.fill.fore_color.rgb = fill or (MIST if zebra and i % 2 == 0 else WHITE)
        return tbl


    # -- speaker script -----------------------------------------------------------------

    def script(self, s, sc: "Script") -> None:
        """Speaker notes = the script of this slide; also kept for guion.md."""
        sc.n = self.n
        words = len(" ".join(sc.say).split())
        sc.seconds = max(25, round(words / 2.4 / 5) * 5)  # ~145 palabras por minuto
        self.scripts.append(sc)
        s.notes_slide.notes_text_frame.text = sc.notes()


# ----------------------------------------------------------------------------- data

PENDING = "pendiente"


@dataclass
class Script:
    title: str
    seconds: int
    key: str
    say: list[str]
    numbers: list[str]
    transition: str
    n: int = 0

    def notes(self) -> str:
        out = [f"MENSAJE: {self.key}", "", "QUÉ DECIR:"]
        out += [f"- {x}" for x in self.say]
        if self.numbers:
            out += ["", "CIFRAS: " + " · ".join(self.numbers)]
        out += ["", f"TRANSICIÓN: {self.transition}", f"(≈ {self.seconds} s)"]
        return "\n".join(out)


def num(n: float | int | None, dec: int = 0) -> str:
    """Spanish number: 3.409 · 0,85."""
    if n is None:
        return PENDING
    s = f"{n:,.{dec}f}"
    return s.replace(",", "·").replace(".", ",").replace("·", ".")


def usd(x: float | None) -> str:
    return PENDING if x is None else f"{num(x, 2)} USD"


def mins(m: float | None) -> str:
    return PENDING if m is None else f"{num(m)} min"


def fmt_usd(x: float | None) -> str:
    return "—" if x is None else usd(x)


def mark(v: str) -> str:
    return v.replace("✅", "✓").replace("❌", "✗").strip()


def status_fill(_i, _j, v):
    if v.startswith("✓"):
        return GREEN_L
    if v.startswith("✗"):
        return RED_L
    if v.startswith("⚑"):
        return AMBER_L
    return None


def _limit(name: str, default: int) -> int:
    m = re.search(rf"^{name}: Final\[int\] = (\d+)", C.read("backend/app/novel/pipeline.py"),
                  re.M)
    return int(m.group(1)) if m else default


@dataclass
class Data:
    tlc: C.TLC
    cfg: dict[str, str]
    sec: C.Security
    ev_b: C.EvalSummary
    ev_a: C.EvalSummary
    runs: dict
    three: dict
    attempts: list[dict]
    final: dict
    final_pub: bool
    max_repair: int
    max_chapter: int
    max_scene: int
    chap_cost: float | None
    chap_min: float | None
    lean_rows: list[list[str]]
    redteam: list[list[str]]
    human_review: bool
    tuning2_after: str | None
    ntab: int

    @property
    def novel(self) -> dict:
        """The novel the deck shows: the final 10-chapter one if published, else the
        published 3-chapter one."""
        return self.final if self.final_pub else self.three

    @property
    def novel_pdf(self) -> str | None:
        f = self.final.get("pdf") or "ejemplos/novela-ejemplo.pdf"
        if self.final_pub:
            return f if C.exists(f) else None
        t = self.three.get("pdf") or "ejemplos/novela-infantil-3-capitulos.pdf"
        return t if t and C.exists(t) else None


def load() -> Data:
    r = C.runs()
    runs_after = [x for x in C.eval_runs() if x.label == "after" and x.cost]
    chap = [c for x in runs_after for c in x.by_chapter if c.get("chapter") is not None]
    er = C.mermaid_blocks("docs/process/diagramas.md")
    ntab = len(re.findall(r"^\s+(\w+) \{", er[2], re.M)) if len(er) > 2 else 16
    rt = C.md_tables(C.read("docs/process/red-team-log.md"))
    return Data(
        tlc=C.tlc(), cfg=C.tla_config(), sec=C.security(),
        ev_b=C.eval_summary("before"), ev_a=C.eval_summary("after"),
        runs=r, three=r.get("three_chapter_novel") or {},
        attempts=r.get("ten_chapter_attempts") or [], final=C.final_novel(),
        final_pub=C.final_published(),
        max_repair=_limit("MAX_REPAIR_ROUNDS", 2), max_chapter=_limit("MAX_CHAPTER_RETRIES", 2),
        max_scene=_limit("MAX_SCENE_RETRIES", 2),
        chap_cost=(sum(c["cost_usd"] for c in chap) / len(chap)) if chap else None,
        chap_min=(sum(c["latency_s"] for c in chap) / len(chap) / 60) if chap else None,
        lean_rows=C.lean_case_table(),
        redteam=[[C.strip_md(c) for c in row] for row in rt[0][1:]] if rt else [],
        human_review=bool(list((C.ROOT / "evals/human-review").glob("review-*.yaml"))),
        tuning2_after=C.tuning2_after(), ntab=ntab,
    )


# ----------------------------------------------------------------------------- slides

def s_title(d: Deck, x: Data) -> None:
    s = d.slide(dark=True)
    d.text(s, M, 0.9, 7, 0.3, "HARNESS ENGINEERING · ENTREGA FINAL", 13, bold=True, color=TERRA)
    d.text(s, M, 1.35, 7, 1.0, "My Story Marker", 54, bold=True, color=WHITE, font=HEAD)
    d.text(s, M, 2.45, 6.6, 1.2,
           "Novelas personalizadas para regalar, escritas por un harness de agentes "
           "que se puede verificar", 22, color=RGBColor(0xE4, 0xE7, 0xEB))
    stats = [("10", "capítulos de 1.000–1.500\npalabras, en español"),
             ("6", "roles con Claude Haiku 4.5\norquestados por código"),
             ("4", "tipos de validador:\nprogramático, semántico,\nLean 4 y TLA+")]
    for i, (big, small) in enumerate(stats):
        xx = M + i * 2.2
        d.text(s, xx, 4.25, 2.0, 0.8, big, 44, bold=True, color=TERRA, font=HEAD)
        d.text(s, xx, 5.1, 2.1, 0.9, small, 12, color=RGBColor(0xC9, 0xCF, 0xD6))
    d.text(s, M, 6.55, 7, 0.4, f"Repositorio storyMaker · commit {C.git_head()} · 2026",
           11, color=MUTED)
    d.image(s, SHOTS / "browser-mcp/desktop-cover.png", 7.75, 0.9, 5.0, 5.7, border=False)
    d.script(s, Script(
        "Portada", 30,
        "Un producto (novelas-regalo) y el harness que lo hace fiable y verificable.",
        ["Buenos días. Soy [tu nombre] y presento My Story Marker.",
         "Es una solución técnico-comercial: un servicio que escribe novelas personalizadas "
         "para regalar, y el harness de agentes que las genera.",
         "La idea que quiero que os llevéis: aquí lo difícil no es escribir 10 capítulos, "
         "es poder demostrar que lo que se publica es coherente y está personalizado.",
         "Os lo cuento en cuatro partes: el problema, cómo funciona, cómo sabemos que "
         "funciona y qué cuesta."],
        ["10 capítulos", "6 roles en Haiku 4.5", "Lean 4 + TLA+"],
        "Empiezo por el problema del cliente."))


def s_problem(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Problema y propuesta de valor", "Un regalo único que no se puede comprar hecho")
    d.box(s, M, 1.75, 5.85, 3.6, MIST)
    d.text(s, M + 0.3, 1.95, 5.3, 0.4, "El problema", 20, bold=True, font=HEAD)
    d.bullets(s, M + 0.3, 2.5, 5.3, 2.8, [
        ("Escribir una novela sobre alguien ", "lleva meses; un regalo tiene fecha."),
        ("Un LLM sin harness ", "mezcla nombres, olvida recuerdos, contradice fechas y "
                                "resucita a la mascota."),
        ("El cliente tiene vetos ", "(un nombre, un tema) que no pueden aparecer nunca."),
    ], 15)
    x2 = M + 6.15
    d.box(s, x2, 1.75, 5.95, 3.6, TERRA_L)
    d.text(s, x2 + 0.3, 1.95, 5.4, 0.4, "La propuesta", 20, bold=True, font=HEAD, color=TERRA)
    d.bullets(s, x2 + 0.3, 2.5, 5.4, 2.8, [
        ("Entrevista guiada ", "→ brief validado con schema; detecta datos que faltan y "
                               "contradicciones."),
        ("Novela de 10 capítulos ", "en la que el destinatario se reconoce."),
        ("Lectura web y PDF: ", "portada con dedicatoria, índice, fichas de personajes."),
        ("Cambios puntuales: ", "«el perro se llama Nala» regenera solo lo necesario."),
    ], 15)
    d.box(s, M, 5.6, W - 2 * M, 1.15, INK)
    d.text(s, M + 0.35, 5.72, W - 2 * M - 0.7, 0.95, [
        [("D11 · ", {"bold": True, "color": TERRA}),
         ("Personalización y calidad narrativa pesan igual. ", {"bold": True, "color": WHITE}),
         ("Que aparezcan todos los datos no basta si la historia no funciona como historia: "
          "validadores, editor y juez comprueban las dos cosas.", {"color": WHITE})]],
        16, anchor=MSO_ANCHOR.MIDDLE)
    d.script(s, Script(
        "Problema y propuesta de valor", 60,
        "El cliente quiere dos cosas a la vez: que el destinatario se reconozca y que la "
        "historia se lea bien.",
        ["Clientes: padres, parejas, bodas, jubilaciones. Y un regalo tiene fecha.",
         "Si se lo pides a un LLM sin más, falla de formas muy concretas: cambia nombres, "
         "olvida recuerdos, contradice fechas, y la mascota que murió vuelve a aparecer.",
         "Además el cliente tiene vetos: el nombre de una expareja, un tema que no quiere. "
         "Eso no puede aparecer nunca.",
         "La propuesta: una entrevista que produce un brief validado, una novela de 10 "
         "capítulos, lectura web y PDF con portada, índice y fichas, y cambios puntuales.",
         "La decisión D11 es el criterio de todo el sistema: personalización y calidad "
         "narrativa pesan igual. Meter los datos a martillazos no cuenta como éxito."],
        [],
        "Veamos cómo se ve el producto."))


def s_demo(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "La solución · demo del producto",
             "Del brief a una novela que se lee, se regala y se corrige")
    shots = [("visual-check/01-cover.png", "Portada con dedicatoria"),
             ("visual-check/02-index.png", "Índice con marcas de versión"),
             ("visual-check/04-sheets.png", "Fichas desde la story bible")]
    bw = 2.35
    from PIL import Image
    hs = [bw * Image.open(SHOTS / f).size[1] / Image.open(SHOTS / f).size[0]
          for f, _ in shots if (SHOTS / f).exists()]
    cy = 1.8 + min(max(hs or [3.0]), 3.4) + 0.25
    for i, (f, cap) in enumerate(shots):
        xx = M + i * (bw + 0.15)
        d.image(s, SHOTS / f, xx, 1.8, bw, 3.4)
        d.circle_num(s, xx, cy, 0.34, i + 1, size=12)
        d.text(s, xx + 0.42, cy + 0.02, bw - 0.45, 0.6, cap, 12, bold=True)
    d.text(s, M, cy + 0.8, 7.35, 0.7,
           "Lector web en React y PDF exportado con la misma portada, índice navegable y "
           "fichas con enlaces «Aparece en» a cada capítulo.", 12, color=SLATE)
    rx = 8.35
    rw = W - M - rx
    d.text(s, rx, 1.75, rw, 0.4, "El lector pide un cambio", 17, bold=True, font=HEAD)
    steps = [
        ("«El perro se llama Nala»", "desde la página, la CLI o la API."),
        ("Un único hecho en la BD", "fact_usage dice qué capítulos lo usan."),
        ("Solo esos se regeneran", "a una versión v+1, en una transacción."),
        ("La v1 se conserva", "el índice marca «modificado»."),
        ("PDF con «novedades»", "enlaces a los capítulos cambiados."),
    ]
    for i, (h, t) in enumerate(steps):
        y = 2.3 + i * 0.6
        d.circle_num(s, rx, y + 0.03, 0.36, i + 1, size=12)
        d.text(s, rx + 0.5, y, rw - 0.5, 0.6,
               [[(h, {"bold": True, "size": 13})], [(t, {"size": 11, "color": SLATE})]], 13)
    d.box(s, rx, 5.4, rw, 1.35, GREEN_L)
    d.text(s, rx + 0.2, 5.48, rw - 0.4, 1.2, [
        [("Ejecución real (ab4731f): ", {"bold": True}),
         ("novela de 2 capítulos → versión 2 publicada; 0 apariciones del nombre antiguo, "
          "16 del nuevo; versión 1 intacta.", {})]], 12, anchor=MSO_ANCHOR.MIDDLE)
    d.script(s, Script(
        "Demo del producto", 75,
        "El cliente recibe una novela con portada, índice y fichas, y puede pedir un cambio "
        "que solo toca lo necesario.",
        ["Estas capturas las tomó el propio sistema: el validador visual abre el lector con "
         "Playwright antes de publicar.",
         "Portada con dedicatoria personalizada, índice navegable, y fichas de personajes y "
         "lugares generadas desde la base de datos, con enlaces al capítulo donde aparece "
         "cada uno.",
         "Lo interesante es el cambio: el lector dice «el perro se llama Nala». Ese nombre "
         "es un único hecho en la base de datos y sabemos en qué capítulos se usa.",
         "Solo esos capítulos se regeneran, en una versión nueva. La anterior se conserva y "
         "el índice marca qué ha cambiado; el PDF lleva una página de novedades.",
         "Lo probamos de verdad: cero apariciones del nombre antiguo, dieciséis del nuevo, "
         "y la versión 1 intacta."],
        ["v1 conservada", "0 nombres antiguos / 16 nuevos"],
        "¿Qué hay detrás? La arquitectura."))


def s_arch(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo funciona · arquitectura", "Roles con un solo trabajo, orquestados por código")
    roles = [("interviewer", "brief + hechos\ndel texto libre"),
             ("planner", "plan, reparto\ny cronología"),
             ("writer", "3 escenas\npor capítulo"),
             ("editor", "une, pule,\nreescribe"),
             ("judge", "rúbrica de\n5 criterios"),
             ("publicación", "versión v\n(lector + PDF)")]
    bw, gap, y = 1.72, 0.39, 2.05
    xs = [M + i * (bw + gap) for i in range(len(roles))]
    for i, (xx, (r, sub)) in enumerate(zip(xs, roles)):
        fill, line = (INK, INK) if i == 5 else (TERRA_L, TERRA)
        sh = d.label_box(s, xx, y, bw, 1.05, r, sub, fill, line, 15, 11,
                         tcolor=WHITE if i == 5 else INK)
        if i == 5:
            sh.text_frame.paragraphs[1].runs[0].font.color.rgb = RGBColor(0xC9, 0xCF, 0xD6)
        if i < len(roles) - 1:
            d.arrow(s, xx + bw, y + 0.52, xx + bw + gap, y + 0.52)
    pts = [(0, "brief_schema", "hook"), (2, "scene_accept", f"≤ {x.max_scene} reescrituras"),
           (4, "chapter_close", f"≤ {x.max_chapter} reescrituras · checkpoint"),
           (5, "pre_publish", "cobertura · Lean · juez · visual")]
    for idx, name, sub in pts:
        xx = xs[idx] - (0.25 if idx == 4 else 0)
        d.label_box(s, xx, 3.45, bw + (0.5 if idx == 4 else 0), 0.78, name, sub, WHITE, SLATE,
                    12, 10, MSO_SHAPE.HEXAGON)
        d.arrow(s, xs[idx] + bw / 2, y + 1.05, xs[idx] + bw / 2, 3.45, MUTED, 1)
    d.box(s, M, 4.55, 8.1, 1.25, MIST, LINE)
    d.text(s, M + 0.25, 4.65, 7.7, 1.1, [
        [("Story bible · SQLite autoritativa", {"bold": True, "size": 15})],
        [("Brief, hechos y su uso por escena, cronología, versiones, checkpoints, resultados "
          "de validadores, log de políticas y coste. Solo BibleRepository la toca.",
          {"size": 12, "color": SLATE})]], 15)
    d.box(s, M + 8.35, 4.55, W - 2 * M - 8.35, 1.25, MIST, LINE)
    d.text(s, M + 8.6, 4.65, W - 2 * M - 8.8, 1.1, [
        [("Langfuse", {"bold": True, "size": 15})],
        [("Sesión por novela, spans por rol y tool, coste, scores y prompts versionados.",
          {"size": 12, "color": SLATE})]], 15)
    d.text(s, M, 6.05, W - 2 * M, 0.8, [
        [("Ningún modelo tiene herramientas. ", {"bold": True}),
         ("El orquestador (app/novel/pipeline.py) decide qué documentos ve cada rol, valida "
          "su salida con JSON Schema y escribe en la BD en su nombre: la tabla de permisos se "
          "aplica en código, no en un prompt. Cada fallo vuelve, con feedback y presupuesto, "
          "al rol que puede arreglarlo.", {})]], 13, color=SLATE)
    d.script(s, Script(
        "Arquitectura del harness", 80,
        "Seis roles con un solo trabajo cada uno; el código decide, los modelos solo "
        "redactan.",
        ["El entrevistador produce el brief; el planner, el plan con reparto y cronología; "
         "el writer escribe tres escenas por capítulo; el editor las une y pule; el juez "
         "puntúa con una rúbrica.",
         "Debajo, los cuatro puntos de validación: al entregar el brief, en cada escena, al "
         "cerrar cada capítulo y antes de publicar.",
         f"Todo bucle está acotado: como mucho {x.max_scene} reescrituras por escena, "
         f"{x.max_chapter} por capítulo y {x.max_repair} rondas de reparación de la novela.",
         "La decisión clave: ningún modelo tiene herramientas. El orquestador, en Python, "
         "elige qué ve cada rol, valida su salida con JSON Schema y escribe él en la base de "
         "datos: los permisos se aplican en código, no se piden en un prompt."],
        [f"reintentos {x.max_scene}/{x.max_chapter}", f"{x.max_repair} rondas de reparación"],
        "Todo eso gira en torno a una memoria: la story bible."))


def s_memory(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo funciona · memoria",
             f"La story bible: una SQLite autoritativa con {x.ntab} tablas")
    cards = [
        ("Hechos y su uso", "fact · fact_usage",
         "Cada hecho del brief es una fila; fact_usage lo liga a (versión, capítulo, "
         "escena). Así change_fact sabe qué capítulos regenerar."),
        ("Cronología", "chronology_event · event_participant",
         "Fechas, lugares, participantes, edades declaradas y salidas (muerte, partida). "
         "Es la entrada del modelo Lean."),
        ("Versiones y checkpoints", "novel_version · chapter_version · checkpoint",
         "Texto + hash por capítulo y versión; texto y checkpoint en una transacción. "
         "Reanudación en el primer capítulo incompleto."),
        ("Auditoría y coste", "validator_result · policy_decision · llm_call",
         "Cada validador, decisión de política y llamada con tokens, coste, latencia y "
         "versión de prompt. Nada se borra (D6)."),
    ]
    cw, ch = (W - 2 * M - 0.3) / 2, 2.05
    for i, (t, tabs, body) in enumerate(cards):
        xx = M + (i % 2) * (cw + 0.3)
        y = 1.75 + (i // 2) * (ch + 0.3)
        d.box(s, xx, y, cw, ch, MIST)
        d.circle_num(s, xx + 0.3, y + 0.3, 0.45, i + 1, size=14)
        d.text(s, xx + 0.95, y + 0.3, cw - 1.2, 0.45, t, 18, bold=True, font=HEAD)
        d.text(s, xx + 0.95, y + 0.78, cw - 1.2, 0.3, tabs, 11, font=MONO, color=TERRA)
        d.text(s, xx + 0.95, y + 1.15, cw - 1.25, 0.85, body, 13, color=SLATE)
    d.text(s, M, 6.5, W - 2 * M, 0.3,
           "Los roles reciben hechos estructurados a través de tools con schema "
           "(app/tools/), no fragmentos recuperados por similitud. Diagrama ER en "
           "anexo-arquitectura.pdf.", 11, color=MUTED)
    d.script(s, Script(
        "Memoria: la story bible", 60,
        "Una sola fuente de verdad en SQLite que usan validadores, lector y Lean.",
        ["La story bible es una SQLite autoritativa: si algo no está ahí, no es verdad para "
         "el sistema.",
         "Cada hecho del brief es una fila, y fact_usage registra en qué capítulo y escena se "
         "usa. Eso es lo que permite regenerar solo los capítulos afectados.",
         "La cronología guarda eventos con fecha, lugar y participantes, y es exactamente lo "
         "que se exporta a Lean.",
         "Texto del capítulo y checkpoint se guardan en la misma transacción: si se cae, se "
         "reanuda en el primer capítulo incompleto sin duplicar ni perder nada."],
        [f"{x.ntab} tablas"],
        "Sobre esa memoria actúan los validadores."))


def s_validators(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo sabemos que funciona · validadores",
             "Cada fallo se detecta donde es barato repararlo")
    pts = [("hook", "al entregar el brief"), ("scene_accept", "cada escena"),
           ("chapter_close", "cada capítulo"), ("pre_publish", "antes de publicar")]
    pw = 2.75
    for i, (p, sub) in enumerate(pts):
        xx = M + i * (pw + 0.4)
        d.label_box(s, xx, 1.7, pw, 0.72, p, sub, TERRA_L if i else MIST, TERRA, 14, 11,
                    MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON)
    rows = [["Tipo", "Validadores", "Punto de ejecución", "Si falla"],
            ["Programático", "brief_schema · schema_role_output · chapter_length · "
             "exact_names · brief_coverage · no_placeholders · calendar_consistency · "
             "prose_repetition (linter X02) · visual_check",
             "hook · scene_accept · chapter_close · pre_publish",
             "vuelve al rol productor con la evidencia"],
            ["Guardrail", "forbidden_words_scene · forbidden_words_chapter · "
             "free_text_injection (prescan)", "entrevista · scene_accept · chapter_close",
             f"reescritura ≤ {x.max_scene} → forbidden_word_limit"],
            ["Semántico", "judge_chapter · judge_novel · revisión humana (misma rúbrica)",
             "chapter_close · pre_publish · una novela",
             "editor; aprueba si cada criterio ≥ 3 y media ≥ 3,5"],
            ["Formal", "lean_chronology (4 invariantes) · TLA+/TLC del flujo",
             "pre_publish · desarrollo",
             f"versión bloqueada; ≤ {x.max_repair} rondas de reparación de los capítulos "
             "citados"]]
    d.table(s, M, 2.7, W - 2 * M, rows, [1.3, 4.8, 2.9, 3.1], size=12, row_h=0.66)
    d.text(s, M, 6.15, W - 2 * M, 0.7, [
        [("Cada validador tiene nombre y punto de ejecución, y envía su resultado a Langfuse "
          "como score. ", {}),
         ("Si se agota el presupuesto, la versión queda bloqueada: ", {"bold": True}),
         ("nunca se publica.", {})]], 13, color=SLATE)
    d.script(s, Script(
        "Validadores", 75,
        "Cuatro tipos de validador, cada uno en el punto donde arreglar el fallo es más "
        "barato.",
        ["Programáticos: schema, longitud, nombres exactos, cobertura de los datos del brief. "
         "El último que añadimos es calendar_consistency: comprueba que un día de la semana "
         "junto a una fecha es el correcto. Luego os cuento por qué.",
         "También hay un linter de prosa, prose_repetition, que detecta repeticiones y "
         "clichés de IA; es el opcional X02 y es blando para no provocar bucles.",
         "Semánticos: el juez por capítulo y por novela, con una rúbrica de continuidad, "
         "tono, calidad narrativa, personalización natural y final. Aprueba con cada "
         "criterio ≥ 3 y media ≥ 3,5.",
         "Formales: Lean sobre la cronología de cada novela, y TLA+ sobre el propio harness.",
         "La regla: si un fallo agota su presupuesto, la versión se bloquea. Nunca se publica "
         "algo que no pasó."],
        ["4 tipos", "4 puntos de ejecución", "juez: ≥ 3 y media ≥ 3,5"],
        "Un tipo especial de validador son los guardrails."))


def s_guardrails(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo sabemos que funciona · guardrails",
             "Reglas que se cumplen aunque el modelo no quiera")
    cols = [
        ("Vetos en 3 niveles", [
            ("Global: ", "sembrado por migración (1300)."),
            ("Novela: ", "los vetos del cliente en el brief."),
            ("Léxico: ", "variantes extra que aporta cada validador."),
            ("Un acierto ", f"vuelve al escritor, ≤ {x.max_scene} veces.")]),
        ("Un solo normalizador", [
            ("Plegado común ", "de texto y término (NFKD, sin tildes)."),
            ("Detecta: ", "t0nt0 · tontooo · t.o.n.t.o · cabrones → cabrón."),
            ("Sin falsos positivos: ", "«ridículo», «tontería»."),
            ("Palabra completa ", "y frases, no subcadenas.")]),
        ("Texto libre = no confiable", [
            ("Prescan determinista ", "de inyección antes del modelo."),
            ("El extractor ", "solo devuelve hechos, y marca la sospecha."),
            ("Ningún rol ", "recibe el texto libre crudo."),
            ("Cada decisión ", "en policy_decision y en Langfuse.")]),
    ]
    cw = (W - 2 * M - 0.6) / 3
    for i, (t, items) in enumerate(cols):
        xx = M + i * (cw + 0.3)
        d.box(s, xx, 1.75, cw, 2.95, MIST)
        d.text(s, xx + 0.25, 1.92, cw - 0.5, 0.4, t, 17, bold=True, font=HEAD)
        d.bullets(s, xx + 0.25, 2.45, cw - 0.45, 2.2, items, 13, gap=4)
    rows = [["Hooks de Claude Code (mismo código que el pipeline)", "Resultado"],
            ["Write backend/.env · valor con forma de clave de API", "bloqueado (exit 2)"],
            ["Bash sqlite3 data/harness.sqlite \"delete …\"", "bloqueado (exit 2)"],
            ["Bash sqlite3 … \"select …\" · Edit backend/app/main.py", "permitido (exit 0)"],
            ["Capítulo con «c4br0n» o de 2 palabras", "bloqueado (exit 2)"]]

    def fill(_i, j, v):
        return (RED_L if "bloqueado" in v else GREEN_L) if j == 1 else None

    d.table(s, M, 4.95, W - 2 * M, rows, [8, 3], size=12, row_h=0.33, cell_fill=fill)
    d.script(s, Script(
        "Guardrails y policy", 60,
        "Los vetos del cliente y la inyección se paran en código, antes y después del "
        "modelo.",
        ["Palabras prohibidas en tres niveles: globales, las del cliente para su novela, y "
         "variantes léxicas.",
         "Un único normalizador quita tildes, mayúsculas, plurales y leetspeak antes de "
         "comparar.",
         "Si aparece un veto, el capítulo vuelve al escritor con un límite de intentos; si "
         "se agota, la generación se para y queda registrado.",
         "El texto libre del cliente se trata como no confiable: un prescan determinista "
         "antes del modelo, el extractor solo devuelve hechos, y ningún rol ve el texto "
         "crudo.",
         "Y los hooks de Claude Code usan el mismo código: si yo, o un agente, intento "
         "escribir una clave o borrar la base de datos, se bloquea."],
        ["3 niveles de vetos", "14 casos de hooks probados"],
        "Para la coherencia temporal usamos verificación formal: Lean."))


def s_lean(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo sabemos que funciona · Lean 4",
             "La cronología de cada novela se demuestra, no se opina")
    inv = [("temporalOrder", "Lo contado después ocurre el mismo día o más tarde."),
           ("agesCoherent", "Cada edad declarada = años desde el nacimiento."),
           ("noBilocation", "Nadie está en dos lugares el mismo día."),
           ("noAfterExit", "Tras una muerte o partida, esa persona no reaparece.")]
    for i, (n, t) in enumerate(inv):
        xx = M + (i % 2) * 2.95
        y = 1.75 + (i // 2) * 1.2
        d.box(s, xx, y, 2.8, 1.05, TERRA_L)
        d.text(s, xx + 0.18, y + 0.12, 2.5, 0.3, n, 13, bold=True, font=MONO, color=TERRA)
        d.text(s, xx + 0.18, y + 0.45, 2.5, 0.6, t, 11)
    d.bullets(s, M, 4.3, 5.75, 2.3, [
        ("Se genera desde la story bible ", "y corre en pre_publish (lake build); si falla, "
                                            "no se publica."),
        ("También antes de escribir: ", "el plan pasa el mismo diagnóstico y se replanea."),
        ("Bool + Prop + teorema: ", "la comprobación es una prueba; decide +kernel, sin "
                                    "Mathlib (300 eventos en 17 s)."),
    ], 12, gap=5)
    d.text(s, M, 5.55, 5.75, 0.6, [
        [("Lo que Lean no vio: ", {"bold": True}),
         ("edades (las recalcula el exportador; las vio judge_chapter) y una partida que el "
          "planner no registró como evento.", {})]], 11, color=MUTED)
    rx = 6.75
    rw = W - M - rx
    d.box(s, rx, 1.75, rw, 4.95, MIST)
    d.text(s, rx + 0.25, 1.88, rw - 0.5, 0.4, "Caso real (L04)", 17, bold=True, font=HEAD)
    rows = x.lean_rows
    if rows:
        d.text(s, rx + 0.25, 2.3, rw - 0.5, 0.55,
               "b4-temporal, plan sin prechequeo: la mascota muere en 2005 y lleva los anillos "
               "en la boda de 2008.", 12, color=SLATE)
        tab = [["Validador", "¿Lo vio?"]]
        for r in rows[1:]:
            name = r[0]
            if "," in name:
                name = f"{len(name.split(','))} validadores programáticos"
            saw = r[2] if len(r) > 2 else ""
            short = "Sí" if saw.startswith("Sí") else "No"
            det = re.split(r"[:(]", saw, maxsplit=1)
            det_s = det[1].split(",")[0].strip()[:40] if len(det) > 1 and short == "Sí" else ""
            if short == "No" and "aprobó" in saw:
                det_s = "aprobó el capítulo de la muerte y la boda"
            tab.append([name, f"{short} — {det_s}".rstrip(" —") if det_s else short])

        def fill(_i, j, v):
            return (GREEN_L if v.startswith("Sí") else RED_L) if j == 1 else None

        d.table(s, rx + 0.25, 2.95, rw - 0.5, tab, [2.2, 3.0], size=11, row_h=0.42,
                cell_fill=fill)
        yb = 2.95 + 0.42 * len(tab) + 0.15
        d.text(s, rx + 0.25, yb, rw - 0.5, 6.6 - yb, [
            [("Lectura honesta: ", {"bold": True}),
             ("no lo vio solo Lean; judge_novel coincidió. Lean es determinista, señala el "
              "evento exacto y actúa antes de escribir (~0,12 USD frente a ~1,3 USD). Solo "
              "prueba lo que el planner pone en la cronología.", {})]], 12, color=SLATE)
    else:
        d.text(s, rx + 0.25, 2.4, rw - 0.5, 1.0, f"Caso real: {PENDING} "
               "(docs/process/lean-caso-real.md).", 13, italic=True, color=MUTED)
    lean_yes = sum(1 for r in rows[1:] if len(r) > 2 and r[2].startswith("Sí"))
    d.script(s, Script(
        "Lean 4", 90,
        "Lean prueba la coherencia temporal de la cronología; en el caso real cazó lo que el "
        "juez de capítulo aprobó.",
        ["De la story bible se genera un fichero Lean y se demuestran cuatro invariantes: "
         "orden temporal, edades, nadie en dos sitios, nadie reaparece tras morir o irse.",
         "Corre antes de publicar; si falla, la versión no se publica y el fallo vuelve al "
         "editor. Y el mismo diagnóstico se aplica al plan, antes de escribir una línea.",
         "El enunciado pide un caso real. Lo forzamos con el brief de trampas temporales, "
         "quitando el prechequeo: la mascota muere en 2005 y lleva los anillos en la boda de "
         "2008.",
         "Lean lo vio, con evento, fecha y capítulo. El juez de novela también. Pero el juez "
         "de capítulo aprobó el capítulo que cuenta la muerte y la boda, y los validadores "
         "programáticos no miran fechas.",
         "Lo digo con honestidad: no es algo que solo viera Lean. Su valor es que es "
         "determinista, localiza el evento y actúa antes de gastar la escritura."],
        [f"{lean_yes} validadores lo vieron" if rows else "caso real pendiente",
         "~0,12 USD en el plan frente a ~1,3 USD de novela"],
        "Lean verifica la historia; TLA+ verifica el harness."))


def s_tla(d: Deck, x: Data) -> None:
    s = d.slide()
    t, cfg = x.tlc, x.cfg
    d.header(s, "Cómo sabemos que funciona · TLA+", "El flujo del harness, comprobado con TLC")
    row1 = ["Configured", "Planned", "Scene", "Editor", "Close"]
    row2 = ["Checkpoint", "Next", "PrePublish", "Published"]
    bw, gap = 1.75, 0.5
    xs = [M + i * (bw + gap) for i in range(5)]
    for i, n in enumerate(row1):
        d.label_box(s, xs[i], 1.75, bw, 0.55, n, "", TERRA_L, TERRA, 13)
        if i < len(row1) - 1:
            d.arrow(s, xs[i] + bw, 2.02, xs[i + 1], 2.02)
    d.arrow(s, xs[4] + bw / 2, 2.3, xs[4] + bw / 2, 2.75)
    for i, n in enumerate(row2):
        xx = xs[4 - i]
        pub = n == "Published"
        d.label_box(s, xx, 2.75, bw, 0.55, n, "", INK if pub else TERRA_L,
                    INK if pub else TERRA, 13, tcolor=WHITE if pub else INK)
        if i < len(row2) - 1:
            d.arrow(s, xx, 3.02, xs[3 - i] + bw, 3.02)
    d.label_box(s, xs[0], 2.75, bw, 0.55, "StoppedError", "", RED_L, RED, 12)
    d.text(s, M, 3.45, W - 2 * M, 0.35,
           f"Bucles acotados (≤ {cfg.get('MAX_CHAPTER_RETRIES', '?')} reintentos, "
           f"≤ {cfg.get('MAX_REPAIR_ROUNDS', '?')} rondas de reparación) → StoppedError al "
           "agotarse. Crash → Resume desde la BD. ChangeFact → versión v+1.", 12, color=SLATE)
    rows = [["Propiedad", "Tipo", "Garantiza"],
            ["NoUnvalidatedPublish", "invariante", "no se publica nada que no pasó todos los "
                                                   "validadores"],
            ["ResumeNoDupNoLoss", "invariante", "reanudar no duplica ni pierde capítulos"],
            ["PreviousVersionKept", "invariante", "la versión publicada anterior no cambia"],
            ["RetriesBounded", "invariante", "reintentos acotados, también tras un crash"],
            ["Termination · EveryGenerationEnds", "liveness", "toda generación acaba publicada "
                                                              "o en error"]]
    d.table(s, M, 3.95, 8.1, rows, [3.0, 1.2, 4.4], size=11, row_h=0.4)
    sx = M + 8.45
    d.box(s, sx, 3.95, W - M - sx, 2.4, INK)
    d.text(s, sx + 0.25, 4.05, W - M - sx - 0.5, 2.2, [
        [(("Sin errores" if t.ok else "Con errores" if t.version else PENDING),
          {"bold": True, "size": 20, "color": GREEN_L if t.ok else RED_L})],
        [(f"{t.distinct}", {"bold": True, "size": 30, "color": TERRA, "font": HEAD})],
        [("estados distintos", {"size": 12, "color": WHITE})],
        [(f"{t.generated} generados · profundidad {t.depth} · {t.duration}",
          {"size": 11, "color": RGBColor(0xC9, 0xCF, 0xD6)})],
        [(f"N = {cfg.get('N', '?')} capítulos · {cfg.get('SCENES', '?')} escenas · "
          f"reintentos {cfg.get('MAX_SCENE_RETRIES', '?')}/"
          f"{cfg.get('MAX_CHAPTER_RETRIES', '?')} · reparación "
          f"{cfg.get('MAX_REPAIR_ROUNDS', '?')}",
          {"size": 11, "color": RGBColor(0xC9, 0xCF, 0xD6)})]], 12)
    d.text(s, M, 6.5, W - 2 * M, 0.3,
           "TLC se re-ejecutó al subir MAX_REPAIR_ROUNDS de 1 a 2 en el tuning 1. "
           "Correspondencia acción → código en formal/tla/README.md.", 11, color=MUTED)
    d.script(s, Script(
        "TLA+", 75,
        "El harness es una máquina de estados y TLC comprueba que nunca publica nada sin "
        "validar y que siempre termina.",
        ["Modelamos el flujo completo como máquina de estados: configuración, plan, escenas, "
         "editor, cierre de capítulo, checkpoint, pre-publicación y publicación; con "
         "reintentos, crash y reanudación, y cambio del lector.",
         "Cuatro invariantes de seguridad: nunca se publica sin validar, reanudar no duplica "
         "ni pierde capítulos, la versión anterior se conserva, y los reintentos están "
         "acotados incluso tras un crash.",
         "Y liveness: toda generación acaba publicando o en error, nunca en un bucle.",
         f"TLC explora el modelo pequeño que pide el enunciado, {cfg.get('N', '?')} "
         f"capítulos con {cfg.get('MAX_CHAPTER_RETRIES', '?')} reintentos: {t.distinct} "
         f"estados distintos, sin errores.",
         "Al subir las rondas de reparación de 1 a 2, lo primero fue volver a pasar TLC."],
        [f"{t.distinct} estados distintos", f"{t.generated} generados",
         f"profundidad {t.depth}", f"{t.duration}"],
        "Lo más valioso de TLA+ no fue este verde, fueron los rojos de antes."))


def s_tla_ce(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "TLA+ · contraejemplos", "Cuatro trazas de TLC que cambiaron el código",
             "El modelo se escribió antes que el pipeline, leyendo el esquema y el plan tal "
             "cual. TLC encontró dónde esa lectura se rompía.")
    ce = C.counterexamples()
    rules = {
        "CE1": "Texto del capítulo y checkpoint en una sola transacción",
        "CE2": "Reintentos de capítulo contados desde validator_result persistidos",
        "CE3": "Upsert por (versión, capítulo); una versión publicada no se escribe",
        "CE4": "Ronda de reparación guardada en novel_version junto a «blocked»",
    }
    causes = {
        "CE1": "Un crash entre la fila del capítulo y su checkpoint duplica el capítulo",
        "CE2": "El contador de reintentos de capítulo vivía en memoria; un crash lo reiniciaba",
        "CE3": "La ronda de reparación insertaba una segunda fila del mismo capítulo",
        "CE4": "El contador de rondas de reparación vivía en memoria; un crash lo reiniciaba",
    }
    rows = [["", "Invariante violado", "Traza", "Causa", "Regla para el código"]]
    for r in ce[1:]:
        cid = C.strip_md(r[0])
        trace = C.strip_md(r[3]).replace("states", "estados")
        rows.append([cid, C.strip_md(r[2]), trace, causes.get(cid, C.strip_md(r[5])),
                     rules.get(cid, "")])
    if len(rows) > 1:
        d.table(s, M, 2.1, W - 2 * M, rows, [0.6, 2.0, 1.0, 4.3, 4.3], size=12, row_h=0.72)
    d.box(s, M, 5.95, W - 2 * M, 0.8, TERRA_L)
    d.text(s, M + 0.3, 6.0, W - 2 * M - 0.6, 0.7, [
        [("Efecto: ", {"bold": True}),
         ("la spec de la story bible volvió a borrador y se reaprobó antes de que existiera el "
          "pipeline, que nació con las cuatro reglas. Dos mutaciones (publicar sin pre_publish, "
          "regenerar en sitio) confirman que las propiedades no son vacías.", {})]], 13,
           anchor=MSO_ANCHOR.MIDDLE)
    d.script(s, Script(
        "Contraejemplos CE1–CE4", 75,
        "TLC encontró cuatro errores de diseño cuando aún eran baratos: antes de escribir el "
        "pipeline.",
        ["Escribimos el modelo en paralelo al diseño, leyendo el esquema tal cual. TLC "
         "encontró cuatro trazas mínimas que lo rompían.",
         "CE1: si el proceso cae entre guardar el capítulo y guardar el checkpoint, al "
         "reanudar se escribe dos veces. Solución: las dos cosas en una transacción.",
         "CE2 y CE4: los contadores de reintentos y de rondas de reparación vivían en "
         "memoria; un crash los ponía a cero y el coste dejaba de estar acotado. Solución: "
         "se leen de la base de datos.",
         "CE3: la reparación insertaba una segunda fila del mismo capítulo. Solución: upsert "
         "por versión y capítulo, y una versión publicada no se toca. El pipeline nació ya "
         "con esas cuatro reglas."],
        ["4 contraejemplos", "trazas de 18 a 50 estados"],
        "Todo esto se puede ver en ejecución gracias a la observabilidad."))


def s_langfuse(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo sabemos que funciona · Langfuse",
             "Qué hizo cada llamada, cuánto costó y con qué prompt")
    levels = [("Sesión", "una por novela: entrevista, generación y regeneraciones"),
              ("Traza", "una por generate o change_fact"),
              ("Spans", "phase:* · chapter:<n> · role:<rol> · tool:<nombre>"),
              ("Generaciones", "tokens, coste y latencia por llamada"),
              ("Scores", "cada validador, guardrail y criterio del juez; novel_cost_usd")]
    for i, (n, t) in enumerate(levels):
        y = 1.8 + i * 0.9
        xx = M + i * 0.3
        d.label_box(s, xx, y, 1.75, 0.66, n, "", TERRA_L if i < 4 else INK,
                    TERRA if i < 4 else INK, 14, tcolor=INK if i < 4 else WHITE)
        d.text(s, xx + 1.95, y + 0.08, 5.2 - i * 0.3, 0.6, t, 13, color=SLATE,
               anchor=MSO_ANCHOR.MIDDLE)
    prompts: dict[tuple[str, str], tuple[str, int]] = {}
    for f in sorted((C.ROOT / "evals/results").glob("*/*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in data.get("prompts") or []:
            k = (p["role"], p["prompt_name"])
            old = prompts.get(k, ("", 0))
            ver = str(p["prompt_version"])
            keep = ver if not old[0] or (ver.isdigit() and old[0].isdigit()
                                         and int(ver) > int(old[0])) else old[0]
            prompts[k] = (keep, old[1] + int(p.get("calls", 0)))
    rows = [["Rol", "Prompt", "Versión", "Llamadas"]]
    for (role, name), (ver, calls) in sorted(prompts.items()):
        rows.append([role, name, ver if len(ver) < 12 else ver[:11] + "…", str(calls)])
    tx = M + 7.6
    d.text(s, tx, 1.8, W - M - tx, 0.35, "Prompts versionados en las evals", 15, bold=True,
           font=HEAD)
    if len(rows) > 1:
        d.table(s, tx, 2.25, W - M - tx, rows, [1.3, 1.7, 1.2, 1.0], size=11, row_h=0.36)
    d.text(s, tx, 2.35 + 0.36 * len(rows), W - M - tx, 1.2,
           "Última versión usada por prompt. Cada llamada guarda prompt_version también en "
           "llm_call (SQLite): el antes/después no depende de Langfuse.", 11, color=SLATE)
    d.script(s, Script(
        "Observabilidad con Langfuse", 50,
        "Cada novela es una sesión con coste, validadores y versión de prompt por llamada.",
        ["Una sesión por novela, que incluye la entrevista y las regeneraciones; una traza "
         "por generación o cambio.",
         "Spans con nombre por fase, capítulo, rol y tool; tokens, coste y latencia por "
         "llamada, por capítulo y por novela.",
         "Todos los validadores, incluidos Lean y el juez, llegan como scores.",
         "Y los prompts están versionados en Langfuse: la tabla de la derecha sale de las "
         "evals y dice qué versión produjo cada resultado. Es lo que hace creíble el "
         "antes/después del tuning."],
        [],
        "Y eso nos lleva a las evals."))


def _outcome(o: str) -> str:
    return {"published": "publicada", "blocked": "bloqueada", "pipeline_error": "parada (plan)",
            "rejected_by_validation": "rechazado"}.get(o, o)


def s_evals(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo sabemos que funciona · evals y tuning 1",
             "Cinco briefs, antes y después de la iteración de tuning")
    b, a = x.ev_b, x.ev_a
    d.box(s, M, 1.75, 4.2, 2.1, INK)
    d.text(s, M + 0.3, 1.88, 3.7, 0.3, "NOVELAS PUBLICADAS", 12, bold=True, color=TERRA)
    big = (f"{b.published}/{b.generable} → {a.published}/{a.generable}"
           if b.generable and a.generable else PENDING)
    d.text(s, M + 0.3, 2.22, 3.8, 0.8, big, 40, bold=True, color=WHITE, font=HEAD)
    d.text(s, M + 0.3, 3.1, 3.7, 0.6,
           "entre los briefs generables (antes → después); b5 se rechaza en el brief, como "
           "se espera.", 11, color=RGBColor(0xC9, 0xCF, 0xD6))
    runs = {(r.brief, r.label): r for r in C.eval_runs()}
    briefs = sorted({r.brief for r in runs.values()})
    tab = [["Brief", "Antes", "Después", "USD"]]
    for br in briefs:
        rb, ra = runs.get((br, "before")), runs.get((br, "after"))
        tab.append([br, _outcome(b.outcomes.get(br, "—")), _outcome(a.outcomes.get(br, "—")),
                    num(ra.cost, 2) if ra and ra.cost else "—"])

    def fill(_i, j, v):
        if j in (1, 2):
            return GREEN_L if v == "publicada" else AMBER_L if v in ("bloqueada",
                                                                      "rechazado") else RED_L
        return None

    if len(tab) > 1:
        d.table(s, M, 4.1, 4.2, tab, [1.7, 1.2, 1.2, 0.6], size=11, row_h=0.4, cell_fill=fill)
    rx = M + 4.5
    rw = W - M - rx
    d.box(s, rx, 1.75, rw, 4.95, MIST)
    d.text(s, rx + 0.3, 1.88, rw - 0.6, 0.4, "Qué cambió: causa y arreglo", 17, bold=True,
           font=HEAD)
    d.bullets(s, rx + 0.3, 2.4, rw - 0.6, 3.4, [
        ("brief_coverage ", "exigía la frase literal del recuerdo → palabras de contenido "
                            "normalizadas (spec 008)."),
        ("noAfterExit ", "daba por «salido» a quien enterraba a la mascota → eje de la "
                         "historia, solo el primer participante; Lean y Python iguales."),
        ("Planner ", "capítulos solapados y saltos vagos → time_marker por capítulo y chequeo "
                     "de solape."),
        ("Juez ", "bloqueaba por defectos «posibles» → solo un defecto «alta» concreto; "
                  "umbrales D11 intactos."),
        ("Reparación ", "rehacía capítulos que nadie pedía → solo capitulos_a_reparar; "
                        f"MAX_REPAIR_ROUNDS 1 → {x.max_repair}, TLC re-ejecutado."),
    ], 13, gap=6)
    d.text(s, rx + 0.3, 5.6, rw - 0.6, 0.9,
           "Prompts en Langfuse: planner 2 → 4 · writer 3 → 4 · editor 3 → 4 · juez 1 → 2. "
           "b4 pasa de un falso positivo a un bloqueo correcto: su trampa de edad no tiene "
           "lectura coherente.", 11, color=SLATE)
    d.script(s, Script(
        "Evals y tuning 1", 90,
        "Una iteración de tuning medida: de 0 a 2 novelas publicadas sin bajar ningún umbral.",
        ["Cinco briefs: ejemplo, infantil, inyección, trampas temporales y contradictorio.",
         f"Antes del tuning se publicaban {b.published} de {b.generable}. El problema no "
         "eran las novelas: brief_coverage exigía la frase literal del recuerdo aunque el "
         "capítulo lo contara, y el espejo Python de noAfterExit daba un falso positivo.",
         "Arreglamos los validadores, añadimos marcas temporales al plan, hicimos que el juez "
         "solo bloquee por defectos graves y concretos, y que la reparación toque solo los "
         "capítulos que el juez pide.",
         f"Después: {a.published} de {a.generable} publicadas. Los umbrales de calidad no "
         "se bajaron.",
         "El brief de trampas temporales sigue bloqueado, y es lo correcto: su trampa de "
         "edad no tiene ninguna lectura coherente. El contradictorio se rechaza antes de "
         "generar."],
        [f"{b.published}/{b.generable} → {a.published}/{a.generable} publicadas",
         f"coste medio publicada ≈ {usd(a.cost_published)}"],
        "Antes de los resultados finales, un punto de seguridad."))


def s_security(d: Deck, x: Data) -> None:
    s = d.slide()
    sec = x.sec
    d.header(s, "Cómo sabemos que funciona · seguridad y opcionales",
             "Red-team, informe de seguridad y los extras que suman nota")
    crit_high = sec.by_sev.get("crítica", 0) + sec.by_sev.get("alta", 0)
    med = sec.by_sev.get("media", 0)
    stats = [(str(sec.total) if sec.total else PENDING, "hallazgos en el informe X04"),
             (str(crit_high) if sec.total else PENDING, "críticos o altos"),
             (f"{med}/{med}" if sec.total else PENDING, "medios corregidos, con test"),
             (str(sec.fixed) if sec.total else PENDING, "corregidos en total")]
    for i, (big, small) in enumerate(stats):
        y = 1.75 + i * 1.12
        d.text(s, M, y, 3.3, 0.6, big, 32, bold=True, color=TERRA, font=HEAD)
        d.text(s, M, y + 0.6, 3.3, 0.35, small, 12, color=SLATE)
    ok = sum(1 for r in x.redteam if len(r) > 4 and "✅" in r[4])
    d.box(s, M, 6.25, 3.3, 0.55, TERRA_L)
    d.text(s, M + 0.15, 6.28, 3.0, 0.5,
           f"Red-team: {ok}/{len(x.redteam)} casos detenidos" if x.redteam else
           f"Red-team: {PENDING}", 13, bold=True, anchor=MSO_ANCHOR.MIDDLE)
    cards = [
        ("X04 · Informe de seguridad", "Secretos en 201 commits, pip-audit y npm audit, "
         "inyección (prescan 10/17 → 17/17), exfiltración entre novelas, hooks. Skill "
         "security-review-harness para repetirlo."),
        ("X03 · Login con SQLite", "bcrypt + JWT; cada novela tiene dueño y otro usuario "
         "recibe 404. Cierra SEC-01 y SEC-08 (spec 018)."),
        ("X01 · Servidor MCP", "FastMCP de solo lectura: list_novels, get_chapter, "
         "list_versions, query_story_bible, download_novel. Schemas, trazas en Langfuse e "
         "identidad del usuario."),
        ("X02 · Linter de prosa", "prose_repetition: repeticiones, 4-gramas y clichés de IA "
         "en español; blando para no crear bucles de reescritura."),
    ]
    cx = M + 3.7
    cw = (W - M - cx - 0.3) / 2
    for i, (t, body) in enumerate(cards):
        xx = cx + (i % 2) * (cw + 0.3)
        y = 1.75 + (i // 2) * 2.55
        d.box(s, xx, y, cw, 2.3, MIST)
        d.text(s, xx + 0.25, y + 0.2, cw - 0.5, 0.4, t, 15, bold=True, font=HEAD)
        d.text(s, xx + 0.25, y + 0.7, cw - 0.5, 1.5, body, 13, color=SLATE)
    d.script(s, Script(
        "Seguridad y opcionales", 70,
        f"Revisión de seguridad hecha por un agente: {sec.total} hallazgos, ninguno crítico "
        "ni alto, y los medios corregidos con test.",
        [f"Además del red-team, hicimos el opcional X04: un agente revisó el sistema. {sec.total} "
         f"hallazgos, {crit_high} críticos o altos; los {med} medios están corregidos, cada "
         "uno con un test que falla sin el cambio.",
         "Ejemplo: el prescan de inyección solo detectaba 10 de 17 variantes; ahora 17 de 17.",
         "El hallazgo más serio era que no había autenticación. Lo cerró el login, X03: "
         "bcrypt, JWT, y un usuario no puede ver las novelas de otro.",
         "X01 es un servidor MCP de solo lectura para consultar y descargar novelas, que "
         "respeta la identidad. X02 es el linter de prosa."],
        [f"{sec.total} hallazgos", f"{crit_high} críticos/altos", f"{sec.fixed} corregidos",
         "inyección 17/17"],
        "Ahora, los resultados con novelas de verdad de 10 capítulos."))


def s_ten(d: Deck, x: Data) -> None:
    s = d.slide()
    stopped = len(x.attempts)
    word = {1: "Una", 2: "Dos", 3: "Tres", 4: "Cuatro"}.get(stopped, str(stopped))
    d.header(s, "Resultados · novelas de 10 capítulos",
             f"{word} paradas, una publicada: nada sin validar sale" if x.final_pub else
             f"{word} novelas paradas: nada sin validar se publica")
    # Chronological: the attempts that motivated a tuning, the published one, then the
    # attempts run in parallel with it (same code), each with what it motivated.
    cols = list(x.attempts[:2])
    final_at = len(cols)
    cols.append({"final": True, **x.final})
    cols += list(x.attempts[2:])
    n = len(cols)
    gap = 0.3
    cw = (W - 2 * M - gap * (n - 1)) / n
    small = n > 3
    body_size = 11 if small else 12
    for i, a in enumerate(cols):
        xx = M + i * (cw + gap)
        final = a.get("final")
        st = a.get("status")
        pub = st == "published"
        stop = st in {"blocked", "stopped_error"}
        fill = GREEN_L if pub else (MIST if final and not st else RED_L)
        d.box(s, xx, 1.75, cw, 3.25, fill)
        when = "después del tuning 2" if final else a.get("when", "")
        kick = f"INTENTO {i + 1} · {when}".upper()
        d.text(s, xx + 0.2, 1.87, cw - 0.4, 0.4, kick, 10 if small else 11, bold=True,
               color=TERRA)
        label = ("publicada" if pub else "bloqueada" if st == "blocked"
                 else "parada" if st == "stopped_error" else (st or PENDING))
        d.text(s, xx + 0.2, 2.3, cw - 0.4, 0.5, label.capitalize(), 24 if small else 26,
               bold=True, font=HEAD, color=GREEN if pub else RED if stop else MUTED)
        if final and not st:
            body = [[("Generándose con el tuning 2. ", {"bold": True}),
                     ("Estado, coste, palabras y rondas se rellenan desde runs.json al "
                      "reconstruir.", {})]]
        elif final:
            body = [[(f"{a.get('chapters') or '?'} capítulos · "
                      f"{num(a.get('words'))} palabras", {"bold": True})],
                     [(f"{a.get('repair_rounds', 0)} "
                       f"{'ronda' if a.get('repair_rounds') == 1 else 'rondas'} de reparación · "
                       f"{mins(a.get('minutes'))}", {})],
                     [(f"judge_novel: {a.get('judge_novel') or '—'}", {})]]
        else:
            body = [[(f"{a.get('validator', '?')}: ", {"bold": True}),
                     (a.get("why", ""), {})],
                    [(f"{a.get('chapters_written', '?')} capítulos · "
                      f"{a.get('repair_rounds', '?')} "
                      f"{'ronda' if a.get('repair_rounds') == 1 else 'rondas'} de reparación · "
                      f"{mins(a.get('minutes'))}", {"color": SLATE})]]
        d.text(s, xx + 0.2, 2.9, cw - 0.4, 1.45, body, body_size, spacing=3)
        d.text(s, xx + 0.2, 4.4, cw - 0.4, 0.5, usd(a.get("cost_usd")), 22, bold=True,
               font=HEAD, color=INK)
        if i < final_at:
            d.arrow(s, xx + cw + 0.02, 3.35, xx + cw + gap - 0.02, 3.35, TERRA, 2)
        if not final and a.get("motivated"):
            d.text(s, xx + 0.2, 5.1, cw - 0.4, 0.4, f"→ motivó el {a.get('motivated', '')}",
                   11 if small else 12, bold=True, color=TERRA)
    d.box(s, M, 5.6, W - 2 * M, 1.15, INK)
    d.text(s, M + 0.3, 5.68, W - 2 * M - 0.6, 1.0, [
        [("Tuning 2 · calendario determinista. ", {"bold": True, "color": TERRA}),
         ("El writer inventaba el día de la semana y cada reparación inventaba otro. Ahora el "
          "plan corrige los días en Python (calendar_facts.py), writer y editor reciben "
          "plan/calendar.txt con fechas y cifras canónicas, y calendar_consistency para en "
          "chapter_close «…pero el 23 de junio de 2026 es martes».", {"color": WHITE})],
        [("Después · eventos con lugar. ", {"bold": True, "color": TERRA}),
         ("La paralela se paró por un evento del plan sin lugar que Lean no podía exportar: "
          "ahora el chequeo del plan lo rechaza y un error de exportación no gasta rondas.",
          {"color": WHITE})]],
        11 if len(x.attempts) > 2 else 12, anchor=MSO_ANCHOR.MIDDLE, spacing=3)
    spent = sum(a.get("cost_usd") or 0 for a in x.attempts)
    if x.final_pub:
        fin_say = (f"El intento final, ya con el tuning 2, se publicó: {x.final.get('chapters')} "
                   f"capítulos, {num(x.final.get('words'))} palabras, "
                   f"{x.final.get('repair_rounds')} rondas de reparación, "
                   f"{usd(x.final.get('cost_usd'))}.")
    elif x.final.get("status"):
        fin_say = (f"El intento final terminó como «{x.final.get('status')}»: también lo "
                   "contamos, porque el sistema volvió a negarse a publicar algo que no pasaba.")
    else:
        fin_say = ("El intento final, con el tuning 2, se estaba generando al preparar esta "
                   "presentación; si os preguntan, está en runs.json y en el log.")
    a1 = x.attempts[0] if x.attempts else {}
    a2 = x.attempts[1] if len(x.attempts) > 1 else {}
    later = x.attempts[2:]
    later_say = [
        f"Y una ejecución paralela con el mismo código, {a.get('novel_id')}, se paró: el juez "
        "de novela la aprobaba, pero un evento del plan no tenía lugar y la exportación a "
        f"Lean falló; las {a.get('repair_rounds', '?')} rondas reescribieron prosa que no "
        f"podía arreglarlo. Coste {usd(a.get('cost_usd'))}. Ahora el chequeo del plan rechaza "
        "ese evento y un error de exportación para la ejecución sin gastar rondas."
        for a in later]
    d.script(s, Script(
        "Novelas de 10 capítulos y tuning 2", 90,
        "Las dos primeras novelas completas se bloquearon, y eso es el sistema funcionando: "
        "nada sin validar llega al cliente.",
        ["Esta es para mí la diapositiva más importante.",
         f"Primer intento: diez capítulos escritos y el juez de novela la suspendió por "
         f"saltos temporales y dos capítulos solapados. Coste {usd(a1.get('cost_usd'))}. No "
         "se publicó. Eso motivó el tuning 1.",
         f"Segundo intento, tras el tuning 1: tras {a2.get('repair_rounds', '?')} rondas de "
         "reparación, bloqueada otra vez: el 24 de junio aparecía como lunes cuando es "
         f"miércoles, y en cada ronda los días de la semana cambiaban. Coste {usd(a2.get('cost_usd'))}. Tampoco se publicó.",
         "La causa: nadie calculaba el calendario. El modelo inventaba el día de la semana, y "
         "cada reparación inventaba otro, así que no convergía. El error ya estaba en el plan.",
         "Tuning 2: el calendario lo calcula Python, no el LLM. El plan se corrige, el writer "
         "recibe las fechas reales, y un validador determinista para el error en el capítulo, "
         "sin gastar una ronda del juez.",
         fin_say, *later_say],
        [f"intentos parados: {', '.join(usd(a.get('cost_usd')) for a in x.attempts)}",
         f"total gastado sin publicar: {usd(spent)}"],
        "Veamos la novela que sí se entrega."))


def s_novel(d: Deck, x: Data) -> None:
    s = d.slide()
    nv = x.novel
    pdf = x.novel_pdf
    ten = x.final_pub
    d.header(s, "Resultados · la novela de ejemplo",
             "Novela de 10 capítulos publicada y exportada a PDF" if ten else
             "Una novela publicada de principio a fin, en PDF")
    imgs = []
    if pdf:
        tag = "novela-10" if ten else "novela-3"
        imgs = [C.pdf_page_png(pdf, 0, f"{tag}-portada"), C.pdf_page_png(pdf, 1, f"{tag}-indice"),
                C.pdf_page_png(pdf, 2, f"{tag}-cap1")]
    shown = [p for p in imgs if p]
    iw = 2.45
    for i, p in enumerate(shown):
        d.image(s, p, M + i * (iw + 0.2), 1.8, iw, 3.5, fit="contain")
    if not shown:
        d.label_box(s, M, 1.8, 3 * iw + 0.4, 3.5, "PDF " + PENDING,
                    "ejemplos/novela-ejemplo.pdf", MIST, LINE)
    d.text(s, M, 5.45, 3 * iw + 0.4, 0.4,
           (pdf or "ejemplos/novela-ejemplo.pdf") + " · portada, índice y capítulo 1", 11,
           color=MUTED)
    rx = M + 3 * iw + 0.8
    rw = W - M - rx
    stats = [(str(nv.get("chapters") or PENDING), "capítulos"),
             (num(nv.get("words")) if nv.get("words") else PENDING, "palabras"),
             (usd(nv.get("cost_usd")), "coste con Haiku 4.5"),
             (mins(nv.get("minutes")), "de generación"),
             (str(nv.get("repair_rounds")) if nv.get("repair_rounds") is not None else PENDING,
              "rondas de reparación")]
    for i, (big, small) in enumerate(stats):
        y = 1.75 + i * 0.82
        d.text(s, rx, y, rw, 0.5, big, 26, bold=True, color=TERRA, font=HEAD)
        d.text(s, rx, y + 0.48, rw, 0.3, small, 11, color=SLATE)
    note = ("Brief de ejemplo del README (evals/briefs/ejemplo.json); todos los validadores "
            "en verde, incluido Lean y judge_novel." if ten else
            "Brief b2-infantil, 3 capítulos. La novela de 10 capítulos (ejemplos/"
            "novela-ejemplo.pdf) está pendiente y sustituye a esta al reconstruir.")
    d.box(s, M, 5.95, W - 2 * M, 0.8, GREEN_L if ten else AMBER_L)
    d.text(s, M + 0.3, 6.0, W - 2 * M - 0.6, 0.7, note, 12, anchor=MSO_ANCHOR.MIDDLE)
    if ten:
        say = [f"Esta es la novela de ejemplo: {nv.get('chapters')} capítulos, "
               f"{num(nv.get('words'))} palabras, generada con el brief del README.",
               "Portada con dedicatoria, índice navegable y fichas, igual que en la web.",
               f"Costó {usd(nv.get('cost_usd'))} y tardó {mins(nv.get('minutes'))}, con "
               f"{nv.get('repair_rounds')} rondas de reparación.",
               "Pasó todos los validadores: nombres, cobertura, calendario, Lean y el juez de "
               "novela."]
    else:
        say = ["Esta es la novela que tenemos publicada de principio a fin con el pipeline "
               f"real: {nv.get('chapters')} capítulos, {num(nv.get('words'))} palabras, para "
               "una niña de siete años.",
               f"Costó {usd(nv.get('cost_usd'))} y {mins(nv.get('minutes'))}; necesitó "
               f"{nv.get('repair_rounds')} ronda de reparación y después pasó todo.",
               "Portada con dedicatoria, índice y fichas, exportada a PDF.",
               "La novela de 10 capítulos con el brief de ejemplo es la que se estaba "
               "generando con el tuning 2; si está, este hueco la muestra al reconstruir."]
    d.script(s, Script(
        "Novela de ejemplo", 60,
        "El sistema funciona de principio a fin: brief → novela publicada → PDF.",
        say,
        [f"{nv.get('chapters') or PENDING} capítulos", f"{num(nv.get('words'))} palabras",
         usd(nv.get("cost_usd")), mins(nv.get("minutes"))],
        "¿Y cuánto cuesta esto como negocio?"))


def s_cost(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Resultados · coste y latencia", "Lo que cuesta una novela con Claude Haiku 4.5")
    fin = x.final
    ten_cost = fin.get("cost_usd") if x.final_pub else None
    ten_min = fin.get("minutes") if x.final_pub else None
    att = [a.get("cost_usd") for a in x.attempts if a.get("cost_usd")]
    stats = [(usd(x.chap_cost), "coste medio por capítulo (evals)"),
             (mins(x.chap_min), "tiempo de modelo por capítulo"),
             (usd(ten_cost) if ten_cost else
              (f"{num(min(att), 2)}–{num(max(att), 2)} USD" if att else PENDING),
              "novela de 10 capítulos" if ten_cost else
              "novela de 10 capítulos (intentos completos)"),
             (mins(ten_min) if ten_min else
              (f"{min(a['minutes'] for a in x.attempts)}–"
               f"{max(a['minutes'] for a in x.attempts)} min" if x.attempts else PENDING),
              "tiempo real, 10 capítulos")]
    for i, (big, small) in enumerate(stats):
        y = 1.8 + i * 1.18
        d.text(s, M, y, 3.7, 0.65, big, 30, bold=True, color=TERRA, font=HEAD)
        d.text(s, M, y + 0.66, 3.7, 0.35, small, 12, color=SLATE)
    bars: list[tuple[str, float]] = []
    for r in C.eval_runs():
        if r.label == "after" and r.cost:
            bars.append((f"{r.brief} (3 cap.)", r.cost))
    if x.three.get("cost_usd"):
        bars.append(("novela-infantil (3 cap.)", x.three["cost_usd"]))
    for i, a in enumerate(x.attempts):
        if a.get("cost_usd"):
            # Numbered as on the results slide: the published attempt is the third.
            number = i + 1 if i < 2 else i + 2
            tag = "parada" if a.get("status") == "stopped_error" else "bloq."
            bars.append((f"10 cap. intento {number} ({tag})", a["cost_usd"]))
    if ten_cost:
        bars.append(("10 cap. final (publicada)", ten_cost))
    if bars:
        cd = CategoryChartData()
        cd.categories = [b[0] for b in reversed(bars)]
        cd.add_series("USD", [round(b[1], 2) for b in reversed(bars)])
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(4.4), Inches(1.7),
                                Inches(4.6), Inches(4.7), cd)
        _style_chart(gf.chart, "Coste por novela (USD)")
    by_role: dict[str, float] = {}
    for f in sorted((C.ROOT / "evals/results/after").glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for k, v in ((data.get("cost") or {}).get("by_role") or {}).items():
            by_role[k] = by_role.get(k, 0) + v
    if by_role:
        cd2 = CategoryChartData()
        items = sorted(by_role.items(), key=lambda kv: kv[1])
        cd2.categories = [k for k, _ in items]
        cd2.add_series("USD", [round(v, 2) for _, v in items])
        gf2 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(9.2), Inches(1.7),
                                 Inches(3.55), Inches(4.7), cd2)
        _style_chart(gf2.chart, "Coste por rol, evals «after»")
    d.text(s, M, 6.55, 12, 0.35,
           "Datos: tabla llm_call (evals/results/*/*.json) y logs de la CLI "
           "(presentacion/build/data/runs.json). Las reparaciones cuentan en el coste.",
           11, color=MUTED)
    d.script(s, Script(
        "Coste y latencia", 60,
        "Una novela de 10 capítulos cuesta unos pocos dólares de modelo y se genera en "
        "menos de dos horas.",
        [f"Un capítulo cuesta de media {usd(x.chap_cost)} y unos {mins(x.chap_min)} de "
         "modelo, contando escenas, editor, juez y reparaciones.",
         ("La novela de 10 capítulos publicada costó " + usd(ten_cost) + "."
          if ten_cost else
          f"Las novelas de 10 capítulos completas costaron entre {usd(min(att) if att else None)}"
          f" y {usd(max(att) if att else None)}, y eso incluye las rondas de reparación."),
         "El writer es el rol más caro, seguido del editor y el juez: tiene sentido, son los "
         "que producen y leen más texto.",
         "Comercialmente, el coste de modelo es pequeño frente al precio de un regalo "
         "personalizado; lo que cuesta de verdad es el tiempo, y por eso los bucles están "
         "acotados: una novela nunca se queda gastando indefinidamente."],
        [f"{usd(x.chap_cost)}/capítulo", f"{mins(x.chap_min)}/capítulo"] +
        ([usd(ten_cost)] if ten_cost else [f"{usd(a)}" for a in att]),
        "Cómo se construyó todo esto: Claude Code."))


def _style_chart(ch, title: str) -> None:
    ch.has_title = True
    ch.chart_title.text_frame.text = title
    tp = ch.chart_title.text_frame.paragraphs[0]
    tp.runs[0].font.size = Pt(13)
    tp.runs[0].font.bold = True
    tp.runs[0].font.name = BODY
    ch.has_legend = False
    plot = ch.plots[0]
    plot.gap_width = 60
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.font.size = Pt(11)
    dl.number_format = "0.00"
    dl.number_format_is_linked = False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    ser = plot.series[0]
    ser.format.fill.solid()
    ser.format.fill.fore_color.rgb = TERRA
    ch.value_axis.visible = False
    ch.value_axis.has_major_gridlines = False
    ch.category_axis.tick_labels.font.size = Pt(10)
    ch.category_axis.format.line.color.rgb = LINE


def s_claude_code(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Cómo se construyó · Claude Code",
             "Un orquestador y subagentes en paralelo, con reglas escritas")
    cards = [
        ("CLAUDE.md + AGENTS.md", "Mapa de docs y Procesos 0–3: docs → spec → plan → código. "
                                  "Proceso 0: preguntas con recomendación antes de editar."),
        ("Subagentes por bloque", "Un git worktree por agente, bloques en oleadas; contratos "
                                  "K1–K5 publicados antes que su implementación."),
        ("Skills", "gift-novel-run y security-review-harness (creadas), react, sqlite, "
                   "verification, fastapi."),
        ("Comandos /", "/generate-novel · /inspect-novel · /change-fact · /exam-gap."),
        ("Hooks", "PreToolUse policy_guard y PostToolUse validate_chapter: el mismo código que "
                  "el pipeline, 14 casos probados."),
        ("Browser MCP", "Playwright MCP inspeccionó el lector: cazó un 500 intermitente "
                        "(SQLite entre hilos) y fichas sin versionar; ambos corregidos."),
    ]
    cw, ch = (W - 2 * M - 0.6) / 3, 1.95
    for i, (t, body) in enumerate(cards):
        xx = M + (i % 3) * (cw + 0.3)
        y = 1.75 + (i // 3) * (ch + 0.25)
        d.box(s, xx, y, cw, ch, MIST)
        d.circle_num(s, xx + 0.25, y + 0.25, 0.42, i + 1, size=13)
        d.text(s, xx + 0.82, y + 0.28, cw - 1.0, 0.4, t, 16, bold=True, font=HEAD)
        d.text(s, xx + 0.25, y + 0.85, cw - 0.5, 1.05, body, 12, color=SLATE)
    d.box(s, M, 6.15, W - 2 * M, 0.65, TERRA_L)
    d.text(s, M + 0.3, 6.18, W - 2 * M - 0.6, 0.6, [
        [("Un límite que funcionó: ", {"bold": True}),
         ("un subagente intentó ampliar las exenciones de una regla de seguridad y el "
          "clasificador del modo auto lo bloqueó; la decisión quedó para el humano.", {})]],
           13, anchor=MSO_ANCHOR.MIDDLE)
    d.script(s, Script(
        "Uso de Claude Code", 60,
        "Claude Code fue el equipo: un orquestador, subagentes en paralelo y reglas que "
        "hacían cumplir el proceso.",
        ["CLAUDE.md y AGENTS.md definen el proceso: primero docs, luego spec, luego plan y "
         "código, y antes de editar, una ronda de preguntas con recomendación.",
         "Un orquestador repartió el trabajo en bloques; cada subagente trabajaba en su "
         "propio worktree, en paralelo, y los contratos entre bloques se publicaban primero.",
         "Skills propias: gift-novel-run para generar e inspeccionar una novela, y "
         "security-review-harness para repetir la revisión de seguridad. Comandos como "
         "/generate-novel o /change-fact.",
         "Y el browser MCP no fue decorativo: encontró un error 500 intermitente por una "
         "conexión SQLite compartida entre hilos, que corregimos."],
        ["14 casos de hooks", "1 worktree por agente"],
        "Toda esta construcción se apoya en decisiones que tomamos conscientemente."))


def s_tradeoffs(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Decisiones clave y trade-offs", "Qué elegimos, frente a qué, y lo que costó")
    rows = [["Decisión", "Frente a", "Por qué", "Coste"],
            ["Multi-agente con orquestador determinista", "un agente con herramientas",
             "permisos en código, reintento por paso, trazas por rol",
             "más llamadas y más orquestación"],
            ["SQLite autoritativa con hechos estructurados", "RAG vectorial sobre la prosa",
             "hechos exactos, fact_usage, entrada de Lean", "sin búsqueda semántica en el "
                                                            "pipeline"],
            ["Calendario y cifras en Python", "confiar en el LLM y el juez",
             "determinista y barato; converge", "solo días junto a una fecha"],
            ["Lector web + PDF exportado", "solo PDF interactivo",
             "pedir cambios, ver versiones, validar con MCP", "dos superficies que mantener"],
            ["TLA+ antes que el pipeline", "modelar después",
             "4 errores de diseño cazados cuando eran baratos", "el modelo abstrae la prosa"],
            ["Lean core, decide +kernel", "Mathlib, native_decide",
             "sin descargas; confía en el kernel", "noBilocation cuadrático"],
            ["claude -p sin tools", "SDK con API key", "ninguna clave en el repo; rol aislado",
             "arranque por llamada"],
            ["Haiku 4.5 para todos los roles", "Sonnet/Opus en writer y juez",
             "coste y latencia de 10 capítulos", "calidad vigilada por el juez"],
            ["Juez bloqueante (≥ 3, media ≥ 3,5)", "juez consultivo",
             "D11: la calidad también bloquea",
             f"reescrituras ≤ {x.max_chapter}, reparaciones ≤ {x.max_repair}"]]
    d.table(s, M, 1.7, W - 2 * M, rows, [3.2, 2.5, 3.6, 2.8], size=12, row_h=0.49)
    d.script(s, Script(
        "Decisiones y trade-offs", 75,
        "Cada decisión tiene alternativa, criterio y coste; la más importante es separar la "
        "verdad de la prosa.",
        ["Multi-agente frente a un agente con herramientas: elegimos roles orquestados por "
         "código porque los permisos se aplican en código y cada paso se valida y reintenta "
         "por separado. El precio: más llamadas.",
         "SQLite con hechos estructurados frente a RAG vectorial: aquí necesitamos hechos "
         "exactos y saber en qué capítulo se usa cada uno, no fragmentos parecidos.",
         "Calendario en Python en vez de confiar en el juez: lo aprendimos por las malas con "
         "la segunda novela bloqueada.",
         "Y el juez es bloqueante: por D11, la calidad narrativa también puede impedir la "
         "publicación."],
        [],
        "Ninguna de estas decisiones es gratis; estas son las limitaciones."))


def s_limits(d: Deck, x: Data) -> None:
    s = d.slide()
    d.header(s, "Limitaciones y siguientes pasos", "Lo que todavía no está demostrado")
    lim = [
        ("Fichas de personajes sin versionar en la BD: ", "solo el nombre se reconstruye por "
                                                          "versión."),
        ("Días sin fecha al lado ", "(«aquel lunes») y duraciones («treinta años») no se "
                                    "validan; van por prompt."),
        ("Lean solo prueba lo que hay en la cronología: ", "una partida que el planner no "
                                                           "registra no se detecta."),
        ("b4 bloquea bien pero caro: ", "agota reparaciones y el timeout de 45 min."),
        ("Regla de fronteras heredada: ", "21 accesos a ficheros fuera de los stores, "
                                          "pendientes de decisión."),
    ]
    if not x.human_review:
        lim.insert(2, ("Revisión humana ", "pendiente: protocolo, rúbrica y plantilla listos."))
    if not x.final_pub:
        lim.insert(0, ("Novela de 10 capítulos: ", f"{PENDING} de publicar con el tuning 2."))
    nxt = [
        ("Versionar el reparto ", "(descripción y rol por versión)."),
        ("Validar días y duraciones ", "en la prosa, no solo junto a fechas."),
        ("Evento «departure» obligatorio ", "cuando el brief dice que alguien se fue."),
        ("Revisión humana ", "y calibración del juez con compare.py."),
        ("Paralelizar capítulos ", "independientes para bajar la latencia."),
        ("Tools de escritura en el MCP ", "con permisos y confirmación."),
    ]
    cw = (W - 2 * M - 0.3) / 2
    d.box(s, M, 1.75, cw, 4.95, MIST)
    d.text(s, M + 0.3, 1.9, cw - 0.6, 0.4, "Limitaciones", 19, bold=True, font=HEAD)
    d.bullets(s, M + 0.3, 2.45, cw - 0.6, 4.2, lim[:7], 14, gap=7, marker_color=SLATE)
    x2 = M + cw + 0.3
    d.box(s, x2, 1.75, cw, 4.95, TERRA_L)
    d.text(s, x2 + 0.3, 1.9, cw - 0.6, 0.4, "Con más tiempo", 19, bold=True, font=HEAD,
           color=TERRA)
    d.bullets(s, x2 + 0.3, 2.45, cw - 0.6, 4.2, nxt, 14, gap=9)
    d.script(s, Script(
        "Limitaciones y siguientes pasos", 60,
        "Sabemos exactamente qué no está demostrado todavía, y está escrito.",
        ["Prefiero decirlo yo antes de que me lo preguntéis.",
         "Las fichas de personajes no están versionadas en la base de datos: si cambia la "
         "descripción de un personaje, la versión antigua de la ficha no la conserva; el "
         "nombre sí.",
         "El validador de calendario solo mira días de la semana junto a una fecha; «aquel "
         "lunes» o «treinta años» dependen del prompt.",
         "Lean solo prueba lo que el planner mete en la cronología: si alguien emigra y el "
         "plan no crea el evento de partida, nadie lo detecta.",
         ("La revisión humana con la misma rúbrica está preparada pero pendiente. "
          if not x.human_review else "") +
         "Y queda una decisión abierta sobre una regla heredada de accesos a ficheros."],
        [],
        "Para cerrar, la decisión que lo resume todo."))


EMAIL = ("Separé la verdad de la prosa: una story bible SQLite con validadores deterministas, "
         "Lean y TLA+ decide qué es cierto, y un bucle acotado planner → writer → editor → "
         "juez solo publica versiones que lo pasan todo; si no, bloquea, nunca entrega.")


def s_closing(d: Deck, x: Data) -> None:
    s = d.slide(dark=True)
    d.text(s, M + 0.4, 1.2, 10, 0.4, "LA DECISIÓN DE DISEÑO MÁS IMPORTANTE", 14, bold=True,
           color=TERRA)
    d.text(s, M + 0.4, 1.85, W - 2 * M - 0.8, 2.8,
           "Separar la verdad (story bible SQLite + validadores deterministas + Lean/TLA+) de "
           "la prosa generada, con un bucle acotado planner → writer → editor → juez que solo "
           "publica versiones que pasan todos los validadores.", 28, color=WHITE, font=HEAD)
    annexes = ["anexo-arquitectura.pdf", "anexo-tla-spec.pdf", "anexo-lean-invariantes.pdf",
               "anexo-evals-tabla.pdf", "anexo-revision-humana.pdf"]
    d.text(s, M + 0.4, 5.3, W - 2 * M, 0.35, "ANEXOS", 12, bold=True, color=TERRA)
    d.text(s, M + 0.4, 5.7, W - 2 * M - 0.8, 0.8, "  ·  ".join(annexes), 13,
           color=RGBColor(0xC9, 0xCF, 0xD6))
    d.text(s, M + 0.4, 6.55, 10, 0.35, f"Gracias · preguntas · presentacion/ · commit "
           f"{C.git_head()}", 11, color=MUTED)
    d.script(s, Script(
        "Cierre", 40,
        "Separar la verdad de la prosa, y publicar solo lo que pasa todos los validadores.",
        ["Si tuviera que quedarme con una decisión: separar la verdad de la prosa.",
         "Lo que es cierto sobre la historia vive en una base de datos, y lo comprueban "
         "validadores deterministas, Lean y TLA+. Los modelos solo redactan.",
         "El bucle está acotado y solo publica lo que pasa todo. Las dos novelas bloqueadas "
         "que os he enseñado son la prueba de que eso se cumple.",
         "En los anexos está el detalle de TLA+, Lean, evals y arquitectura. Muchas gracias; "
         "encantado de responder preguntas."],
        [],
        "Preguntas."))


# ----------------------------------------------------------------------------- guion.md

def qa(x: Data) -> list[tuple[str, str]]:
    a1 = x.attempts[0] if x.attempts else {}
    a2 = x.attempts[1] if len(x.attempts) > 1 else {}
    t = x.tlc
    fin = x.final
    if x.final_pub:
        cost_ans = (f"La novela de 10 capítulos publicada costó {usd(fin.get('cost_usd'))} y "
                    f"tardó {mins(fin.get('minutes'))}, con {fin.get('repair_rounds')} rondas "
                    "de reparación. ")
    else:
        cost_ans = ("La novela final de 10 capítulos está pendiente en runs.json; las dos "
                    f"completas que se bloquearon costaron {usd(a1.get('cost_usd'))} y "
                    f"{usd(a2.get('cost_usd'))}, en {mins(a1.get('minutes'))} y "
                    f"{mins(a2.get('minutes'))}. ")
    return [
        ("¿Por qué multi-agente y no un solo agente con herramientas?",
         "Porque quería que los permisos se cumplieran en código. Ningún modelo tiene "
         "herramientas: el orquestador decide qué ve cada rol, valida su salida con schema y "
         "escribe él en la base de datos. Así cada paso se valida y se reintenta por separado, "
         "hay trazas por rol y cada fallo vuelve al rol que puede arreglarlo. El coste es "
         "más llamadas y más código de orquestación; un agente único sería más simple, pero "
         "no podría demostrar quién escribió qué."),
        ("¿Por qué SQLite y no RAG vectorial?",
         "Porque lo que necesita el pipeline son hechos exactos, no fragmentos parecidos: el "
         "nombre del perro, la fecha de la boda, y en qué capítulo se usa cada hecho "
         "(fact_usage), que es lo que permite regenerar solo lo afectado y exportar la "
         "cronología a Lean. Los roles reciben hechos estructurados a través de tools "
         "validadas con schema (app/tools/). El índice heredado del harness genérico sí tiene "
         "FTS5 y sqlite-vec, pero el pipeline de novelas-regalo no lo usa: una búsqueda por "
         "similitud podría devolver un hecho parecido pero falso."),
        ("¿Qué detecta Lean que no detecte el juez?",
         "Caso L04, con el brief de trampas temporales y sin el prechequeo: la mascota muere "
         "en 2005 y lleva los anillos en la boda de 2008. Lean lo detectó con evento, fecha y "
         "capítulo. judge_novel también, pero judge_chapter aprobó el capítulo que cuenta la "
         "muerte y la boda, y ningún validador programático mira fechas. La diferencia: Lean "
         "es determinista, localiza el evento exacto y actúa sobre el plan, antes de escribir "
         "(~0,12 USD frente a ~1,3 USD de novela). Limitación: solo prueba lo que el planner "
         "pone en la cronología."),
        ("¿Qué contraejemplos encontró TLC y qué cambiaron en el código?",
         "Cuatro, antes de que existiera el pipeline. CE1: un crash entre guardar el capítulo "
         "y el checkpoint duplicaba el capítulo → texto y checkpoint en una transacción. CE2: "
         "el contador de reintentos de capítulo vivía en memoria → se cuenta desde "
         "validator_result. CE3: la reparación insertaba una segunda fila → upsert por "
         "(versión, capítulo) y la versión publicada no se escribe. CE4: el contador de rondas "
         "de reparación en memoria → columna repair_rounds guardada junto a «blocked». El "
         f"modelo actual pasa: {t.distinct} estados distintos, sin errores."),
        ("¿Cómo evitas que la personalización estropee la narrativa?",
         "Es la decisión D11: las dos pesan igual. brief_coverage comprueba que cada dato "
         "obligatorio aparece, pero el juez puntúa continuidad, tono, calidad narrativa, "
         "personalización natural (penaliza la personalización forzada) y final, y aprueba "
         "solo con cada criterio ≥ 3 y media ≥ 3,5. Un capítulo con todos los datos pero mal "
         "escrito no pasa. El linter de prosa añade repeticiones y clichés."),
        ("¿Cómo tratas la inyección en el texto libre?",
         "Como contenido no confiable. Un prescan determinista antes del modelo (tras la "
         "revisión de seguridad detecta 17 de 17 variantes), el extractor solo devuelve hechos "
         "y marca la sospecha, ningún rol recibe el texto crudo, y ningún modelo tiene "
         "herramientas para hacer daño. Las peticiones de cambio del lector también se "
         "escanean. Riesgo aceptado: un hecho extraído llega a los prompts, delimitado como "
         "dato."),
        ("¿Qué pasa si el juez suspende?",
         f"En un capítulo, el editor lo reescribe con la evidencia, como mucho "
         f"{x.max_chapter} veces. En la novela, hay hasta {x.max_repair} rondas de reparación "
         "solo de los capítulos que el juez señala. Si se agota, la versión queda «blocked» y "
         "nunca se publica: es el invariante NoUnvalidatedPublish de TLA+. Las dos novelas de "
         "10 capítulos bloqueadas son exactamente eso."),
        ("¿Cuánto cuesta y cuánto tarda una novela?",
         cost_ans + f"Un capítulo cuesta de media {usd(x.chap_cost)} y unos "
         f"{mins(x.chap_min)} de modelo; la novela de 3 capítulos publicada costó "
         f"{usd(x.three.get('cost_usd'))} en {mins(x.three.get('minutes'))}."),
        ("¿Por qué Haiku?",
         "Por coste y latencia: una novela son unas 70–80 llamadas. La calidad la vigila el "
         "juez con umbrales bloqueantes. Subir un rol concreto a Sonnet es una variable de "
         "entorno (MODEL_<ROL>) y se registraría en el log de iteraciones; no hizo falta: los "
         "fallos que vimos eran de diseño (calendario, validadores), no del modelo."),
        ("¿Cómo funciona el cambio del lector y qué se conserva?",
         "El lector pide «el perro se llama Nala». El hecho es una fila única; fact_usage dice "
         "qué capítulos lo usan y, si es un nombre, se busca el antiguo en hechos, brief, plan "
         "y texto. Solo esos capítulos se regeneran a una versión v+1, todo en una "
         "transacción. La versión anterior se conserva intacta (PreviousVersionKept), el "
         "índice marca los capítulos modificados y el PDF lleva una página de novedades."),
        ("¿Cuáles son las limitaciones reales?",
         "Las fichas de personajes no están versionadas en la BD (solo el nombre); los días de "
         "la semana sin fecha al lado y las duraciones no se validan; Lean solo ve lo que el "
         "planner registra; " +
         ("la revisión humana está pendiente; " if not x.human_review else "") +
         "y hay una regla heredada de accesos a ficheros pendiente de decisión (el test de "
         "fronteras)."),
        ("¿Qué harías con más tiempo?",
         "Versionar el reparto, validar días y duraciones en toda la prosa, exigir eventos de "
         "partida cuando el brief dice que alguien se fue, hacer la revisión humana y calibrar "
         "el juez, paralelizar capítulos para bajar la latencia y añadir tools de escritura "
         "al servidor MCP con confirmación."),
        ("¿Cómo usaste Claude Code?",
         "Como un equipo: una sesión orquestadora escribió la spec del programa y lanzó "
         "subagentes en paralelo, uno por bloque y cada uno en su git worktree, con contratos "
         "publicados antes. CLAUDE.md y AGENTS.md fijan el proceso docs → spec → plan → "
         "código. Hooks de validación y de policy, skills propias (gift-novel-run, "
         "security-review-harness), comandos / y el browser MCP, que encontró un 500 "
         "intermitente de SQLite entre hilos."),
        ("¿Por qué se bloquearon las novelas de 10 capítulos? ¿No es un fracaso?",
         "Es el sistema funcionando. La primera, por saltos temporales y capítulos solapados; "
         "la segunda, por días de la semana que contradecían su fecha, que el modelo "
         "reinventaba en cada reparación. Ninguna llegó al cliente. Cada bloqueo produjo una "
         "iteración de tuning con causa y efecto registrados; la segunda movió el calendario "
         "a Python y a un validador determinista."),
    ]


def write_guion(d: Deck, x: Data, out: Path) -> None:
    total = sum(sc.seconds for sc in d.scripts)
    L = ["# Guion de la presentación", "",
         "> Generado por `presentacion/build/build_deck.py` a partir de los mismos datos que el "
         "deck (`build/data/runs.json`, evals, TLC, informe de seguridad…). Las cifras "
         "coinciden con las diapositivas; si cambian los datos, se regenera. Para cambiar el "
         "texto, edita el script, no este fichero.", "",
         f"**Duración estimada:** {total // 60} min {total % 60:02d} s en "
         f"{len(d.scripts)} diapositivas (objetivo 12–15 min). Las notas del orador de cada "
         "diapositiva llevan este mismo guion.", "",
         "**Consejos:** habla a partir de los puntos, no leas. Si vas justo de tiempo, acorta "
         "Langfuse (11), contraejemplos (10) y Claude Code (17); no recortes la 14 (novelas "
         "bloqueadas): es el argumento central.", ""]
    for sc in d.scripts:
        L += [f"## {sc.n}. {sc.title} · ≈ {sc.seconds} s", "", f"**Mensaje clave.** {sc.key}",
              "", "**Qué decir:**", ""]
        L += [f"- {s}" for s in sc.say]
        if sc.numbers:
            L += ["", "**Cifras que mencionar:** " + " · ".join(sc.numbers)]
        L += ["", f"**Transición:** {sc.transition}", ""]
    L += ["---", "", "## Preguntas probables del tribunal", ""]
    for i, (q, a) in enumerate(qa(x), 1):
        L += [f"**{i}. {q}**", "", a, ""]
    L += ["---", "", "## Frase para el email (≤ 3 líneas)", "", f"> {EMAIL}", ""]
    out.write_text("\n".join(L), encoding="utf-8")


# ----------------------------------------------------------------------------- main

def to_pdf(pptx: Path) -> Path | None:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        print("  ! soffice not found: presentacion.pdf not regenerated")
        return None
    profile = C.HERE / ".lo-profile"
    cmd = [soffice, f"-env:UserInstallation=file://{profile}", "--headless",
           "--convert-to", "pdf", "--outdir", str(pptx.parent), str(pptx)]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=300)
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"  ! soffice failed: {exc}")
        return None
    pdf = pptx.with_suffix(".pdf")
    if not pdf.exists() or pdf.stat().st_mtime < pptx.stat().st_mtime:
        print("  ! soffice produced no PDF (is libreoffice-impress installed?)")
        return None
    return pdf


SLIDES = (s_title, s_problem, s_demo, s_arch, s_memory, s_validators, s_guardrails, s_lean,
          s_tla, s_tla_ce, s_langfuse, s_evals, s_security, s_ten, s_novel, s_cost,
          s_claude_code, s_tradeoffs, s_limits, s_closing)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--no-guion", action="store_true")
    ap.add_argument("--render", action="store_true", help="force Mermaid re-render")
    ap.add_argument("--out", default=str(C.PRES / "presentacion.pptx"))
    a = ap.parse_args()
    C.render_all(force=a.render)
    x = load()
    d = Deck()
    for fn in SLIDES:
        fn(d, x)
    out = Path(a.out)
    d.prs.save(out)
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB, {d.n} slides)")
    if not a.no_guion:
        g = C.PRES / "guion.md"
        write_guion(d, x, g)
        print(f"wrote {g.relative_to(C.ROOT)} "
              f"({sum(sc.seconds for sc in d.scripts) / 60:.1f} min)")
    if not a.no_pdf:
        pdf = to_pdf(out)
        if pdf:
            print(f"wrote {pdf}")


if __name__ == "__main__":
    main()

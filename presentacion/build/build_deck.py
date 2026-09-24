"""Build presentacion/presentacion.pptx (and presentacion.pdf) from the repository.

    uvx --with python-pptx --with matplotlib python presentacion/build/build_deck.py

Numbers are read live from the repo on every run: evals/results.md and
evals/results/*/*.json (outcomes, costs, prompt versions), evals/results/tuning.md,
formal/tla/tlc-output.txt and COUNTEREXAMPLES.md, docs/process/red-team-log.md,
docs/process/lean-caso-real.md. Re-run it after the final novel run.

Options: --no-pdf (skip the LibreOffice conversion), --render (force Mermaid re-render).
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
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

    def notes(self, s, txt):
        s.notes_slide.notes_text_frame.text = txt


# ----------------------------------------------------------------------------- helpers

def mark(v: str) -> str:
    return v.replace("✅", "✓").replace("❌", "✗").replace("⚑", "⚑").strip()


def status_fill(_i, _j, v):
    if v.startswith("✓"):
        return GREEN_L
    if v.startswith("✗"):
        return RED_L
    if v.startswith("⚑"):
        return AMBER_L
    return None


def fmt_usd(x: float | None) -> str:
    return "—" if x is None else f"{x:.2f} USD".replace(".", ",")


def fmt_min(sec: float | None) -> str:
    return "—" if sec is None else f"{sec / 60:.0f} min"


def exists(rel: str) -> bool:
    return (C.ROOT / rel).exists()


# ----------------------------------------------------------------------------- slides

def s_title(d: Deck) -> None:
    s = d.slide(dark=True)
    d.text(s, M, 0.9, 7, 0.3, "HARNESS ENGINEERING · ENTREGA FINAL", 13, bold=True, color=TERRA)
    d.text(s, M, 1.35, 7, 1.0, "My Story Marker", 54, bold=True, color=WHITE, font=HEAD)
    d.text(s, M, 2.45, 6.6, 1.2,
           "Novelas personalizadas para regalar, escritas por un harness de agentes "
           "que se puede verificar", 22, color=RGBColor(0xE4, 0xE7, 0xEB))
    stats = [("10", "capítulos de 1.000–1.500\npalabras, en español"),
             ("6", "roles con Claude Haiku 4.5\norquestados por código"),
             ("2", "verificaciones formales:\nLean 4 y TLA+")]
    for i, (big, small) in enumerate(stats):
        x = M + i * 2.2
        d.text(s, x, 4.25, 2.0, 0.8, big, 44, bold=True, color=TERRA, font=HEAD)
        d.text(s, x, 5.1, 2.1, 0.8, small, 12, color=RGBColor(0xC9, 0xCF, 0xD6))
    d.text(s, M, 6.55, 7, 0.4, f"Repositorio storyMaker · commit {C.git_head()} · 2026",
           11, color=MUTED)
    d.image(s, SHOTS / "browser-mcp/desktop-cover.png", 7.75, 0.9, 5.0, 5.7, border=False)
    d.notes(s, "Presentación técnico-comercial. Un producto (novelas-regalo) y el harness que "
               "lo hace fiable.")


def s_problem(d: Deck) -> None:
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
    d.notes(s, "Clientes: padres, parejas, bodas, aniversarios, jubilaciones.")


def s_demo1(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Demo del producto · 1/2", "Del brief a una novela que se lee y se regala")
    shots = [("visual-check/01-cover.png", "Portada con dedicatoria personalizada"),
             ("visual-check/02-index.png", "Índice navegable con marcas de versión"),
             ("visual-check/04-sheets.png", "Fichas desde la story bible, con «Aparece en»")]
    bw = (W - 2 * M - 0.5) / 3
    for i, (f, cap) in enumerate(shots):
        x = M + i * (bw + 0.25)
        d.image(s, SHOTS / f, x, 1.8, bw, 3.55)
        d.circle_num(s, x, 5.55, 0.36, i + 1, size=12)
        d.text(s, x + 0.48, 5.57, bw - 0.5, 0.5, cap, 13, bold=True)
    d.notes(s, "Capturas del lector React tomadas por el validador visual_check (Playwright) "
               "en pre_publish, novela de demostración demo-faro.")


def s_demo2(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Demo del producto · 2/2", "El lector pide un cambio: «el perro se llama Nala»")
    steps = [
        ("Selecciona el hecho", "en la página o por CLI/API (change_fact)."),
        ("Se actualiza la story bible", "el hecho es único: nunca hay dos versiones de él."),
        ("Solo se regeneran sus capítulos", "fact_usage dice qué capítulos lo usan."),
        ("Versión v+1 publicada", "la v1 se conserva; el índice marca «modificado»."),
        ("PDF nuevo con «novedades»", "capítulos cambiados con enlaces internos."),
    ]
    for i, (h, t) in enumerate(steps):
        y = 1.8 + i * 0.86
        d.circle_num(s, M, y, 0.45, i + 1)
        d.text(s, M + 0.65, y - 0.02, 4.6, 0.8,
               [[(h, {"bold": True, "size": 15})], [(t, {"size": 13, "color": SLATE})]], 15)
    d.image(s, SHOTS / "browser-mcp/desktop-index.png", 6.0, 1.75, 6.73, 3.6)
    d.box(s, 6.0, 5.55, 6.73, 1.2, GREEN_L)
    d.text(s, 6.25, 5.65, 6.3, 1.0, [
        [("Ejecución real (ab4731f): ", {"bold": True}),
         ("novela de 2 capítulos → versión 2 publicada, 0 apariciones del nombre antiguo, "
          "16 del nuevo, versión 1 intacta.", {})]], 14, anchor=MSO_ANCHOR.MIDDLE)
    d.notes(s, "El renombrado se propaga a hechos derivados, brief, plan, reparto y todo "
               "capítulo que mencione el nombre (iteración 7).")


def s_arch(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Arquitectura del harness", "Roles con un solo trabajo, orquestados por código")
    roles = [("interviewer", "brief + hechos\ndel texto libre"),
             ("planner", "plan, reparto\ny cronología"),
             ("writer", "3 escenas\npor capítulo"),
             ("editor", "une, pule,\nreescribe"),
             ("judge", "rúbrica de\n4 criterios"),
             ("publicación", "versión v\n(lector + PDF)")]
    bw, gap, y = 1.72, 0.39, 2.05
    xs = [M + i * (bw + gap) for i in range(len(roles))]
    for i, (x, (r, sub)) in enumerate(zip(xs, roles)):
        fill, line = (INK, INK) if i == 5 else (TERRA_L, TERRA)
        sh = d.label_box(s, x, y, bw, 1.05, r, sub, fill, line, 15, 11,
                         tcolor=WHITE if i == 5 else INK)
        if i == 5:
            sh.text_frame.paragraphs[1].runs[0].font.color.rgb = RGBColor(0xC9, 0xCF, 0xD6)
        if i < len(roles) - 1:
            d.arrow(s, x + bw, y + 0.52, x + bw + gap, y + 0.52)
    # validation points under the pipeline
    pts = [(0, "brief_schema", "hook"), (2, "scene_accept", "≤ 2 reescrituras"),
           (4, "chapter_close", "≤ 2 reescrituras · checkpoint"),
           (5, "pre_publish", "cobertura · Lean · juez · visual")]
    for idx, name, sub in pts:
        x = xs[idx] - (0.25 if idx == 4 else 0)
        d.label_box(s, x, 3.45, bw + (0.5 if idx == 4 else 0), 0.78, name, sub, WHITE, SLATE,
                    12, 10, MSO_SHAPE.HEXAGON)
        d.arrow(s, xs[idx] + bw / 2, y + 1.05, xs[idx] + bw / 2, 3.45, MUTED, 1)
    # store + observability
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
    d.notes(s, "Diagrama completo (Mermaid) en anexo-arquitectura.pdf, desde "
               "docs/process/diagramas.md.")


def s_memory(d: Deck) -> None:
    s = d.slide()
    er = C.mermaid_blocks("docs/process/diagramas.md")
    ntab = len(re.findall(r"^\s+(\w+) \{", er[2], re.M)) if len(er) > 2 else 16
    d.header(s, "Memoria", f"La story bible: una SQLite autoritativa con {ntab} tablas")
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
        x = M + (i % 2) * (cw + 0.3)
        y = 1.75 + (i // 2) * (ch + 0.3)
        d.box(s, x, y, cw, ch, MIST)
        d.circle_num(s, x + 0.3, y + 0.3, 0.45, i + 1, size=14)
        d.text(s, x + 0.95, y + 0.3, cw - 1.2, 0.45, t, 18, bold=True, font=HEAD)
        d.text(s, x + 0.95, y + 0.78, cw - 1.2, 0.3, tabs, 11, font=MONO, color=TERRA)
        d.text(s, x + 0.95, y + 1.15, cw - 1.25, 0.85, body, 13, color=SLATE)
    d.text(s, M, 6.5, W - 2 * M, 0.3,
           "Diagrama entidad-relación completo (Mermaid) en anexo-arquitectura.pdf", 11,
           color=MUTED)
    d.notes(s, "Decisiones D1, D2, D6, V4. Migraciones 1000_init, 1001_tlc_rules, "
               "1300_forbidden_terms_global.")


def s_validators(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Validadores", "Cada fallo se detecta donde es barato repararlo")
    pts = [("hook", "al entregar el brief"), ("scene_accept", "cada escena"),
           ("chapter_close", "cada capítulo"), ("pre_publish", "antes de publicar")]
    pw = 2.75
    for i, (p, sub) in enumerate(pts):
        x = M + i * (pw + 0.4)
        d.label_box(s, x, 1.7, pw, 0.72, p, sub, TERRA_L if i else MIST, TERRA, 14, 11,
                    MSO_SHAPE.CHEVRON if i else MSO_SHAPE.PENTAGON)
    rows = [["Tipo", "Validadores", "Punto de ejecución", "Si falla"],
            ["Programático", "brief_schema · schema_role_output · chapter_length · "
             "exact_names · brief_coverage · prose_repetition · no_placeholders · visual_check",
             "hook · scene_accept · chapter_close · pre_publish",
             "vuelve al rol productor con la evidencia"],
            ["Guardrail", "forbidden_words_scene · forbidden_words_chapter · "
             "free_text_injection (prescan)", "entrevista · scene_accept · chapter_close",
             "reescritura ≤ 2 → forbidden_word_limit"],
            ["Semántico", "judge_chapter · judge_novel · revisión humana (misma rúbrica)",
             "chapter_close · pre_publish · una novela", "editor; aprueba si cada criterio ≥ 3 "
             "y media ≥ 3,5"],
            ["Formal", "lean_chronology (4 invariantes) · TLA+/TLC del flujo (en desarrollo)",
             "pre_publish · desarrollo", "versión bloqueada; 1 ronda de reparación de los "
             "capítulos citados"]]
    d.table(s, M, 2.7, W - 2 * M, rows, [1.3, 4.6, 3.0, 3.2], size=12, row_h=0.62)
    d.text(s, M, 6.05, W - 2 * M, 0.7, [
        [("Cada validador tiene nombre y punto de ejecución, y envía su resultado a Langfuse "
          "como score. ", {}),
         ("Un fallo en pre_publish no reescribe la novela: ", {"bold": True}),
         ("solo se reabren los capítulos que cita la evidencia.", {})]], 13, color=SLATE)
    d.notes(s, "Registro K3 en app/validators/registry.py. Tabla completa en "
               "docs/process/diagramas.md y anexo-arquitectura.pdf.")


def s_guardrails(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Guardrails y policy", "Reglas que se cumplen aunque el modelo no quiera")
    cols = [
        ("Vetos en 3 niveles", [
            ("Global: ", "sembrado por migración (1300)."),
            ("Novela: ", "los vetos del cliente en el brief."),
            ("Léxico: ", "variantes extra que aporta cada validador."),
            ("Un acierto ", "vuelve al escritor, ≤ 2 veces.")]),
        ("Un solo normalizador", [
            ("Plegado común ", "de texto y término (NFKD, sin tildes)."),
            ("Detecta: ", "t0nt0 · tontooo · t.o.n.t.o · cabrones → cabrón."),
            ("Sin falsos positivos: ", "«ridículo», «tontería»."),
            ("Palabra completa ", "y frases, no subcadenas.")]),
        ("Audit log y hooks", [
            ("policy_decision: ", "cada decisión con término, intento y traza."),
            ("Score guardrail:* ", "en Langfuse."),
            ("PreToolUse policy_guard: ", ".env, claves, escritura directa a la BD."),
            ("PostToolUse validate_chapter: ", "mismas reglas en ediciones a mano.")]),
    ]
    cw = (W - 2 * M - 0.6) / 3
    for i, (t, items) in enumerate(cols):
        x = M + i * (cw + 0.3)
        d.box(s, x, 1.75, cw, 2.95, MIST)
        d.text(s, x + 0.25, 1.92, cw - 0.5, 0.4, t, 17, bold=True, font=HEAD)
        d.bullets(s, x + 0.25, 2.45, cw - 0.45, 2.2, items, 13, gap=4)
    rows = [["Intento en Claude Code (commit 54854d3)", "Resultado"],
            ["Write backend/.env · valor con forma de clave sk-ant-…", "bloqueado (exit 2)"],
            ["Bash sqlite3 data/harness.sqlite \"delete …\"", "bloqueado (exit 2)"],
            ["Bash sqlite3 … \"select …\" · Edit backend/app/main.py", "permitido (exit 0)"],
            ["Capítulo con «c4br0n» o de 2 palabras", "bloqueado (exit 2)"]]

    def fill(_i, j, v):
        return (RED_L if "bloqueado" in v else GREEN_L) if j == 1 else None

    d.table(s, M, 4.95, W - 2 * M, rows, [8, 3], size=12, row_h=0.33, cell_fill=fill)
    d.notes(s, "Motor en app/policy/engine.py: decide y registra, nunca reescribe. El texto "
               "libre del cliente es contenido no confiable: prescan de inyección y solo "
               "hechos extraídos llegan a los roles.")


def s_lean(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Verificación formal · Lean 4",
             "Un build verde prueba que la cronología es coherente")
    inv = [("temporalOrder", "Lo que se cuenta después ocurre el mismo día o más tarde."),
           ("agesCoherent", "Cada edad declarada = años cumplidos desde el nacimiento."),
           ("noBilocation", "Nadie está en dos lugares el mismo día."),
           ("noAfterExit", "Tras una muerte o partida, esa persona no vuelve a aparecer.")]
    for i, (n, t) in enumerate(inv):
        x = M + (i % 2) * 3.95
        y = 1.75 + (i // 2) * 1.35
        d.box(s, x, y, 3.75, 1.15, TERRA_L)
        d.text(s, x + 0.22, y + 0.14, 3.4, 0.35, n, 15, bold=True, font=MONO, color=TERRA)
        d.text(s, x + 0.22, y + 0.52, 3.35, 0.6, t, 12)
    d.bullets(s, M, 4.6, 7.6, 1.5, [
        ("Bool + Prop + teorema de corrección: ", "la comprobación es una prueba, no un true."),
        ("Solo core Lean, sin Mathlib; ", "decide +kernel (decide revienta maxRecDepth ~100 "
                                           "eventos)."),
        ("Se genera desde la story bible ", "en pre_publish; si falla, no se publica y el "
                                           "fallo vuelve al editor con los eventos."),
    ], 13, gap=4)
    # stats
    sx = M + 8.2
    for i, (big, small) in enumerate([("3 s", "100 eventos"), ("17 s", "300 eventos")]):
        d.text(s, sx + i * 2.2, 1.75, 2.0, 0.7, big, 36, bold=True, color=TERRA, font=HEAD)
        d.text(s, sx + i * 2.2, 2.5, 2.0, 0.3, f"build · {small}", 12, color=SLATE)
    # real case
    real = C.lean_real_case()
    d.box(s, sx, 3.1, W - M - sx, 3.0, MIST)
    d.text(s, sx + 0.22, 3.22, W - M - sx - 0.4, 0.35, "Caso real", 16, bold=True, font=HEAD)
    if real:
        body = re.sub(r"^#.*\n", "", real).strip()
        body = C.strip_md(re.split(r"\n\s*\n", body)[0])[:420]
        d.text(s, sx + 0.22, 3.62, W - M - sx - 0.4, 2.4, body, 12, color=SLATE)
    else:
        log = C.read("evals/results/before/logs/b4-temporal.log")
        invs = sorted(set(re.findall(r"chronology (\w+):", log)))
        runs = {r.brief: r for r in C.eval_runs()}
        b4 = runs.get("b4-temporal")
        txt = [[("b4-temporal: ", {"bold": True}),
                (f"el diagnóstico de cronología del plan (los mismos invariantes) detectó "
                 f"{', '.join(invs) or 'las trampas'} — la mascota muerta que reaparece — "
                 f"antes de escribir una línea; tras 1 replan, parada controlada", {})],
               [(f"({fmt_usd(b4.cost if b4 else None)} en vez de una novela entera).",
                 {})],
               [("Pendiente: un caso cazado por Lean en pre_publish y por ningún otro "
                 "validador (docs/process/lean-caso-real.md).", {"italic": True,
                                                                  "color": MUTED})]]
        d.text(s, sx + 0.22, 3.62, W - M - sx - 0.4, 2.4, txt, 12, color=SLATE, spacing=4)
    d.notes(s, "formal/lean/Chronology/Basic.lean; exportador backend/app/formal/"
               "lean_export.py. Detalle en anexo-lean-invariantes.pdf.")


def s_tla(d: Deck) -> None:
    s = d.slide()
    t = C.tlc()
    cfg = C.tla_config()
    d.header(s, "Verificación formal · TLA+",
             "El flujo del harness, comprobado con TLC")
    # snake: row 1 left to right, row 2 right to left
    row1 = ["Configured", "Planned", "Scene", "Editor", "Close"]
    row2 = ["Checkpoint", "Next", "PrePublish", "Published"]  # under Close … Planned
    bw, gap = 1.75, 0.5
    xs = [M + i * (bw + gap) for i in range(5)]
    for i, n in enumerate(row1):
        d.label_box(s, xs[i], 1.75, bw, 0.55, n, "", TERRA_L, TERRA, 13)
        if i < len(row1) - 1:
            d.arrow(s, xs[i] + bw, 2.02, xs[i + 1], 2.02)
    d.arrow(s, xs[4] + bw / 2, 2.3, xs[4] + bw / 2, 2.75)
    for i, n in enumerate(row2):
        x = xs[4 - i]
        pub = n == "Published"
        d.label_box(s, x, 2.75, bw, 0.55, n, "", INK if pub else TERRA_L,
                    INK if pub else TERRA, 13, tcolor=WHITE if pub else INK)
        if i < len(row2) - 1:
            d.arrow(s, x, 3.02, xs[3 - i] + bw, 3.02)
    d.label_box(s, xs[0], 2.75, bw, 0.55, "StoppedError", "", RED_L, RED, 12)
    d.text(s, M, 3.45, W - 2 * M, 0.35,
           "Bucles acotados (≤ 2 reintentos, 1 reparación) → StoppedError al agotarse. "
           "Crash → Resume desde la BD. ChangeFact → versión v+1.", 12, color=SLATE)
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
        [(("Sin errores" if t.ok else "Con errores"), {"bold": True, "size": 20,
                                                        "color": GREEN_L if t.ok else RED_L})],
        [(f"{t.distinct}", {"bold": True, "size": 30, "color": TERRA, "font": HEAD})],
        [("estados distintos", {"size": 12, "color": WHITE})],
        [(f"{t.generated} generados · profundidad {t.depth} · {t.duration}",
          {"size": 11, "color": RGBColor(0xC9, 0xCF, 0xD6)})],
        [(f"N = {cfg.get('N', '?')} capítulos · {cfg.get('SCENES', '?')} escenas · "
          f"reintentos {cfg.get('MAX_SCENE_RETRIES', '?')}/"
          f"{cfg.get('MAX_CHAPTER_RETRIES', '?')}",
          {"size": 11, "color": RGBColor(0xC9, 0xCF, 0xD6)})]], 12)
    d.notes(s, "formal/tla/GiftNovelHarness.tla + .cfg; salida en tlc-output.txt. TLC corre en "
               "desarrollo, no por generación.")


def s_tla_ce(d: Deck) -> None:
    s = d.slide()
    d.header(s, "TLA+ · contraejemplos", "Cuatro trazas de TLC que cambiaron el código",
             "El modelo se escribió en paralelo al pipeline, leyendo el esquema y el plan tal "
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
    d.table(s, M, 2.1, W - 2 * M, rows, [0.6, 2.0, 1.0, 4.3, 4.3], size=12, row_h=0.72)
    d.box(s, M, 5.95, W - 2 * M, 0.8, TERRA_L)
    d.text(s, M + 0.3, 6.0, W - 2 * M - 0.6, 0.7, [
        [("Efecto: ", {"bold": True}),
         ("la spec de la story bible volvió a borrador y se reaprobó antes de que existiera el "
          "pipeline, que nació con las cuatro reglas. Dos mutaciones (publicar sin pre_publish, "
          "regenerar en sitio) confirman que las propiedades no son vacías.", {})]], 13,
           anchor=MSO_ANCHOR.MIDDLE)
    d.notes(s, "Detalle de cada traza en formal/tla/COUNTEREXAMPLES.md y "
               "anexo-tla-spec.pdf.")


def s_langfuse(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Observabilidad · Langfuse", "Qué hizo cada llamada, cuánto costó y con qué prompt")
    levels = [("Sesión", "una por novela: entrevista, generación y regeneraciones"),
              ("Traza", "una por generate o change_fact"),
              ("Spans", "phase:* · chapter:<n> · role:<rol> · tool:<nombre>"),
              ("Generaciones", "tokens, coste (pricing.py) y latencia por llamada"),
              ("Scores", "cada validador, guardrail y criterio del juez; novel_cost_usd")]
    for i, (n, t) in enumerate(levels):
        y = 1.8 + i * 0.9
        x = M + i * 0.3
        d.label_box(s, x, y, 1.75, 0.66, n, "", TERRA_L if i < 4 else INK,
                    TERRA if i < 4 else INK, 14, tcolor=INK if i < 4 else WHITE)
        d.text(s, x + 1.95, y + 0.08, 5.2 - i * 0.3, 0.6, t, 13, color=SLATE,
               anchor=MSO_ANCHOR.MIDDLE)
    # prompts table from the last eval run
    prompts: dict[tuple[str, str], tuple[str, int]] = {}
    import json
    for f in sorted((C.ROOT / "evals/results").glob("*/*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for p in data.get("prompts") or []:
            k = (p["role"], p["prompt_name"])
            old = prompts.get(k, ("", 0))
            prompts[k] = (str(p["prompt_version"]), old[1] + int(p.get("calls", 0)))
    rows = [["Rol", "Prompt", "Versión", "Llamadas"]]
    for (role, name), (ver, calls) in sorted(prompts.items()):
        rows.append([role, name, ver if len(ver) < 12 else ver[:11] + "…", str(calls)])
    tx = M + 7.6
    d.text(s, tx, 1.8, W - M - tx, 0.35, "Prompts versionados en las evals", 15, bold=True,
           font=HEAD)
    if len(rows) > 1:
        d.table(s, tx, 2.25, W - M - tx, rows, [1.3, 1.7, 1.2, 1.0], size=11, row_h=0.36)
    d.text(s, tx, 2.35 + 0.36 * len(rows), W - M - tx, 1.2,
           "Cada llamada guarda prompt_version también en llm_call (SQLite), así el coste y "
           "la comparación antes/después no dependen de Langfuse. Sin claves: NoopObserver.",
           11, color=SLATE)
    d.notes(s, "backend/app/commons/observability/ (contrato K2). Prompts en "
               "backend/app/prompts/*.md publicados en la gestión de prompts de Langfuse.")


def s_evals(d: Deck) -> None:
    s = d.slide()
    label = C.results_label()
    d.header(s, "Evals", f"Cinco briefs × validadores · iteración «{label}»")
    tab = C.results_table()
    short = {"brief_schema": "schema", "forbidden_words_scene": "vetos esc.",
             "forbidden_words_chapter": "vetos cap.", "chapter_length": "longitud",
             "exact_names": "nombres", "brief_coverage": "cobertura",
             "prose_repetition": "repetición", "judge_chapter": "juez cap.",
             "judge_novel": "juez nov.", "lean_chronology": "Lean", "visual_check": "visual",
             "injection": "inyección", "final": "final", "cost USD": "USD", "brief": "brief"}
    if tab:
        head = tab[0]
        keep = [i for i, h in enumerate(head) if h != "tokens in/out"]
        rows = [[short.get(head[i], head[i]) for i in keep]]
        for r in tab[1:]:
            rows.append([mark(C.strip_md(r[i])) if i < len(r) else "" for i in keep])
        widths = [1.5] + [0.75] * (len(keep) - 3) + [1.55, 0.7]
        d.table(s, M, 1.75, W - 2 * M, rows, widths, size=10, row_h=0.42,
                cell_fill=status_fill)
    y = 1.75 + 0.42 * (len(tab) if tab else 1) + 0.3
    tuning = C.tuning_md()
    d.box(s, M, y, W - 2 * M, min(1.9, H - 0.7 - y), MIST)
    d.text(s, M + 0.3, y + 0.15, 5, 0.4, "Iteración de tuning", 16, bold=True, font=HEAD)
    if tuning:
        tt = C.md_tables(tuning)
        body = C.strip_md(re.sub(r"^#.*\n", "", tuning).strip().split("\n\n")[0])[:500]
        d.text(s, M + 0.3, y + 0.6, W - 2 * M - 0.6, 1.8, body, 12, color=SLATE)
        del tt
    else:
        d.text(s, M + 0.3, y + 0.6, W - 2 * M - 0.6, 1.8, [
            [("Lo que ya muestra «before»: ", {"bold": True}),
             ("el validador que bloquea es brief_coverage (recuerdos obligatorios que no "
              "aparecen literalmente); b3 marca la inyección y no la sigue; b4 se detiene en el "
              "plan por la cronología; b5 se rechaza antes de generar, como se esperaba.", {})],
            [("Pendiente: ", {"bold": True}),
             ("la ejecución «after» tras un cambio de prompt y su comparación "
              "(compare_iterations.py → evals/results/tuning.md); esta sección se rellena sola "
              "al reconstruir.", {"italic": True})]], 12, color=SLATE, spacing=6)
    d.notes(s, "evals/run_evals.py; tabla en evals/results.md; detalle en "
               "anexo-evals-tabla.pdf.")


def s_redteam(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Red-team", "Ataques probados, qué los detuvo y qué queda pendiente")
    tabs = C.md_tables(C.read("docs/process/red-team-log.md"))
    rows = [["#", "Caso", "Defensa", "Estado"]]
    if tabs:
        for r in tabs[0][1:]:
            rows.append([C.strip_md(r[0]), C.strip_md(r[1]), C.strip_md(r[3]),
                         mark(C.strip_md(r[4]))])

    def fill(_i, j, v):
        if j != 3:
            return None
        if v.startswith("✓") and "pendiente" not in v.lower():
            return GREEN_L
        if "pendiente" in v.lower():
            return AMBER_L
        return None

    d.table(s, M, 1.75, W - 2 * M, rows, [0.5, 4.0, 4.6, 3.0], size=11, row_h=0.5,
            cell_fill=fill)
    d.text(s, M, 6.45, W - 2 * M, 0.4,
           "Hallazgo de revisión (R2): el texto libre crudo llegaba al planner y al juez; desde "
           "a721bc7 solo reciben los hechos extraídos.", 12, color=SLATE)
    d.notes(s, "docs/process/red-team-log.md. Los casos de generación se actualizan con cada "
               "ejecución de evals.")


def s_claude_code(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Uso de Claude Code", "Construido por un orquestador y subagentes en paralelo")
    cards = [
        ("CLAUDE.md + AGENTS.md", "Mapa de docs y Procesos 0–3: docs → spec → plan → código. "
                                  "Proceso 0 en 4 rondas antes de la spec 004."),
        ("Subagentes por bloque", "12 bloques, 4 oleadas, un git worktree por agente; "
                                  "contratos K1–K5 publicados antes que su implementación."),
        ("Skills", "gift-novel-run (creada: generar e inspeccionar de punta a punta), react, "
                   "sqlite, verification, fastapi."),
        ("Comandos /", "/generate-novel · /inspect-novel · /change-fact · /exam-gap."),
        ("Hooks", "PreToolUse policy_guard y PostToolUse validate_chapter: el mismo código que "
                  "el pipeline, 14 casos probados."),
        ("Browser MCP", "Playwright MCP inspeccionó el lector: cazó un 500 intermitente "
                        "(SQLite entre hilos) y fichas sin versionar; ambos corregidos."),
    ]
    cw, ch = (W - 2 * M - 0.6) / 3, 1.95
    for i, (t, body) in enumerate(cards):
        x = M + (i % 3) * (cw + 0.3)
        y = 1.75 + (i // 3) * (ch + 0.25)
        d.box(s, x, y, cw, ch, MIST)
        d.circle_num(s, x + 0.25, y + 0.25, 0.42, i + 1, size=13)
        d.text(s, x + 0.82, y + 0.28, cw - 1.0, 0.4, t, 16, bold=True, font=HEAD)
        d.text(s, x + 0.25, y + 0.85, cw - 0.5, 1.05, body, 12, color=SLATE)
    d.box(s, M, 6.15, W - 2 * M, 0.65, TERRA_L)
    d.text(s, M + 0.3, 6.18, W - 2 * M - 0.6, 0.6, [
        [("Un límite que funcionó: ", {"bold": True}),
         ("un subagente intentó ampliar las exenciones de una regla de seguridad y el "
          "clasificador del modo auto lo bloqueó; la decisión quedó para el humano.", {})]],
           13, anchor=MSO_ANCHOR.MIDDLE)
    d.notes(s, "docs/process/subagentes-comandos-skills.md y browser-mcp-log.md.")


def s_cost(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Coste y latencia", "Lo que cuesta una novela con Claude Haiku 4.5")
    runs = [r for r in C.eval_runs() if r.cost]
    chap = [c for r in runs for c in r.by_chapter if c.get("chapter") is not None]
    plan = [c for r in runs for c in r.by_chapter if c.get("chapter") is None]
    cpc = sum(c["cost_usd"] for c in chap) / len(chap) if chap else None
    lpc = sum(c["latency_s"] for c in chap) / len(chap) if chap else None
    cplan = sum(c["cost_usd"] for c in plan) / len(plan) if plan else 0.0
    lplan = sum(c["latency_s"] for c in plan) / len(plan) if plan else 0.0
    est = cplan + 10 * cpc if cpc else None
    estl = lplan + 10 * lpc if lpc else None
    stats = [(fmt_usd(cpc), "coste medio por capítulo"),
             (fmt_min(lpc), "tiempo de modelo por capítulo"),
             (fmt_usd(est), "estimación, novela de 10 capítulos"),
             (fmt_min(estl), "estimación de tiempo, 10 capítulos")]
    for i, (big, small) in enumerate(stats):
        y = 1.8 + i * 1.18
        d.text(s, M, y, 3.6, 0.65, big, 34, bold=True, color=TERRA, font=HEAD)
        d.text(s, M, y + 0.66, 3.6, 0.35, small, 12, color=SLATE)
    d.text(s, M, 6.55, 12, 0.35,
           f"Medido en {len(chap)} capítulos de {len(runs)} ejecuciones de evals (tiempo de "
           "modelo secuencial); smoke de 1 capítulo: 0,30 USD, 7 llamadas, ~6,5 min.",
           11, color=MUTED)
    # chart 1: cost per brief
    if runs:
        cd = CategoryChartData()
        cd.categories = [f"{r.brief} ({r.label})" for r in runs]
        cd.add_series("USD", [round(r.cost or 0, 2) for r in runs])
        gf = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(4.4), Inches(1.7),
                                Inches(4.3), Inches(4.6), cd)
        _style_chart(gf.chart, "Coste por ejecución (USD)")
    by_role: dict[str, float] = {}
    import json
    for f in sorted((C.ROOT / "evals/results").glob("*/*.json")):
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
        gf2 = s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED, Inches(8.9), Inches(1.7),
                                 Inches(3.85), Inches(4.6), cd2)
        _style_chart(gf2.chart, "Coste acumulado por rol (USD)")
    d.notes(s, "Datos de evals/results/*/*.json (tabla llm_call). Las ejecuciones incluyen la "
               "ronda de reparación de pre_publish, así que la estimación es conservadora.")


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
    ch.category_axis.tick_labels.font.size = Pt(11)
    ch.category_axis.format.line.color.rgb = LINE


def s_tradeoffs(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Decisiones clave y trade-offs", "Qué elegimos, frente a qué, y lo que costó")
    rows = [["Decisión", "Frente a", "Por qué", "Coste"],
            ["Multi-agente con orquestador determinista", "un agente con herramientas",
             "permisos en código, reintento por paso, trazas por rol", "más llamadas y más "
                                                                         "orquestación"],
            ["SQLite autoritativa (y el texto en la BD)", "ficheros + índice derivado",
             "una sola verdad para validadores, lector y Lean", "sin diffs de git sobre la "
                                                                 "prosa"],
            ["Lector web + PDF exportado", "solo PDF interactivo",
             "pedir cambios, ver versiones, validar con MCP", "dos superficies que mantener"],
            ["TLA+ antes que el pipeline", "modelar después",
             "4 errores de diseño cazados cuando eran baratos", "el modelo abstrae prosa y "
                                                                "validadores"],
            ["Lean core, decide +kernel", "Mathlib, native_decide",
             "sin descargas; confía en el kernel", "noBilocation cuadrático"],
            ["claude -p sin tools", "SDK con API key", "ninguna clave en el repo; rol aislado",
             "arranque por llamada; política de privacidad del CLI"],
            ["Haiku 4.5 para todos los roles", "Sonnet/Opus en writer y juez",
             "coste y latencia de 10 capítulos", "calidad vigilada por juez; subida por rol"],
            ["Juez bloqueante (≥ 3, media ≥ 3,5)", "juez consultivo",
             "D11: la calidad también bloquea", "reescrituras con presupuesto 2"]]
    d.table(s, M, 1.7, W - 2 * M, rows, [3.2, 2.4, 3.6, 2.9], size=11, row_h=0.54)
    d.notes(s, "docs/process/trade-offs.md, con opciones, criterios y elección para cada una.")


def s_limits(d: Deck) -> None:
    s = d.slide()
    d.header(s, "Limitaciones y siguientes pasos", "Lo que todavía no está demostrado")
    lim = [
        ("Evals «before»: ", "b2 y b3 quedan bloqueadas por brief_coverage; falta publicar la "
                             "novela de 10 capítulos del ejemplo."),
        ("Lean: ", "aún sin un caso real cazado en pre_publish que no viera otro validador."),
        ("Revisión humana ", "pendiente (protocolo y plantilla listos)."),
        ("Reparto sin versionar: ", "solo el nombre se reconstruye por versión."),
        ("Verificación ligera (V3), ", "registrada como riesgo aceptado U."),
        ("policy_guard trabaja por patrones; ", "la defensa de fondo es BibleRepository."),
        ("Regla de fronteras heredada: ", "21 accesos a ficheros fuera de los stores, "
                                          "pendientes de decisión humana."),
    ]
    if C.tuning_md():
        lim[0] = ("Evals: ", "ver la iteración de tuning en el anexo de evals.")
    if C.lean_real_case():
        lim.pop(1)
    if list((C.ROOT / "evals/human-review").glob("review-*.yaml")):
        lim = [x for x in lim if not x[0].startswith("Revisión humana")]
    nxt = [
        ("Tuning de cobertura: ", "cambio de prompt, ejecución «after» y comparación."),
        ("Novela de ejemplo ", "de 10 capítulos, publicada y exportada a PDF."),
        ("Revisión humana ", "de una novela completa y calibración del juez (compare.py)."),
        ("Versionar el reparto ", "(descripción y rol por versión)."),
        ("Subir un rol a Sonnet ", "solo si falla de forma repetida, con registro."),
        ("Vídeo de demo ", "del flujo completo."),
    ]
    cw = (W - 2 * M - 0.3) / 2
    d.box(s, M, 1.75, cw, 4.55, MIST)
    d.text(s, M + 0.3, 1.9, cw - 0.6, 0.4, "Limitaciones", 19, bold=True, font=HEAD)
    d.bullets(s, M + 0.3, 2.45, cw - 0.6, 4.2, lim, 14, gap=8, marker_color=SLATE)
    x2 = M + cw + 0.3
    d.box(s, x2, 1.75, cw, 4.55, TERRA_L)
    d.text(s, x2 + 0.3, 1.9, cw - 0.6, 0.4, "Siguientes pasos", 19, bold=True, font=HEAD,
           color=TERRA)
    d.bullets(s, x2 + 0.3, 2.45, cw - 0.6, 4.2, nxt, 14, gap=8)
    d.notes(s, "Lista generada: los puntos desaparecen al existir tuning.md, "
               "lean-caso-real.md o una revisión humana rellenada.")


def s_closing(d: Deck) -> None:
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
    d.text(s, M + 0.4, 6.55, 10, 0.35, f"presentacion/ · commit {C.git_head()}", 11,
           color=MUTED)
    d.notes(s, "Frase de la entrega (≤ 3 líneas).")


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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-pdf", action="store_true")
    ap.add_argument("--render", action="store_true", help="force Mermaid re-render")
    ap.add_argument("--out", default=str(C.PRES / "presentacion.pptx"))
    a = ap.parse_args()
    C.render_all(force=a.render)
    d = Deck()
    for fn in (s_title, s_problem, s_demo1, s_demo2, s_arch, s_memory, s_validators,
               s_guardrails, s_lean, s_tla, s_tla_ce, s_langfuse, s_evals, s_redteam,
               s_claude_code, s_cost, s_tradeoffs, s_limits, s_closing):
        fn(d)
    out = Path(a.out)
    d.prs.save(out)
    print(f"wrote {out.relative_to(C.ROOT)} ({out.stat().st_size / 1e6:.1f} MB, {d.n} slides)")
    if not a.no_pdf:
        pdf = to_pdf(out)
        if pdf:
            print(f"wrote {pdf.relative_to(C.ROOT)}")


if __name__ == "__main__":
    main()

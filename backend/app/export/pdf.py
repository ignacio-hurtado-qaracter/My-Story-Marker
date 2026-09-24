"""The interactive PDF of one novel version (spec 014, AC 2; exam § 2 and E05).

Pure Python (reportlab). The document, in order:

1. **Portada**: title, "Para <recipient>", the personalised dedication.
2. **Novedades** (only when the version has a parent): the chapters changed against it,
   each an internal link to the chapter (R06).
3. **Índice**: every chapter as an internal link, changed ones marked (R01, R02).
4. The **chapters**, one per page run.
5. **Personajes y lugares**, from the story bible, each with links to the chapters where
   it appears (R03).

Every heading is also a PDF outline entry (bookmark), so a viewer's side panel navigates
the book as well. The read side is `app.reader.service`, the same the web reader uses.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import escape as _html_escape
from pathlib import Path
from typing import Final

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate,
    Flowable,
    Frame,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)

from app.bible import BibleNotFoundError, BibleRepository
from app.reader import service
from app.reader.models import BibleEntry

ACCENT: Final = HexColor("#E8590C")
INK: Final = HexColor("#1F1A17")
MUTED: Final = HexColor("#6B625C")

_BASE: Final = ParagraphStyle(
    "base", fontName="Times-Roman", fontSize=11, leading=15.5, textColor=INK
)
STYLES: Final[dict[str, ParagraphStyle]] = {
    "body": ParagraphStyle(
        "body", parent=_BASE, alignment=TA_JUSTIFY, firstLineIndent=5 * mm, spaceAfter=2
    ),
    "h1": ParagraphStyle(
        "h1",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=23,
        spaceBefore=6 * mm,
        spaceAfter=6 * mm,
    ),
    "h2": ParagraphStyle(
        "h2",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=12.5,
        leading=16,
        spaceBefore=4 * mm,
        spaceAfter=1.5 * mm,
    ),
    "eyebrow": ParagraphStyle(
        "eyebrow",
        parent=_BASE,
        fontName="Helvetica",
        fontSize=8.5,
        textColor=ACCENT,
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    ),
    "title": ParagraphStyle(
        "title",
        parent=_BASE,
        fontName="Helvetica-Bold",
        fontSize=26,
        leading=31,
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    ),
    "to": ParagraphStyle(
        "to",
        parent=_BASE,
        fontName="Times-Italic",
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=6 * mm,
    ),
    "dedication": ParagraphStyle(
        "dedication",
        parent=_BASE,
        fontName="Times-Italic",
        fontSize=12,
        leading=17,
        alignment=TA_CENTER,
        textColor=MUTED,
    ),
    "label": ParagraphStyle(
        "label",
        parent=_BASE,
        fontName="Helvetica",
        fontSize=8.5,
        textColor=ACCENT,
        spaceBefore=4 * mm,
    ),
    "item": ParagraphStyle("item", parent=_BASE, fontSize=11.5, leading=18, leftIndent=2 * mm),
    "meta": ParagraphStyle("meta", parent=_BASE, fontSize=9.5, leading=13, textColor=MUTED),
}

_ANCHOR_COVER: Final = "portada"
_ANCHOR_NEWS: Final = "novedades"
_ANCHOR_INDEX: Final = "indice"
_ANCHOR_BIBLE: Final = "personajes-y-lugares"
_MODIFIED: Final = " <font color='#E8590C' size='8'>(modificado)</font>"


def escape(text: str) -> str:
    """Text for a reportlab paragraph, which parses a small XML-like markup."""
    return _html_escape(text, quote=False)


def chapter_anchor(n: int) -> str:
    return f"cap-{n}"


def note_lines(note: str | None) -> list[str]:
    """The version note for a reader: `{"change": {key, old, new}}` becomes
    "Cambio: <key>: «old» → «new»"; internal keys (`stop_reason`) are not shown; a note
    that is not JSON is shown as written."""
    if not note:
        return []
    try:
        data = json.loads(note)
    except json.JSONDecodeError:
        return [note]
    if not isinstance(data, dict):
        return [note]
    lines: list[str] = []
    change = data.get("change")
    if isinstance(change, dict) and {"key", "old", "new"} <= change.keys():
        lines.append(f"Cambio: {change['key']}: «{change['old']}» → «{change['new']}»")
    text = data.get("text")
    if isinstance(text, str) and text:
        lines.append(text)
    return lines


def pdf_filename(novel_id: str, version: int) -> str:
    """R07: the version is in the name, so the previous version's PDF is never replaced."""
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", novel_id).strip("-") or "novela"
    return f"{safe}-v{version}.pdf"


@dataclass(frozen=True, slots=True)
class _Mark:
    key: str
    title: str
    level: int


class _NovelDoc(BaseDocTemplate):
    """Registers a named destination and an outline entry after each marked flowable."""

    def __init__(self, filename: str, marks: dict[int, _Mark], **kwargs: object) -> None:
        super().__init__(filename, **kwargs)  # type: ignore[arg-type]  # reportlab's kwargs are untyped
        self._marks = marks

    def afterFlowable(self, flowable: Flowable) -> None:  # noqa: N802 - reportlab's hook name
        mark = self._marks.get(id(flowable))
        if mark is None:
            return
        canvas = self.canv
        canvas.bookmarkPage(mark.key, fit="FitH", top=self.pagesize[1])
        canvas.addOutlineEntry(mark.title, mark.key, level=mark.level, closed=False)


class _Builder:
    def __init__(self) -> None:
        self.story: list[Flowable] = []
        self.marks: dict[int, _Mark] = {}

    def add(self, flowable: Flowable, mark: _Mark | None = None) -> None:
        if mark is not None:
            self.marks[id(flowable)] = mark
        self.story.append(flowable)

    def para(self, text: str, style: str, mark: _Mark | None = None) -> None:
        self.add(Paragraph(text, STYLES[style]), mark)


def _link(anchor: str, label: str) -> str:
    return f'<link href="#{anchor}" color="#E8590C">{escape(label)}</link>'


def _paragraphs(text: str) -> list[str]:
    """Blank-line separated paragraphs; single newlines inside a paragraph are joined."""
    blocks = re.split(r"\n\s*\n", text.strip())
    cleaned = [" ".join(line.strip() for line in block.splitlines()).strip() for block in blocks]
    return [re.sub(r"^#+\s*", "", block) for block in cleaned if block]


def _footer(canvas: Canvas, doc: BaseDocTemplate) -> None:
    page = canvas.getPageNumber()
    if page == 1:
        canvas.showOutline()  # open the viewer's bookmark panel
        return
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(MUTED)
    canvas.drawCentredString(doc.pagesize[0] / 2, 9 * mm, str(page))
    canvas.restoreState()


def _entry_lines(entry: BibleEntry, titles: dict[int, str]) -> list[str]:
    lines: list[str] = []
    if entry.role:
        lines.append(f"<i>{escape(entry.role)}</i>")
    if entry.description:
        lines.append(escape(entry.description))
    if entry.chapters:
        links = ", ".join(
            _link(chapter_anchor(n), titles.get(n, f"Capítulo {n}")) for n in entry.chapters
        )
        lines.append(f"Aparece en: {links}")
    else:
        lines.append("<i>No aparece en ningún capítulo de esta versión.</i>")
    return lines


def export_pdf(
    repo: BibleRepository, novel_id: str, version: int | None, out_path: Path | str
) -> Path:
    """Write the PDF of `version` (the current published one when None) to `out_path`."""
    novel = repo.get_novel(novel_id)
    if version is None:
        version = service.current_version(repo, novel_id)
        if version is None:
            latest = repo.latest_version(novel_id)
            if latest is None:
                message = f"novel {novel_id!r} has no version to export"
                raise BibleNotFoundError(message)
            version = latest.version
    info = repo.get_version(novel_id, version)
    index = service.chapter_index(repo, novel_id, version)
    chapters = repo.list_chapters(novel_id, version)
    bible = service.story_bible(repo, novel_id, version)
    titles = {entry.n: entry.title for entry in index.chapters}
    title = novel.title or "Mi novela"

    b = _Builder()
    # 1. Cover.
    b.add(Spacer(1, 30 * mm), _Mark(_ANCHOR_COVER, "Portada", 0))
    b.para("NOVELA", "eyebrow")
    b.para(escape(title), "title")
    if novel.recipient_name:
        b.para(f"Para {escape(novel.recipient_name)}", "to")
    if novel.dedication:
        for block in _paragraphs(novel.dedication):
            b.para(escape(block), "dedication")
    b.add(Spacer(1, 20 * mm))
    b.para(f"Versión {version}", "eyebrow")
    b.add(PageBreak())

    # 2. Novedades (R06).
    if info.parent_version is not None:
        changed = [e for e in index.chapters if e.changed_vs_parent]
        b.para("Novedades", "h1", _Mark(_ANCHOR_NEWS, "Novedades", 0))
        b.para(
            f"Esta es la versión {version}, hecha a partir de la versión "
            f"{info.parent_version}. La versión anterior se conserva.",
            "meta",
        )
        for line in note_lines(info.note):
            b.para(escape(line), "meta")
        b.add(Spacer(1, 4 * mm))
        if changed:
            b.para("Capítulos modificados:", "h2")
            for entry in changed:
                b.para("• " + _link(chapter_anchor(entry.n), f"{entry.n}. {entry.title}"), "item")
        else:
            b.para("Ningún capítulo ha cambiado respecto a la versión anterior.", "item")
        b.add(PageBreak())

    # 3. Index (R01).
    b.para("Índice", "h1", _Mark(_ANCHOR_INDEX, "Índice", 0))
    for entry in index.chapters:
        mark = _MODIFIED if entry.changed_vs_parent else ""
        b.para(_link(chapter_anchor(entry.n), f"{entry.n}. {entry.title}") + mark, "item")
    b.add(Spacer(1, 3 * mm))
    b.para(_link(_ANCHOR_BIBLE, "Personajes y lugares"), "item")
    b.add(PageBreak())

    # 4. Chapters.
    for chapter in chapters:
        heading = f"{chapter.chapter}. {titles.get(chapter.chapter, '')}"
        b.para(escape(heading), "h1", _Mark(chapter_anchor(chapter.chapter), heading, 0))
        for block in _paragraphs(chapter.text):
            b.para(escape(block), "body")
        b.add(PageBreak())

    # 5. Characters and places (R03).
    b.para("Personajes y lugares", "h1", _Mark(_ANCHOR_BIBLE, "Personajes y lugares", 0))
    for label, entries in (("Personajes", bible.characters), ("Lugares", bible.places)):
        if not entries:
            continue
        b.para(label.upper(), "label")
        for sheet in entries:
            b.para(escape(sheet.name), "h2", _Mark(f"ficha-{sheet.id}", sheet.name, 1))
            for line in _entry_lines(sheet, titles):
                b.para(line, "meta")
    b.para(_link(_ANCHOR_INDEX, "Volver al índice"), "meta")

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    doc = _NovelDoc(
        str(target),
        b.marks,
        pagesize=A5,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=16 * mm,
        bottomMargin=18 * mm,
        title=title,
        author="My Story Marker",
        subject=f"Versión {version}",
        lang="es-ES",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="body")
    doc.addPageTemplates([PageTemplate(id="page", frames=[frame], onPage=_footer)])
    doc.build(b.story)
    return target


__all__ = ["chapter_anchor", "export_pdf", "note_lines", "pdf_filename"]

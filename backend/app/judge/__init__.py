"""B7 — LLM-as-judge and human review (spec 011).

`register_validators()` registers `judge_chapter` (chapter_close) and `judge_novel`
(pre_publish) in the K3 registry. The pipeline imports it through `app.novel.setup`.
"""

from __future__ import annotations

from app.judge.rubric import CHAPTER_CRITERIA, NOVEL_CRITERIA, evaluate, render_markdown
from app.judge.validators import JudgeChapter, JudgeNovel
from app.validators import register


def register_validators() -> None:
    register(JudgeChapter())
    register(JudgeNovel())


__all__ = [
    "CHAPTER_CRITERIA",
    "NOVEL_CRITERIA",
    "JudgeChapter",
    "JudgeNovel",
    "evaluate",
    "register_validators",
    "render_markdown",
]

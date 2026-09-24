"""Two small gaps in K1 that the pipeline needs, kept in one place (spec 007, Open questions).

* **Plan storage.** The plan is stored as one planner-source fact, key `plan.v1`, kind
  `plan`, never mandatory. No migration is needed and the plan is written in one statement,
  so a crash leaves either the whole plan or none.
* **Rename.** K1 has no method to rename a character or a place; `change_fact` needs one
  when the changed fact is a name. `rename_cast` runs one UPDATE per table over the
  repository's own connection. To be replaced by a `BibleRepository` method (B1).
"""

from __future__ import annotations

from typing import Final

from app.bible import BibleRepository
from app.novel.models import NovelPlan

PLAN_KEY: Final[str] = "plan.v1"
PLAN_KIND: Final[str] = "plan"


def load_plan(repo: BibleRepository, novel_id: str) -> NovelPlan | None:
    fact = repo.find_fact(novel_id, PLAN_KEY)
    return None if fact is None else NovelPlan.model_validate_json(fact.value)


def store_plan(repo: BibleRepository, novel_id: str, plan: NovelPlan) -> None:
    payload = plan.model_dump_json()
    existing = repo.find_fact(novel_id, PLAN_KEY)
    if existing is None:
        repo.add_fact(
            novel_id, key=PLAN_KEY, value=payload, kind=PLAN_KIND, source="planner", mandatory=False
        )
    else:
        repo.update_fact_value(existing.id, payload)


def rename_cast(repo: BibleRepository, novel_id: str, old: str, new: str) -> int:
    """Rename every character and place of the novel whose name is exactly `old`."""
    if not old or old == new:
        return 0
    db = repo.connection
    changed = 0
    for table in ("character", "place"):
        # Table names come from the fixed tuple above, never from input.
        cursor = db.execute(
            f"update {table} set name = ? where novel_id = ? and name = ?",  # nosec B608
            (new, novel_id, old),
        )
        changed += cursor.rowcount
    return changed


__all__ = ["PLAN_KEY", "load_plan", "rename_cast", "store_plan"]

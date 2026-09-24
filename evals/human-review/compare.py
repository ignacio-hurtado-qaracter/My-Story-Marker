"""Human review vs LLM judge (spec 011). Thin wrapper over `app.judge.compare`.

cd backend && uv run python ../evals/human-review/compare.py REVIEW.yaml [--db PATH]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

from app.judge.compare import main  # after the sys.path insert above

if __name__ == "__main__":
    raise SystemExit(main())

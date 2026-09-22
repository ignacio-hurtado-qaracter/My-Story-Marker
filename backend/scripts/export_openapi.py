"""Export the OpenAPI document of the app (IF-08).

    uv run python scripts/export_openapi.py            # write backend/openapi.json
    uv run python scripts/export_openapi.py --check    # exit 1 if the committed file is stale

Deliberately the same shape and the same two options as `export_schemas.py`, because they
answer the same question about two halves of one contract: that one exports what a store
file must look like, this one exports what the HTTP surface promises.

`--check` is a gate stage rather than a convenience. The frontend's client is generated from
this document, so a route or a model changed without regenerating it is a contract change
that nobody reviewed and a client that is wrong in a way no test in this repository can see.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.main import create_app


def openapi_path() -> Path:
    """`backend/openapi.json`, beside `schemas/` and committed like it."""
    return Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    """One canonical rendering, so `--check` compares content and not formatting.

    `sort_keys` matters more here than in `export_schemas.py`: FastAPI builds the document by
    walking the routes and the models it reaches, so the insertion order of `paths` and
    `components` follows mount order and would turn a reordered `include_router` call into a
    diff that says nothing.
    """
    document = create_app().openapi()
    return json.dumps(document, indent=2, sort_keys=True) + "\n"


def stale() -> bool:
    """True when the committed document is missing or no longer matches the app."""
    path = openapi_path()
    return not path.is_file() or path.read_text(encoding="utf-8") != render()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="do not write; exit 1 if the committed openapi.json is stale",
    )
    args = parser.parse_args(argv)

    path = openapi_path()

    if args.check:
        if stale():
            print(f"stale OpenAPI document (run without --check to regenerate): {path.name}")
            return 1
        print(f"{path.name} is up to date")
        return 0

    document = render()
    path.write_text(document, encoding="utf-8")
    print(f"wrote {path} ({len(document)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""`uv run python -m app.mcp_server` — the read-only MCP server over stdio (spec 017).

`--http PORT` serves streamable HTTP on 127.0.0.1 instead (for MCP Inspector's URL mode).
"""

from __future__ import annotations

import argparse

from app.mcp_server.server import build_server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m app.mcp_server")
    parser.add_argument("--http", type=int, metavar="PORT", help="serve HTTP on this port")
    args = parser.parse_args(argv)
    server = build_server()
    if args.http:
        server.run(transport="http", host="127.0.0.1", port=args.http, show_banner=False)
    else:
        server.run(transport="stdio", show_banner=False)


if __name__ == "__main__":
    main()

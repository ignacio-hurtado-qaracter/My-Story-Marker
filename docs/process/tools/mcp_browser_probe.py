"""Drive the Playwright MCP server over stdio JSON-RPC and inspect the web reader.

Evidence for docs/process/browser-mcp-log.md (exam K06/V05). Standard library only.

It starts the same server `.mcp.json` declares (`npx -y @playwright/mcp@latest --headless
--isolated --browser chromium`), sends `initialize` and `tools/list`, then for every page of
the reader calls `browser_navigate`, `browser_snapshot`, `browser_take_screenshot` and a few
`browser_evaluate` probes (title, dedication, links, horizontal overflow). Everything the
server answers is written to a JSON transcript; the screenshots land in --out.

    PLAYWRIGHT_MCP_EXECUTABLE_PATH=/path/to/chrome \\
    python docs/process/tools/mcp_browser_probe.py \\
        --base http://127.0.0.1:5183 --novel demo-faro \\
        --out frontend/screenshots/browser-mcp --transcript /tmp/probe.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

PROBE_JS = """() => {
  const vis = (el) => !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  const links = [...document.querySelectorAll('a[href]')].filter(vis).map(a => ({
    text: a.innerText.trim().slice(0, 80), href: a.getAttribute('href') }));
  const doc = document.documentElement;
  const wide = [...document.querySelectorAll('body *')]
    .filter(el => vis(el) && el.getBoundingClientRect().right > doc.clientWidth + 1)
    .slice(0, 5).map(el => el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''));
  const imgsNoAlt = [...document.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).length;
  return {
    title: document.title,
    h1: [...document.querySelectorAll('h1')].map(h => h.innerText.trim()),
    h2: [...document.querySelectorAll('h2')].map(h => h.innerText.trim()).slice(0, 20),
    text_head: document.body.innerText.trim().slice(0, 600),
    links,
    scroll_width: doc.scrollWidth, client_width: doc.clientWidth,
    overflowing: wide, imgs_without_alt: imgsNoAlt,
    lang: doc.lang,
  };
}"""


class McpClient:
    def __init__(self, cmd: list[str], env: dict[str, str]) -> None:
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=env, text=True, bufsize=1,
        )
        self.next_id = 0

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self.next_id += 1
        msg = {"jsonrpc": "2.0", "id": self.next_id, "method": method, "params": params or {}}
        assert self.proc.stdin is not None and self.proc.stdout is not None
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        while True:
            line = self.proc.stdout.readline()
            if not line:
                err = self.proc.stderr.read() if self.proc.stderr else ""
                raise RuntimeError(f"server closed the stream: {err[-2000:]}")
            data = json.loads(line)
            if data.get("id") == self.next_id:
                return data  # notifications and other ids are skipped

    def notify(self, method: str) -> None:
        assert self.proc.stdin is not None
        self.proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self.proc.stdin.flush()

    def call(self, tool: str, **arguments: Any) -> dict[str, Any]:
        return self.request("tools/call", {"name": tool, "arguments": arguments})

    def close(self) -> None:
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


def text_of(response: dict[str, Any]) -> str:
    content = response.get("result", {}).get("content", [])
    return "\n".join(c.get("text", "") for c in content if c.get("type") == "text")


def evaluate(client: McpClient) -> Any:
    raw = text_of(client.call("browser_evaluate", function=PROBE_JS))
    # The server answers with a Markdown section "### Result" followed by the JSON value.
    start = raw.find("{")
    try:
        value, _end = json.JSONDecoder().raw_decode(raw[start:])
    except (ValueError, json.JSONDecodeError):
        return {"unparsed": raw[:2000]}
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5173")
    parser.add_argument("--novel", default="demo-faro")
    parser.add_argument("--out", default="frontend/screenshots/browser-mcp")
    parser.add_argument("--transcript", default="browser-mcp-transcript.json")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--prefix", default="")
    parser.add_argument("--watch", action="append", default=[],
                        help="reader path to reload N times, recording text at 0.3 s and 3 s")
    parser.add_argument("--repeat", type=int, default=5)
    args = parser.parse_args()

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["npx", "-y", "@playwright/mcp@latest", "--headless", "--isolated",
           "--browser", "chromium", "--output-dir", str(out)]
    client = McpClient(cmd, dict(os.environ))
    log: dict[str, Any] = {"command": cmd, "base": args.base, "novel": args.novel, "steps": []}
    try:
        init = client.request("initialize", {
            "protocolVersion": "2025-06-18", "capabilities": {},
            "clientInfo": {"name": "mcp_browser_probe", "version": "1"},
        })
        client.notify("notifications/initialized")
        log["server"] = init.get("result", {}).get("serverInfo")
        tools = client.request("tools/list")
        log["tools"] = [t["name"] for t in tools.get("result", {}).get("tools", [])]
        client.call("browser_resize", width=args.width, height=args.height)

        base = f"{args.base}/novelas/{args.novel}"
        for path in args.watch:
            for i in range(args.repeat):
                client.call("browser_navigate", url=f"{base}{path}")
                early = evaluate(client)
                time.sleep(3.0)
                late = evaluate(client)
                console = text_of(client.call("browser_console_messages", level="error"))
                log.setdefault("watch", []).append({
                    "path": path, "try": i, "early_h1": early.get("h1"),
                    "early_text": str(early.get("text_head", ""))[-200:],
                    "late_h1": late.get("h1"),
                    "errors_500": console.count("status of 500"),
                })
                print(f"watch {path} #{i}: early={early.get('h1')} late={late.get('h1')} "
                      f"500s={console.count('status of 500')}", file=sys.stderr)
        if args.watch:
            return 0
        pages = [("cover", base), ("index", f"{base}/indice"),
                 ("chapter-1", f"{base}/capitulos/1"), ("personajes", f"{base}/personajes"),
                 ("index-v1", f"{base}/indice?v=1"), ("chapter-1-v1", f"{base}/capitulos/1?v=1"),
                 ("personajes-v1", f"{base}/personajes?v=1")]
        for name, url in pages:
            t0 = time.time()
            nav = text_of(client.call("browser_navigate", url=url))
            time.sleep(1.5)  # let the data queries settle
            snap = text_of(client.call("browser_snapshot"))
            probe = evaluate(client)
            shot_name = str(out / f"{args.prefix}{name}.png")
            shot = text_of(client.call("browser_take_screenshot", filename=shot_name, fullPage=True))
            console = text_of(client.call("browser_console_messages"))
            log["steps"].append({
                "page": name, "url": url, "seconds": round(time.time() - t0, 1),
                "navigate": nav[:1500], "snapshot": snap[:6000], "probe": probe,
                "screenshot": shot[:500], "console": console[:2000],
            })
            print(f"{name}: title={probe.get('title')!r} h1={probe.get('h1')} "
                  f"links={len(probe.get('links', []))} scroll={probe.get('scroll_width')}/"
                  f"{probe.get('client_width')}", file=sys.stderr)
        # Every chapter link found on the index and the sheets page must land on a chapter.
        targets = sorted({
            link["href"] for step in log["steps"] if step["page"] in ("index", "personajes")
            for link in step["probe"].get("links", []) if "/capitulos/" in link["href"]
        })
        for href in targets:
            client.call("browser_navigate", url=f"{args.base}{href}")
            time.sleep(1.0)
            probe = evaluate(client)
            log.setdefault("link_checks", []).append({
                "href": href, "title": probe.get("title"), "h1": probe.get("h1"),
                "error_text": "error" in str(probe.get("text_head", "")).lower()
                or "no encontr" in str(probe.get("text_head", "")).lower(),
            })
            print(f"link {href}: h1={probe.get('h1')}", file=sys.stderr)
    finally:
        client.close()
        Path(args.transcript).write_text(json.dumps(log, ensure_ascii=False, indent=2), "utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

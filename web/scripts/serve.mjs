#!/usr/bin/env node
// Dev server for web/: serves the static site and rebuilds the library index from
// books/ on demand, so the Biblioteca always reflects what is on disk.
// No dependencies. Usage: `node web/scripts/serve.mjs [port]` (default 8080).

import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildIndex, asScript } from './build-data.mjs';

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, '..');
const port = Number(process.argv[2] ?? process.env.PORT ?? 8080);

const MIME = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.jpg': 'image/jpeg', '.ico': 'image/x-icon', '.md': 'text/markdown; charset=utf-8',
};
const NO_CACHE = { 'Cache-Control': 'no-store' };

// Rebuild at most once per second: the page polls every few seconds and the harness
// may write several files in a burst.
let cache = { at: 0, index: null };
async function freshIndex() {
  if (Date.now() - cache.at > 1000) cache = { at: Date.now(), index: await buildIndex() };
  return cache.index;
}

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);
    let pathname = decodeURIComponent(url.pathname);
    if (pathname === '/') pathname = '/index.html';

    // Library data: always generated live from books/.
    if (pathname === '/data/books.json' || pathname === '/data/books.js') {
      const index = await freshIndex();
      const isJs = pathname.endsWith('.js');
      res.writeHead(200, { 'Content-Type': MIME[isJs ? '.js' : '.json'], ...NO_CACHE });
      res.end(isJs ? asScript(index) : JSON.stringify(index));
      return;
    }

    const file = path.resolve(webRoot, '.' + pathname);
    if (!file.startsWith(webRoot)) { res.writeHead(403); res.end('forbidden'); return; }
    const st = await stat(file).catch(() => null);
    if (!st || !st.isFile()) { res.writeHead(404); res.end('not found'); return; }
    res.writeHead(200, { 'Content-Type': MIME[path.extname(file)] ?? 'application/octet-stream', ...NO_CACHE });
    res.end(await readFile(file));
  } catch (e) {
    res.writeHead(500, { 'Content-Type': 'text/plain' });
    res.end(String(e));
  }
});

server.listen(port, () => {
  console.log(`My-Story-Maker → http://localhost:${port}  (library data rebuilt live from books/)`);
});

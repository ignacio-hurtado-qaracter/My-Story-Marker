#!/usr/bin/env node
// Scans books/<slug>/ and writes web/data/books.json for the Biblioteca page.
// No dependencies. Run from anywhere: `node web/scripts/build-data.mjs [booksDir]`.

import { readdir, readFile, stat, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(here, '..', '..');
const defaultBooksDir = path.resolve(repoRoot, 'books');
const outFile = path.resolve(here, '..', 'data', 'books.json');

// ---------- minimal YAML (mappings, sequences, scalars, > and | blocks) ----------
function parseYaml(text) {
  const lines = text.split(/\r?\n/).filter((l) => !/^\s*#/.test(l) && l.trim() !== '');
  let i = 0;

  const indentOf = (l) => l.match(/^ */)[0].length;

  function scalar(raw) {
    const v = raw.trim();
    if (v === '' || v === 'null' || v === '~') return null;
    if (v === 'true') return true;
    if (v === 'false') return false;
    if (/^-?\d+(\.\d+)?$/.test(v)) return Number(v);
    if (v.startsWith('[') && v.endsWith(']')) {
      return v.slice(1, -1).split(',').map((s) => s.trim().replace(/^["']|["']$/g, '')).filter(Boolean);
    }
    return v.replace(/^["']|["']$/g, '');
  }

  function block(indent, style) {
    const parts = [];
    while (i < lines.length && indentOf(lines[i]) > indent) parts.push(lines[i++].trim());
    return style === '>' ? parts.join(' ') : parts.join('\n');
  }

  function parseNode(indent) {
    if (i >= lines.length) return null;
    const line = lines[i];
    if (/^\s*- /.test(line)) return parseSeq(indentOf(line));
    return parseMap(indentOf(line));
  }

  function parseMap(indent) {
    const obj = {};
    while (i < lines.length) {
      const line = lines[i];
      const ind = indentOf(line);
      if (ind < indent || /^\s*- /.test(line)) break;
      if (ind > indent) { i++; continue; }
      const m = line.match(/^\s*([^:]+):\s*(.*)$/);
      if (!m) { i++; continue; }
      const [, key, rest] = m;
      i++;
      if (rest === '>' || rest === '|') obj[key.trim()] = block(indent, rest);
      else if (rest.trim() === '') obj[key.trim()] = i < lines.length && indentOf(lines[i]) > indent ? parseNode(indentOf(lines[i])) : null;
      else obj[key.trim()] = scalar(rest);
    }
    return obj;
  }

  function parseSeq(indent) {
    const arr = [];
    while (i < lines.length) {
      const line = lines[i];
      const ind = indentOf(line);
      if (ind < indent || !/^\s*- /.test(line)) break;
      if (ind > indent) { i++; continue; }
      // Turn "- key: value" into a map whose first line is at indent+2.
      const inner = line.replace(/^(\s*)- /, '$1  ');
      lines[i] = inner;
      if (/^\s*[^:]+:\s*/.test(inner)) arr.push(parseMap(indentOf(inner)));
      else { arr.push(scalar(inner)); i++; }
    }
    return arr;
  }

  return parseNode(0);
}

function yamlBlock(md) {
  const m = md.match(/```ya?ml\s*\n([\s\S]*?)```/);
  return m ? m[1] : null;
}

// ---------- helpers ----------
async function readIf(p) {
  return existsSync(p) ? readFile(p, 'utf8') : null;
}

function wordCount(md) {
  return md ? md.split(/\s+/).filter(Boolean).length : 0;
}

function paragraphCount(md) {
  return md
    ? md.split(/\r?\n\s*\r?\n/).filter((p) => p.trim() && !p.trim().startsWith('#') && !p.trim().startsWith('<!--')).length
    : 0;
}

function chapterHeadings(md) {
  return md ? [...md.matchAll(/^# (.+)$/gm)].map((m) => m[1].trim()) : [];
}

async function listMd(dir) {
  if (!existsSync(dir)) return [];
  const files = (await readdir(dir)).filter((f) => f.endsWith('.md')).sort();
  return Promise.all(files.map(async (f) => ({ file: f, markdown: await readFile(path.join(dir, f), 'utf8') })));
}

// ---------- main ----------
async function buildBook(booksDir, slug) {
  const dir = path.join(booksDir, slug);
  const st = await stat(dir);
  if (!st.isDirectory()) return null;

  const runRaw = await readIf(path.join(dir, 'run.json'));
  const run = runRaw ? JSON.parse(runRaw) : null;
  const spiritMd = await readIf(path.join(dir, 'spirit.md'));
  const charactersMd = await readIf(path.join(dir, 'characters.md'));
  const novelMd = await readIf(path.join(dir, 'novel.md'));
  const metricsRaw = await readIf(path.join(dir, 'metrics.jsonl'));

  let spirit = null;
  let characters = null;
  try { const y = spiritMd && yamlBlock(spiritMd); spirit = y ? parseYaml(y)?.spirit ?? null : null; } catch { spirit = null; }
  try { const y = charactersMd && yamlBlock(charactersMd); characters = y ? parseYaml(y)?.characters ?? null : null; } catch { characters = null; }

  const metrics = metricsRaw
    ? metricsRaw.split(/\r?\n/).filter(Boolean).map((l) => { try { return JSON.parse(l); } catch { return null; } }).filter(Boolean)
    : [];

  const summaries = await listMd(path.join(dir, 'summaries'));
  const manuscript = await listMd(path.join(dir, 'manuscript'));
  const manuscriptStats = manuscript.map((m) => ({
    file: m.file,
    fragments: (m.markdown.match(/<!--\s*fragment:/g) ?? []).length,
    paragraphs: paragraphCount(m.markdown),
  }));

  const approved = metrics.filter((m) => m.approved).length;
  const checks = ['main_thread', 'current_chapter', 'characters', 'pacing'];
  const checkFails = Object.fromEntries(checks.map((c) => [c, metrics.filter((m) => m.checks?.[c] === 'fail').length]));

  return {
    slug,
    title: run?.novel?.title ?? spirit?.title ?? slug,
    status: run?.status ?? (novelMd ? 'complete' : 'unknown'),
    language: run?.config_snapshot?.language ?? null,
    model: run?.config_snapshot?.model ?? null,
    createdAt: st.birthtime?.toISOString?.() ?? st.mtime.toISOString(),
    updatedAt: st.mtime.toISOString(),
    premise: spirit?.premise ?? null,
    tone_and_style: spirit?.tone_and_style ?? null,
    main_thread: spirit?.main_thread ?? null,
    chapters: spirit?.chapters ?? null,
    chapterTitles: chapterHeadings(novelMd),
    characters,
    config: run?.config_snapshot ?? null,
    totals: run?.totals ?? null,
    counters: run?.counters ?? null,
    position: run?.position ?? null,
    stats: {
      words: wordCount(novelMd),
      paragraphs: paragraphCount(novelMd),
      chapters: chapterHeadings(novelMd).length,
      verdicts: metrics.length,
      approved,
      rejected: metrics.length - approved,
      checkFails,
      manuscript: manuscriptStats,
    },
    metrics,
    summaries,
    raw: {
      spirit: spiritMd,
      characters: charactersMd,
      novel: novelMd,
      run: run,
    },
    hasNovel: Boolean(novelMd),
  };
}

/** Builds the library index from books/ and returns it (does not write). */
export async function buildIndex(booksDir = defaultBooksDir) {
  if (!existsSync(booksDir)) throw new Error(`books dir not found: ${booksDir}`);
  const slugs = (await readdir(booksDir)).sort();
  const books = (await Promise.all(slugs.map((slug) => buildBook(booksDir, slug)))).filter(Boolean);
  books.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
  return { generatedAt: new Date().toISOString(), books };
}

/** Same data as a classic script so library.html works when opened via file://. */
export function asScript(index) {
  return `// Generated by scripts/build-data.mjs. Do not edit.\nwindow.__BOOKS__ = ${JSON.stringify(index)};\n`;
}

/** Builds the index and writes data/books.json + data/books.js. */
export async function buildAndWrite({ quiet = false, booksDir = defaultBooksDir } = {}) {
  const index = await buildIndex(booksDir);
  await mkdir(path.dirname(outFile), { recursive: true });
  await writeFile(outFile, JSON.stringify(index, null, 2) + '\n', 'utf8');
  const jsFile = outFile.replace(/\.json$/, '.js');
  await writeFile(jsFile, asScript(index), 'utf8');
  if (!quiet) {
    console.log(`wrote ${path.relative(repoRoot, outFile)} + ${path.basename(jsFile)} · ${index.books.length} book(s): ${index.books.map((b) => b.slug).join(', ')}`);
  }
  return index;
}

// Run only when executed directly (`node build-data.mjs`), not when imported by serve.mjs.
const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const positional = process.argv.slice(2).filter((a) => !a.startsWith('--'));
  const booksDir = positional[0] ? path.resolve(repoRoot, positional[0]) : defaultBooksDir;
  buildAndWrite({ quiet: process.argv.includes('--quiet'), booksDir }).catch((e) => { console.error(e); process.exit(1); });
}

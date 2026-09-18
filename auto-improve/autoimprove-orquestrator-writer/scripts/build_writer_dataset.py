"""Build the `writer-contexts` dataset from a finished novel folder.

Deterministic, no model calls, no third-party packages. See spec §3.1.

    python build_writer_dataset.py [--book books/el-custodio-de-aurora] [--out dataset/writer-contexts.jsonl]

One item per approved fragment, describing the run state *just before* that fragment
was written, plus three fault-injection items for invariant I8.
"""
from __future__ import annotations

import argparse
import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

MARKER = re.compile(r'<!--\s*fragment:\s*(\S+)\s+beats_completed=(\[[^\]]*\])\s*-->')
BEAT = re.compile(r'^(\s*)- id: "(\d+\.\d+)"\s*$')
CHAPTER = re.compile(r'^    - id: (\d+)\s*$')


def paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r'\n\s*\n', text.strip()) if p.strip()]


def parse_manuscript(book: Path) -> list[dict]:
    """Ordered approved fragments across all chapter files."""
    frags = []
    for f in sorted((book / 'manuscript').glob('chapter-*.md')):
        chapter = int(f.stem.split('-')[1])
        text = io.open(f, encoding='utf-8').read()
        parts = MARKER.split(text)  # [pre, id, beats, body, id, beats, body, ...]
        for i in range(1, len(parts), 3):
            frags.append({
                'chapter': chapter,
                'marker_id': parts[i],
                'beats_completed': json.loads(parts[i + 1]),
                'paragraphs': paragraphs(parts[i + 2]),
            })
    return frags


def spirit_slices(spirit_text: str) -> tuple[str, str, dict[int, dict]]:
    """Return (tone_and_style, main_thread block, {chapter: {block, title, target, beats}})."""
    lines = spirit_text.splitlines()
    tone = folded_value(lines, '  tone_and_style:')
    mt_start = next(i for i, l in enumerate(lines) if l.startswith('  main_thread:'))
    ch_start = next(i for i, l in enumerate(lines) if l.startswith('  chapters:'))
    main_thread = '\n'.join(lines[mt_start:ch_start]).rstrip()

    chapters: dict[int, dict] = {}
    starts = [i for i, l in enumerate(lines) if CHAPTER.match(l)]
    end_all = next((i for i, l in enumerate(lines) if l.startswith('  current_chapter_id')), len(lines))
    for n, s in enumerate(starts):
        e = starts[n + 1] if n + 1 < len(starts) else end_all
        block = lines[s:e]
        cid = int(CHAPTER.match(lines[s]).group(1))
        title = next((l.split(':', 1)[1].strip().strip('"') for l in block if l.strip().startswith('title:')), '')
        target = next((int(l.split(':', 1)[1]) for l in block if l.strip().startswith('target_paragraphs:')), None)
        beats = []
        for j, l in enumerate(block):
            m = BEAT.match(l)
            if m:
                beats.append({'id': m.group(2), 'description': folded_value(block[j:], 'description:')})
        chapters[cid] = {'block': '\n'.join(block).rstrip(), 'title': title, 'target': target, 'beats': beats}
    return tone, main_thread, chapters


def folded_value(lines: list[str], key: str) -> str:
    """Value of the first `key: >` folded scalar (or inline value) found in lines."""
    for i, l in enumerate(lines):
        if l.strip().startswith(key.strip()):
            inline = l.split(':', 1)[1].strip()
            if inline and inline != '>':
                return inline.strip('"')
            indent = len(l) - len(l.lstrip())
            out = []
            for m in lines[i + 1:]:
                if m.strip() == '':
                    continue
                if len(m) - len(m.lstrip()) <= indent:
                    break
                out.append(m.strip())
            return ' '.join(out)
    return ''


def build(book: Path, recent_n: int, distant_m: int, fmin: int, fmax: int, language: str) -> list[dict]:
    slug = book.name
    frags = parse_manuscript(book)
    tone, main_thread, chapters = spirit_slices(io.open(book / 'spirit.md', encoding='utf-8').read())
    characters = io.open(book / 'characters.md', encoding='utf-8').read().strip()

    items = []
    approved_so_far: list[str] = []          # every approved paragraph, in order
    per_chapter_index: dict[int, int] = {}
    done_beats: dict[int, set] = {}
    for fr in frags:
        c = fr['chapter']
        idx = per_chapter_index.get(c, 0) + 1
        per_chapter_index[c] = idx
        done = done_beats.setdefault(c, set())
        ch = chapters[c]
        future = [b for b in ch['beats'] if b['id'] not in done]
        recent = approved_so_far[-recent_n:] if approved_so_far else []
        distant = []
        for pc in range(max(1, c - distant_m), c):
            p = book / 'summaries' / f'chapter-{pc:02d}.md'
            if p.exists():
                distant.append({'chapter': pc, 'summary': io.open(p, encoding='utf-8').read().strip()})
        item = {
            'id': f'{slug.split("-")[-1]}-c{c:02d}-f{idx}',
            'source': {'book': slug, 'marker_id': fr['marker_id']},
            'chapter_id': c,
            'fragment_index': idx,
            'fault': None,
            'spirit_view': {
                'main_thread': main_thread,
                'chapter': {'id': c, 'title': ch['title'], 'block': ch['block']},
                'characters': characters,
                'characters_state': 'final',   # known simplification, spec §6
            },
            'recent': recent,
            'distant': distant,
            'future': [{'id': b['id'], 'status': 'current' if k == 0 else 'pending', 'description': b['description']}
                       for k, b in enumerate(future)],
            'budget': {
                'paragraphs_approved_in_chapter': sum(len(f['paragraphs']) for f in frags
                                                      if f['chapter'] == c and frags.index(f) < frags.index(fr)),
                'target_paragraphs': ch['target'],
                'beats_not_done': len(future),
            },
            'constraints': {'language': language, 'tone_and_style': tone,
                            'min_paragraphs': fmin, 'max_paragraphs': fmax},
            'expected': {
                'recent_verbatim': '\n\n'.join(recent),
                'valid_beat_ids': [b['id'] for b in future],
                'min_paragraphs': fmin, 'max_paragraphs': fmax,
                'error': None,
                'reference_fragment': '\n\n'.join(fr['paragraphs']),   # what Sonnet wrote here; not a target
            },
        }
        items.append(item)
        approved_so_far.extend(fr['paragraphs'])
        done.update(fr['beats_completed'])
    return items


def add_faults(items: list[dict]) -> list[dict]:
    """Three fault-injection items for I8 (spec §3.1 step 3)."""
    by_id = {it['id']: it for it in items}
    faults = []
    picks = [('c02-f2', 'recent_abridged'), ('c04-f1', 'recent_missing'), ('c05-f3', 'constraints_missing')]
    for suffix, fault in picks:
        src = next(it for it in items if it['id'].endswith(suffix))
        it = json.loads(json.dumps(src))
        it['id'] = f'{src["id"]}-fault-{fault}'
        it['fault'] = fault
        if fault == 'recent_abridged':
            first = src['recent'][0][:80] if src['recent'] else ''
            it['recent'] = [f'{first}... [{len(src["recent"])} párrafos anteriores]']
            it['expected']['error'] = 'recent_context_incomplete'
        elif fault == 'recent_missing':
            it['recent'] = None
            it['expected']['error'] = 'recent_context_incomplete'
        else:
            it['constraints'] = None
            it['expected']['error'] = 'constraints_missing'
        faults.append(it)
    return items + faults


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--book', default=str(REPO / 'books' / 'el-custodio-de-aurora'))
    ap.add_argument('--out', default=str(HERE.parent / 'dataset' / 'writer-contexts.jsonl'))
    args = ap.parse_args()
    book = Path(args.book)
    cfg = json.load(io.open(book / 'run.json', encoding='utf-8'))['config_snapshot']
    items = build(book,
                  recent_n=cfg['context']['recent_paragraphs'],
                  distant_m=cfg['context']['distant_chapters'],
                  fmin=cfg['fragment']['min_paragraphs'],
                  fmax=cfg['fragment']['max_paragraphs'],
                  language=cfg['language'])
    items = add_faults(items)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with io.open(out, 'w', encoding='utf-8', newline='\n') as fh:
        for it in items:
            fh.write(json.dumps(it, ensure_ascii=False) + '\n')
    n_fault = sum(1 for it in items if it['fault'])
    print(f'{len(items)} items ({len(items) - n_fault} real + {n_fault} fault) -> {out}')
    for it in items:
        print(f"  {it['id']:38} recent={len(it['recent'] or []):d} future={len(it['future'])} "
              f"budget={it['budget']['paragraphs_approved_in_chapter']}/{it['budget']['target_paragraphs']} "
              f"distant={len(it['distant'])}")


if __name__ == '__main__':
    main()

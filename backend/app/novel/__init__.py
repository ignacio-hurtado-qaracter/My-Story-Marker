"""The gift-novel generation pipeline (spec 007, block B3, contract K4).

from app.novel.pipeline import generate, change_fact

`generate(repo, novel_id)` plans once, writes each chapter scene by scene (writer), polishes
it (editor), validates it at the hook points and checkpoints it, then publishes; run again,
it resumes at the first incomplete chapter. `change_fact` regenerates only the chapters
that use one fact, into a new version. CLI: `python -m app.novel.cli`.
"""

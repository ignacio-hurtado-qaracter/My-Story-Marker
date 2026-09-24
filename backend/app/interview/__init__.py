"""Interview and brief (spec 006, block B2).

from app.interview.brief import Brief, validate_brief
from app.interview.service import ingest_brief

`brief` is the contract shape and its validation; `extract` the untrusted free-text path;
`interviewer` the conversational agent; `service` the ingest into the story bible (K1);
`router` and `cli` the two front doors.
"""

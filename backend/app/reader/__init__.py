"""The reader (spec 014, contract K5): read models over the story bible, the `/novels`
routes, the change-request jobs and the pre-publish visual check.

`app.reader.router.router` is mounted by `app.main`; `app.reader.visual_check` exposes
`register_validators()` for the pipeline's `register_all()`.
"""

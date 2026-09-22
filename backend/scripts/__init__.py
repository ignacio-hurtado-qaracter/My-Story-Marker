"""Developer scripts. Not part of the application package.

They live outside `app/` on purpose: `export_schemas.py` is the one place that knows every
store document type at once, including the feature-owned ones, and a module inside
`app/commons/` that imported `app.canon` would break the NFR-04 contract that `commons/`
knows no feature's name.
"""

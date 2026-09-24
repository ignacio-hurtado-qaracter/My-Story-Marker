"""`schema_role_output` and `schema_brief` — V04 (spec 008 / AC 5).

**schema_role_output** (``scene_accept``) reports, as a named validator, the schema check
the pipeline already performs on each role's structured output. ``ctx.extra["role_output"]``
is either a pydantic model instance (re-validated from its dump) or a mapping validated
against ``ctx.extra["role_output_model"]`` (a pydantic model class). Absent → pass.

**schema_brief** (``pre_publish``) validates the stored brief against, in order:
``app.interview.brief.Brief`` (block B2, imported guarded), else the JSON Schema
``backend/schemas/brief.v1.json`` if present (and ``jsonschema`` importable), else a
skipped pass that says so.
"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Final

from pydantic import BaseModel, ValidationError

from app.validators.protocol import ValidationContext, ValidationPoint, ValidationResult

BRIEF_SCHEMA: Final = Path(__file__).resolve().parents[3] / "schemas" / "brief.v1.json"


def _pydantic_errors(error: ValidationError) -> list[str]:
    return [
        f"{'.'.join(str(p) for p in item['loc']) or '<raíz>'}: {item['msg']}"
        for item in error.errors()[:10]
    ]


def _brief_model() -> type[BaseModel] | None:
    try:
        module = importlib.import_module("app.interview.brief")
    except ImportError:
        return None
    model = getattr(module, "Brief", None)
    return model if isinstance(model, type) and issubclass(model, BaseModel) else None


def _jsonschema() -> ModuleType | None:
    """`jsonschema` is only a transitive dependency here, so it is imported guarded."""
    try:
        return importlib.import_module("jsonschema")
    except ImportError:
        return None


@dataclass(frozen=True, slots=True)
class SchemaRoleOutput:
    name: str = "schema_role_output"
    point: ValidationPoint = ValidationPoint.SCENE_ACCEPT

    def run(self, ctx: ValidationContext) -> ValidationResult:
        output = ctx.extra.get("role_output")
        role = str(ctx.extra.get("feedback_role") or "el rol")
        if output is None:
            return ValidationResult(self.name, True, None, [], "Sin salida de rol que validar.")
        model: type[BaseModel] | None
        data: object
        if isinstance(output, BaseModel):
            model, data = type(output), output.model_dump(mode="json")
        else:
            candidate = ctx.extra.get("role_output_model")
            model = (
                candidate
                if isinstance(candidate, type) and issubclass(candidate, BaseModel)
                else None
            )
            data = output
        if model is None:
            return ValidationResult(
                self.name,
                True,
                None,
                ["sin modelo pydantic (role_output_model)"],
                "La salida no trae modelo con el que validarla; se acepta sin comprobar.",
            )
        try:
            model.model_validate(data)
        except ValidationError as error:
            return ValidationResult(
                self.name,
                False,
                0.0,
                _pydantic_errors(error),
                f"La salida de {role} no cumple el esquema {model.__name__}: corrige los "
                "campos indicados y devuelve solo el objeto válido.",
            )
        return ValidationResult(
            self.name, True, 1.0, [model.__name__], f"Salida conforme a {model.__name__}."
        )


@dataclass(frozen=True, slots=True)
class SchemaBrief:
    name: str = "schema_brief"
    point: ValidationPoint = ValidationPoint.PRE_PUBLISH

    def run(self, ctx: ValidationContext) -> ValidationResult:
        stored = ctx.repo.get_brief(ctx.novel_id)
        if stored is None:
            return ValidationResult(
                self.name, False, 0.0, ["no hay brief guardado"], "La novela no tiene brief."
            )
        data: Mapping[str, object] = stored.data
        model = _brief_model()
        if model is not None:
            try:
                model.model_validate(data)
            except ValidationError as error:
                return ValidationResult(
                    self.name,
                    False,
                    0.0,
                    _pydantic_errors(error),
                    "El brief guardado no cumple el modelo Brief; la entrevista debe "
                    "completar o corregir los campos indicados.",
                )
            return ValidationResult(self.name, True, 1.0, ["Brief (pydantic)"], "Brief válido.")
        jsonschema = _jsonschema()
        if jsonschema is not None and BRIEF_SCHEMA.is_file():
            schema = json.loads(BRIEF_SCHEMA.read_text(encoding="utf-8"))
            validator = jsonschema.Draft202012Validator(schema)
            errors = sorted(validator.iter_errors(dict(data)), key=lambda e: list(e.path))
            if errors:
                return ValidationResult(
                    self.name,
                    False,
                    0.0,
                    [f"{'.'.join(map(str, e.path)) or '<raíz>'}: {e.message}" for e in errors[:10]],
                    "El brief guardado no cumple brief.v1.json; la entrevista debe corregirlo.",
                )
            return ValidationResult(self.name, True, 1.0, ["brief.v1.json"], "Brief válido.")
        return ValidationResult(
            self.name,
            True,
            None,
            ["omitido: ni app.interview.brief.Brief ni schemas/brief.v1.json disponibles"],
            "Validación del brief omitida: no hay esquema disponible todavía (bloque B2).",
        )


__all__ = ["BRIEF_SCHEMA", "SchemaBrief", "SchemaRoleOutput"]

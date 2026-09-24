"""AC 29 -- the API answers every request its own schema allows without a server error.

`schemathesis` reads the OpenAPI document the app serves (the same one IF-08 commits) and
generates requests for every operation: valid bodies, boundary values, and bodies the schema
allows but the handler may not have imagined. The only check is `not_a_server_error`. A 4xx
is the API refusing a request it should refuse -- a missing role, a forbidden write, an
invalid record -- and is a pass; a 5xx is a handler that met an input it did not handle, which
the error contract of IF-07 says must not happen.

Each operation runs against its own private copy of the fixture novel (NFR-09). The app is
served the way `conftest.fixture_client` serves it: `FakeEmbedder` in place of `fastembed`, and
the conftest's `fake_model`, which fails every unscripted call as a model error, in place of
`claude -p`. A generated request that starts a turn therefore escalates on its first model
call, as it would with the CLI unavailable; nothing ever reaches a model, and the conftest's
guard would stop it if something tried.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

import pytest
import schemathesis
from hypothesis import HealthCheck, settings

from app.commons.deps import get_embedder, get_model_client
from app.commons.embeddings import FakeEmbedder
from app.commons.llm import FakeModelClient
from app.main import create_app


@pytest.fixture
def api_schema(fixture_root: Path, fake_model: FakeModelClient) -> schemathesis.BaseSchema:
    """The schema of an app bound to a private fixture copy, with fakes for both models."""
    del fixture_root  # requested for its side effect: settings now point at the copy
    app = create_app()
    app.dependency_overrides[get_embedder] = FakeEmbedder
    app.dependency_overrides[get_model_client] = lambda: fake_model
    return schemathesis.openapi.from_asgi("/openapi.json", app)


schema = schemathesis.pytest.from_fixture("api_schema")


class GeneratedCase(Protocol):
    """The one method this test calls on a `schemathesis.Case`. The class itself is generic over
    an operation type with four parameters of its own, which cannot be spelled without `Any`
    (NFR-02); a protocol types exactly what is used."""

    def call_and_validate(self, *, checks: list[schemathesis.CheckFunction]) -> object: ...


# spec 001 / AC 29 -- no 5xx for any request the schema allows.
@schema.parametrize()
@settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.too_slow,
        HealthCheck.filter_too_much,
    ],
)
def test_no_request_the_schema_allows_is_a_server_error(
    case: GeneratedCase,
) -> None:
    # Only this check: the others schemathesis runs by default would also demand that every
    # status code and error body be declared in openapi.json, which IF-07's errors are not yet
    # (spec 001, Open questions). `@check` widens the function's type; the cast narrows it back.
    server_errors = cast("schemathesis.CheckFunction", schemathesis.checks.not_a_server_error)
    case.call_and_validate(checks=[server_errors])

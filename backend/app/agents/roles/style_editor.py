"""The style editor's one call: `polish` (FR-AGENT-04).

Figure 3's style editor row is the narrowest in the table: `manuscript/NNN.md`, `canon/style.md`,
`canon/lexicon.yaml` and the POV's `cast/{id}/voice.md`, and nothing else. It polishes a scene
without ever seeing the axioms or the ledger, which is why a voice decision taken here cannot
become a rule about the world ("The style editor reads canon and writes prose, never the
reverse").

All four inputs are mandatory and bounded by construction (FR-CTX-03): there is nothing to
prune, so a set that does not fit is refused with `ContextBudgetExceeded` before any call.
The scene record is read by code to learn whose voice applies; it is not in the row, so it is
not sent. The instruction carries the operation and the prose language (FR-LLM-10), nothing
from the stores beyond that name.

The polished body is re-checked by the mechanical lexicon and voice checks before acceptance
(FR-AGENT-04); that, and writing it, are the orchestrator's (plan step 18).
"""

from __future__ import annotations

from typing import Final

from app.agents.models import RoleCall
from app.agents.roles import RoleInput, call_role
from app.agents.roles.writer import language_line, prose_language
from app.canon import service as canon_service
from app.cast import service as cast_service
from app.commons.config import CONTEXT_TOKEN_CAP
from app.commons.llm import ModelClient
from app.commons.permissions import AgentRole
from app.commons.schemas import PolishOutput
from app.commons.stores import Store, paths
from app.manuscript import service as manuscript_service
from app.scenes import service as scenes_service

ROLE: Final[AgentRole] = AgentRole.STYLE_EDITOR


def polish_instruction(scene_id: str, pov: str, language: str) -> str:
    """FR-AGENT-04. Which document is the scene and whose voice applies; the rules are in the
    documents."""
    return "\n".join(
        [
            f"Operation: polish scene {scene_id}.",
            (
                f"The accepted scene is the document labelled {paths.draft(scene_id)}; the style "
                f"guide is {paths.STYLE}, the lexicon {paths.LEXICON}, and the voice profile of "
                f"the point-of-view character is {paths.cast_file(pov, 'voice')}."
            ),
            language_line(language),
            "Return the whole polished scene as body.",
        ]
    )


def polish(
    store: Store, client: ModelClient, scene_id: str, *, cap: int = CONTEXT_TOKEN_CAP
) -> RoleCall[PolishOutput]:
    """FR-AGENT-04. The accepted draft in the book's voice. Four mandatory documents, in the
    order the row lists them: the draft's prose, the style guide, the lexicon, the voice."""
    pov = scenes_service.read_scene(store, scene_id).pov
    draft = paths.draft(scene_id)
    voice = paths.cast_file(pov, "voice")
    render = scenes_service.render_record
    inputs = [
        RoleInput(key=draft, path=draft, text=manuscript_service.read_draft(store, scene_id).body),
        RoleInput(key=paths.STYLE, path=paths.STYLE, text=render(canon_service.style(store))),
        RoleInput(key=paths.LEXICON, path=paths.LEXICON, text=render(canon_service.lexicon(store))),
        RoleInput(key=voice, path=voice, text=render(cast_service.read_voice(store, pov))),
    ]
    return call_role(
        client,
        role=ROLE,
        instruction=polish_instruction(scene_id, pov, prose_language(store)),
        mandatory=inputs,
        output_schema=PolishOutput,
        cap=cap,
    )


__all__ = ["ROLE", "polish", "polish_instruction"]

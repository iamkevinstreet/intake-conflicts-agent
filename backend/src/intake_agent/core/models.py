########################################################################
#               backend/src/intake_agent/core/models.py                #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Defines the shapes that cross a boundary: tool arguments and replies,
matches, findings, drafts and decisions. Tool arguments arrive from the
model, so each is parsed into a model here before anything uses it, and
the same models give the JSON schema the model is shown. Unknown fields
are refused, so a tool cannot be handed an argument it does not declare.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, Final, Literal

# Third-party
from kds.logs import get_logger
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# Local
from intake_agent.config import MAX_PARTIES, SETTINGS
from intake_agent.core.names import Band

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the shape of a draft id, from the config")
DRAFT_ID: Final = SETTINGS.ids_draft_pattern

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Lists the verdicts on an intake, mildest first")
Recommendation = Literal["clear", "review", "conflict"]
# log.debug("Lists how serious one finding is")
Severity = Literal["review", "conflict"]
# log.debug("Lists a party's side in the new matter")
Side = Literal["client", "adverse"]
# log.debug("Lists which of the firm's records a match is")
RecordKind = Literal["client", "adverse_party"]
# log.debug("Lists the roles a person may hold")
Role = Literal["requester", "approver"]
# log.debug("Lists a draft's states, in the order they can happen")
DraftStatus = Literal["draft", "pending", "approved", "rejected", "opened"]
# log.debug("Lists how a run can end")
Outcome = Literal["running", "submitted", "no_draft", "incomplete", "failed"]
# log.debug("Lists an approver's choices")
Decision = Literal["approved", "rejected"]
# log.debug("Sets the longest party name accepted")
NAME_CHARS = 200
# log.debug("Defines a party name: trimmed, not empty, not too long")
PartyName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=NAME_CHARS)
]
# log.debug("Sets the settings shared by every argument model")
STRICT = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
# log.debug("Sets the settings shared by every stored record")
FROZEN = ConfigDict(frozen=True)


########################################################################
#                           Boundary shapes                            #
########################################################################
# log.debug("Defines who is acting: a person, or the agent on their behalf")
class Actor(BaseModel):
    """A signed-in person, or the agent acting for one."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds a stable id: the Entra object id, or dev: and a name")
    user_id: str
    # log.debug("Holds the name to show")
    name: str
    # log.debug("Holds the roles the person holds")
    roles: frozenset[Role]


# log.debug("Defines the arguments of both search tools")
class SearchArgs(BaseModel):
    """A name to look up, as written in the email."""

    # log.debug("Refuses unknown fields and freezes the arguments")
    model_config = STRICT

    # log.debug("Holds the name to search for")
    name: PartyName = Field(description="A party's name")


# log.debug("Defines the arguments of draft_matter")
class DraftArgs(BaseModel):
    """The agent's reading of the intake and its recommendation."""

    # log.debug("Refuses unknown fields and freezes the arguments")
    model_config = STRICT

    # log.debug("Holds the prospective client")
    client: PartyName = Field(description="Who wants to hire us")
    # log.debug("Holds every party on the other side")
    adverse_parties: list[PartyName] = Field(
        max_length=MAX_PARTIES, description="Every party on the other side, people and companies"
    )
    # log.debug("Holds what kind of matter it is")
    matter_type: str = Field(min_length=1, max_length=120, description="For example: wage claim")
    # log.debug("Holds the timing the sender asked for")
    timeline: str = Field(default="", max_length=300, description="Deadlines the email gives")
    # log.debug("Holds a short summary for the approver")
    summary: str = Field(min_length=1, max_length=800, description="Two or three sentences")
    # log.debug("Holds the agent's verdict")
    recommendation: Recommendation = Field(description="clear, review or conflict")
    # log.debug("Holds why, for the approver")
    reasoning: str = Field(min_length=1, max_length=1500, description="Why, citing the matches")


# log.debug("Defines the arguments of request_approval")
class SubmitArgs(BaseModel):
    """The draft to send to an approver, and a note for them."""

    # log.debug("Refuses unknown fields and freezes the arguments")
    model_config = STRICT

    # log.debug("Holds the draft id draft_matter returned")
    draft_id: str = Field(pattern=DRAFT_ID, description="The id draft_matter returned")
    # log.debug("Holds a note for the approver")
    note: str = Field(default="", max_length=500, description="Anything the approver should know")


# log.debug("Defines the arguments of open_matter")
class OpenArgs(BaseModel):
    """The approved draft to open as a matter."""

    # log.debug("Refuses unknown fields and freezes the arguments")
    model_config = STRICT

    # log.debug("Holds the draft id")
    draft_id: str = Field(pattern=DRAFT_ID, description="An approved draft's id")


# log.debug("Defines one record a search found")
class Match(BaseModel):
    """A client or adverse party whose name is close to the query."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds which table it came from")
    kind: RecordKind
    # log.debug("Holds its row id")
    id: int
    # log.debug("Holds its name as the firm recorded it")
    name: str
    # log.debug("Holds how alike the names are, 0 to 100")
    score: int
    # log.debug("Holds how sure the match is")
    band: Band
    # log.debug("Holds current or former for a client, open or closed for a matter")
    status: str
    # log.debug("Holds, for an adverse party, the matter number")
    matter: str | None = None
    # log.debug("Holds, for an adverse party, the client in that matter")
    matter_client: str | None = None


# log.debug("Defines one finding: a party, a match and how serious it is")
class Finding(BaseModel):
    """A match that touches the new matter, and why it matters."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the party as the draft names it")
    party: str
    # log.debug("Holds the party's side in the new matter")
    side: Side
    # log.debug("Holds the record it matched")
    match: Match
    # log.debug("Holds how serious it is")
    severity: Severity
    # log.debug("Holds the rule that set the severity, in words")
    why: str


# log.debug("Defines the draft an approver reviews; its hash binds the approval")
class Draft(BaseModel):
    """The saved draft: the agent's reading, the checks, the email."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the draft id")
    id: str
    # log.debug("Holds the run that made it")
    run_id: str
    # log.debug("Holds the requester's id")
    requester: str
    # log.debug("Holds the requester's name")
    requester_name: str
    # log.debug("Holds when it was saved, UTC")
    created_at: str
    # log.debug("Holds the prospective client")
    client: str
    # log.debug("Holds the parties on the other side")
    adverse_parties: tuple[str, ...]
    # log.debug("Holds the kind of matter")
    matter_type: str
    # log.debug("Holds the timing asked for")
    timeline: str
    # log.debug("Holds the agent's summary")
    summary: str
    # log.debug("Holds the agent's verdict")
    agent_recommendation: Recommendation
    # log.debug("Holds the agent's reasons")
    agent_reasoning: str
    # log.debug("Holds every match the run's searches found for these parties")
    findings: tuple[Finding, ...]
    # log.debug("Holds the verdict the checks alone give, whatever the agent says")
    checks_recommendation: Recommendation
    # log.debug("Holds the verdict shown: the stricter of the two")
    recommendation: Recommendation
    # log.debug("Holds lines of the email that read like orders to the agent")
    warnings: tuple[str, ...]
    # log.debug("Holds the intake email, for the approver to compare")
    email: str
    # log.debug("Holds the email's SHA-256, the link to the run's audit")
    email_sha256: str


# log.debug("Defines an approver's decision")
class Approval(BaseModel):
    """Who decided a draft, what, why and when."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the approver's id")
    approver: str
    # log.debug("Holds the approver's name")
    approver_name: str
    # log.debug("Holds the decision")
    decision: Decision
    # log.debug("Holds the approver's note")
    note: str
    # log.debug("Holds when, UTC")
    decided_at: str


# log.debug("Defines a matter opened from an approved draft")
class NewMatter(BaseModel):
    """The matter number, who opened it and when."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the new matter's number")
    number: str
    # log.debug("Holds who opened it")
    opened_by: str
    # log.debug("Holds their name")
    opened_by_name: str
    # log.debug("Holds when, UTC")
    opened_at: str


# log.debug("Defines a draft with where it stands")
class DraftRecord(BaseModel):
    """A draft, its status, and its approval and matter if any."""

    # log.debug("Freezes the record once built")
    model_config = FROZEN

    # log.debug("Holds the draft")
    draft: Draft
    # log.debug("Holds its status")
    status: DraftStatus
    # log.debug("Holds the agent's note to the approver")
    note: str = ""
    # log.debug("Holds the decision, once made")
    approval: Approval | None = None
    # log.debug("Holds the opened matter, once opened")
    matter: NewMatter | None = None


# log.debug("Defines what a tool call returns")
@dataclass(frozen=True)
class ToolReply:
    """If the call worked, what the model is told, the audit code."""

    # log.debug("Holds whether the call did what was asked")
    ok: bool
    # log.debug("Holds the JSON the model reads")
    payload: dict[str, Any]
    # log.debug("Holds a short code for the audit when it did not")
    code: str = ""

########################################################################
#               backend/src/intake_agent/core/offline.py               #
########################################################################
"""
Author:            Kevin Street
Created on:        2026-10-29
Last modified on:  2026-10-29

Plays the agent offline, with fixed rules and no model or key. It makes
the service run with no key and gives the evaluation a baseline a model
must beat. The rules are simple on purpose:

- not an intake: an automatic reply, or no words asking for legal work
- the client: the last company named in the signature (the last four
  lines), else the first named after "our company", "on behalf of" or
  "we are"
- the other side: every other company named with a legal form (LLC,
  Inc., ...), a first and last name set off by commas ("our former
  bookkeeper, Ann Lee, took"), and names in a "Party:" field
- the verdict: the firm's rules applied to the matches, as the prompt
  states them

It misses companies written without a legal form and people named any
other way. The evaluation reports how much that costs.
"""

########################################################################
#                               Imports                                #
########################################################################
# Standard library
from __future__ import annotations

import json
import re
from typing import Any, Final

# Third-party
from kds.args import required
from kds.llm import Message, ModelAdapter
from kds.llm.fake import FakeProvider
from kds.logs import get_logger

# Local
from intake_agent.config import SETTINGS, AppSettings
from intake_agent.core import prompt
from intake_agent.core.guard import flag
from intake_agent.core.models import DraftArgs, Recommendation, SearchArgs, SubmitArgs
from intake_agent.core.names import normalize

########################################################################
#                           Global constants                           #
########################################################################
log = get_logger(__name__)
# log.debug("Takes the bands the firm's rules treat as strong, from the config")
STRONG: Final = SETTINGS.match_strong_bands
# log.debug("Takes the verdict for a match that blocks the matter, from the config")
CONFLICT: Final = SETTINGS.verdicts_conflict
# log.debug("Takes the verdict for a match a person must weigh, from the config")
REVIEW: Final = SETTINGS.verdicts_review
# log.debug("Takes the verdict when no record matched, from the config")
CLEAR: Final = SETTINGS.verdicts_clear

########################################################################
#                           Local constants                            #
########################################################################
# log.debug("Names the model the stand-in reports; it is priced at zero")
STAND_IN = "fake-model"
# log.debug("Lists legal forms that end a company name")
LEGAL = r"(?:LLC|L\.L\.C\.|Inc\.?|Corp\.?|Corporation|Co\.?|Company|LLP|LP|Ltd\.?|PLLC|PC|Group)"
# log.debug("Matches a company: up to five capitalised words on one line, then a legal form")
COMPANY_RE = re.compile(
    rf"\b((?:(?:[A-Z][\w'&-]*|&)[ \t]+){{0,4}}[A-Z][\w'&-]*,?[ \t]+{LEGAL})(?![\w])"
)
# log.debug("Matches a person set off by commas after a lowercase word: our bookkeeper, Ann Lee,")
PERSON_RE = re.compile(r"(?<=[a-z]),[ \t]+([A-Z][a-z'-]+[ \t]+[A-Z][a-z'-]+)(?=[,.;])")
# log.debug("Matches a structured party field: Party: Lee, Ann")
FIELD_RE = re.compile(
    r"^\s*(?:party|respondent|defendant|claimant|plaintiff|opposing party|adverse party)"
    r"\s*:\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)
# log.debug("Matches the cues that name the sender's own company")
CLIENT_CUE_RE = re.compile(r"\b(?:our company,|on behalf of|we are|I am .{0,40}? at)\s+$")
# log.debug("Matches an automatic reply")
AUTO_REPLY_RE = re.compile(r"\b(automatic reply|auto-?reply|out of (the )?office)\b", re.I)
# log.debug("Matches words that ask for legal work")
ASK_RE = re.compile(
    r"\b(represent|counsel|advice|advise|claim|dispute|lawsuit|sue|suing|charge|demand|"
    r"defend|enforce|help|pursue|recover|stop|need|want)\b",
    re.IGNORECASE,
)
# log.debug("Lists words that start a sentence, not a company name")
LEADING = frozenset("The A An Our We Since After When Yesterday Last In On Hello Hi Dear".split())
# log.debug("Sets how many closing lines count as the signature")
SIGNATURE_LINES = 4
# log.debug("Matches a parenthetical, dropped from a party field")
ASIDE_RE = re.compile(r"\s*\(.*?\)")
# log.debug("Names the key a scripted turn lists its tool calls under")
TOOL_CALLS = "tool_calls"
# log.debug("Sets the words of a refusal to draft")
NOT_INTAKE = "This is not a request for new legal work, so there is nothing to check or draft."
# log.debug("Sets the words when a search failed")
CHECK_FAILED = "The conflicts check could not be completed: the database did not answer."


########################################################################
#                           Offline stand-in                           #
########################################################################
# log.debug("Defines the stand-in's reply to the conversation so far")
def respond(messages: list[Message] | None = None) -> str | dict[str, Any]:
    """Returns the next move: tool calls as a dict, or final words.

    Args:
        messages: The conversation so far, the fenced email first.
            Required.

    Returns:
        The next turn's tool calls, as the stand-in provider expects
        them, or the closing words.
    """
    # log.debug("Takes the messages, which the caller must give")
    messages = required(messages=messages)
    # log.debug("Takes the email out of its fence")
    email = prompt.email_from(messages[0].content)
    # log.debug("Reads every tool result so far, by call id")
    results = {m.tool_call_id: json.loads(m.content) for m in messages if m.role == "tool"}
    # log.debug("Lists every tool call so far")
    calls = [call for m in messages if m.role == "assistant" for call in m.tool_calls]
    # log.debug("Lists the tools called")
    called = [call.name for call in calls]
    # log.debug("Starts with the searches")
    if not calls:
        # log.debug("Returns the searches, or the reason there are none")
        return _searches(email)
    # log.debug("Drafts once every search is back")
    if prompt.DRAFT_MATTER not in called:
        # log.debug("Stops if any search failed")
        if any(prompt.ERROR_KEY in results.get(c.id, {}) for c in calls):
            # log.debug("Returns the failure")
            return CHECK_FAILED
        # log.debug("Returns the draft")
        return _draft(email, calls, results)
    # log.debug("Asks for approval once the draft is saved")
    if prompt.REQUEST_APPROVAL not in called:
        # log.debug("Reads the draft's result")
        saved = next(results[c.id] for c in calls if c.name == prompt.DRAFT_MATTER)
        # log.debug("Returns the request, or why the draft was refused")
        return _request(email, saved)
    # log.debug("Returns its closing words")
    return "Sent to an approver."


# log.debug("Defines the parties the rules can find")
def parties(email: str | None = None) -> tuple[str | None, list[str]]:
    """Returns the client, or None, and the parties on the other side.

    Args:
        email: The intake email. Required.

    Returns:
        The client the rules find, or None, and every other party the
        email names, each once and never the client.
    """
    # log.debug("Takes the email, which the caller must give")
    email = required(email=email)
    # log.debug("Finds the client in the signature, else after a cue")
    client = _client(email)
    # log.debug("Collects every company, person and party field in the body")
    found = [
        *(_trim(m.group(1)) for m in COMPANY_RE.finditer(email)),
        *(m.group(1) for m in PERSON_RE.finditer(email)),
        *(ASIDE_RE.sub("", m.group(1)) for m in FIELD_RE.finditer(email)),
    ]
    # log.debug("Keeps each other party once, never the client")
    seen = {normalize(client)} if client else set()
    # log.debug("Starts the other side")
    adverse: list[str] = []
    # log.debug("Adds each new name")
    for name in found:
        # log.debug("Skips the client and repeats")
        if normalize(name) in seen:
            # log.debug("Moves on")
            continue
        # log.debug("Remembers it")
        seen.add(normalize(name))
        # log.debug("Adds it")
        adverse.append(name)
    # log.debug("Returns both")
    return client, adverse


# log.debug("Defines the first move: the searches")
def _searches(email: str | None = None) -> str | dict[str, Any]:
    """Returns a search for every party, or why there is none.

    Args:
        email: The intake email. Required.

    Returns:
        One turn with a search for each party, the client first, or
        why the email is not an intake.
    """
    # log.debug("Takes the email, which the caller must give")
    email = required(email=email)
    # log.debug("Refuses an automatic reply or an email that asks for nothing")
    if AUTO_REPLY_RE.search(email) or not ASK_RE.search(email):
        # log.debug("Returns the refusal")
        return NOT_INTAKE
    # log.debug("Finds the parties")
    client, adverse = parties(email)
    # log.debug("Refuses an email whose client cannot be found")
    if client is None:
        # log.debug("Returns the refusal")
        return NOT_INTAKE
    # log.debug("Searches the client among the parties the firm is against")
    searches = [(prompt.SEARCH_ADVERSE, client)] + [(prompt.SEARCH_CLIENTS, p) for p in adverse]
    # log.debug("Returns one call per search")
    return _turn(
        *(
            _call(f"search-{i}", tool, SearchArgs(name=name).model_dump())
            for i, (tool, name) in enumerate(searches)
        )
    )


# log.debug("Defines the second move: the draft")
def _draft(
    email: str | None = None,
    calls: list[Any] | None = None,
    results: dict[str | None, Any] | None = None,
) -> str | dict[str, Any]:
    """Returns the draft_matter call with the rules' verdict.

    Args:
        email: The intake email. Required.
        calls: Every tool call made so far. Required.
        results: Each call's result, by call id. Required.

    Returns:
        One turn with the draft_matter call and the rules' verdict, or
        why there is nothing to draft.
    """
    # log.debug("Takes the email, which the caller must give")
    email = required(email=email)
    # log.debug("Takes the calls so far, which the caller must give")
    calls = required(calls=calls)
    # log.debug("Takes the results so far, which the caller must give")
    results = required(results=results)
    # log.debug("Finds the parties again")
    client, adverse = parties(email)
    # log.debug("Refuses to draft without a client; the first move already checked")
    if client is None:
        # log.debug("Returns the refusal")
        return NOT_INTAKE
    # log.debug("Applies the firm's rules to every match")
    verdicts = [_judge(call.name, m) for call in calls for m in results[call.id]["matches"]]
    # log.debug("Takes the most serious")
    recommendation = CONFLICT if CONFLICT in verdicts else REVIEW if verdicts else CLEAR
    # log.debug("Returns the call, its arguments checked as the tool will check them")
    return _turn(
        _call(
            "draft",
            prompt.DRAFT_MATTER,
            DraftArgs(
                client=client,
                adverse_parties=adverse,
                matter_type="not classified by the offline rules",
                summary=f"{client} asks for help in a matter involving "
                f"{', '.join(adverse) or 'no other party'}.",
                recommendation=recommendation,
                reasoning=f"The firm's rules, applied to {_count(len(verdicts))}.",
            ).model_dump(),
        )
    )


# log.debug("Defines the third move: the request for approval")
def _request(
    email: str | None = None, saved: dict[str, Any] | None = None
) -> str | dict[str, Any]:
    """Returns request_approval, or why the draft was refused.

    Args:
        email: The intake email, checked for order-giving lines.
            Required.
        saved: The draft_matter call's result. Required.

    Returns:
        One turn with the request_approval call, whose note flags any
        order-giving lines, or why the draft was refused.
    """
    # log.debug("Takes the email, which the caller must give")
    email = required(email=email)
    # log.debug("Takes the draft's result, which the caller must give")
    saved = required(saved=saved)
    # log.debug("Reports a refused draft")
    if prompt.DRAFT_ID_KEY not in saved:
        # log.debug("Returns the refusal")
        return f"The draft was refused: {saved.get(prompt.ERROR_KEY, 'no reason given')}."
    # log.debug("Notes order-giving lines for the approver")
    note = "The email contains instructions aimed at the agent." if flag(email) else ""
    # log.debug("Returns the call")
    return _turn(
        _call(
            "request",
            prompt.REQUEST_APPROVAL,
            SubmitArgs(draft_id=saved[prompt.DRAFT_ID_KEY], note=note).model_dump(),
        )
    )


# log.debug("Defines a scripted turn of tool calls")
def _turn(*calls: dict[str, Any]) -> dict[str, Any]:
    """Returns a turn that makes the tool calls and says nothing.

    Args:
        *calls: The tool calls the turn makes, in order.

    Returns:
        The turn, with no words and the calls.
    """
    # log.debug("Returns the turn in the stand-in provider's shape")
    return {"text": "", TOOL_CALLS: list(calls)}


# log.debug("Defines one scripted tool call")
def _call(
    call_id: str | None = None, name: str | None = None, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Returns one tool call: its id, the tool and the arguments.

    Args:
        call_id: The call's id, which its result comes back under.
            Required.
        name: The tool to call. Required.
        arguments: The tool's arguments. Required.

    Returns:
        The call as the stand-in provider expects it.
    """
    # log.debug("Takes the call id, which the caller must give")
    call_id = required(call_id=call_id)
    # log.debug("Takes the tool's name, which the caller must give")
    name = required(name=name)
    # log.debug("Takes the arguments, which the caller must give")
    arguments = required(arguments=arguments)
    # log.debug("Returns the call")
    return {"id": call_id, "name": name, "arguments": arguments}


# log.debug("Defines the firm's rule for one match")
def _judge(tool: str | None = None, match: dict[str, Any] | None = None) -> Recommendation:
    """Returns conflict or review for one match, as the prompt states.

    Args:
        tool: The search that found the match. Required.
        match: The match as the search returned it. Required.

    Returns:
        conflict for a strong match with a current client or in an
        open matter, else review.
    """
    # log.debug("Takes the search's name, which the caller must give")
    tool = required(tool=tool)
    # log.debug("Takes the match, which the caller must give")
    match = required(match=match)
    # log.debug("Notes a strong match")
    strong = match["band"] in STRONG
    # log.debug("Reads the client's or the matter's status")
    status = match["status"]
    # log.debug("Calls a strong match with a current client a conflict")
    if tool == prompt.SEARCH_CLIENTS:
        # log.debug("Returns the verdict")
        return CONFLICT if strong and status == "current" else REVIEW
    # log.debug("Calls a strong match in an open matter a conflict")
    return CONFLICT if strong and status == "open" else REVIEW


# log.debug("Defines how the client is found")
def _client(email: str | None = None) -> str | None:
    """Returns the signature's company, else one after a cue.

    Args:
        email: The intake email. Required.

    Returns:
        The last company in the signature, else the first company
        named right after a cue, else None.
    """
    # log.debug("Takes the email, which the caller must give")
    email = required(email=email)
    # log.debug("Takes the signature: the last few non-empty lines")
    signature = "\n".join([line for line in email.splitlines() if line.strip()][-SIGNATURE_LINES:])
    # log.debug("Finds the companies in it; a signature names the sender's last")
    named = [_trim(match.group(1)) for match in COMPANY_RE.finditer(signature)]
    # log.debug("Returns the last one when there is one")
    if named:
        # log.debug("Returns it")
        return named[-1]
    # log.debug("Looks for a company right after a cue")
    for match in COMPANY_RE.finditer(email):
        # log.debug("Returns it when a cue comes just before")
        if CLIENT_CUE_RE.search(email[: match.start()]):
            # log.debug("Returns it")
            return _trim(match.group(1))
    # log.debug("Returns None: no client found")
    return None


# log.debug("Defines how a matched company name is tidied")
def _trim(name: str | None = None) -> str:
    """Returns the name without the sentence words in front of it.

    Args:
        name: A company name as the pattern matched it. Required.

    Returns:
        The name from its first word that does not start a sentence.
    """
    # log.debug("Takes the name, which the caller must give")
    name = required(name=name)
    # log.debug("Splits the name into words")
    words = name.split()
    # log.debug("Drops leading words that start sentences")
    while len(words) > 1 and words[0].rstrip(",") in LEADING:
        # log.debug("Drops one")
        words.pop(0)
    # log.debug("Returns the words joined")
    return " ".join(words)


# log.debug("Defines how a number of matches is written")
def _count(matches: int | None = None) -> str:
    """Returns "1 match" or "3 matches".

    Args:
        matches: How many matches. Required.

    Returns:
        The count with the right noun.
    """
    # log.debug("Takes the number of matches, which the caller must give")
    matches = required(matches=matches)
    # log.debug("Returns the count with the right noun")
    return f"{matches} match" if matches == 1 else f"{matches} matches"


# log.debug("Defines the adapter the settings call for")
def adapter_for(settings: AppSettings | None = None) -> ModelAdapter:
    """Returns the stand-in for the fake provider, else the real one.

    Args:
        settings: The settings that name the provider and model.
            Required.

    Returns:
        The adapter that plays the agent: the stand-in, priced at
        zero, for the fake provider, else the configured one.
    """
    # log.debug("Takes the settings, which the caller must give")
    settings = required(settings=settings)
    # log.debug("Returns the stand-in, priced at zero, when the provider is fake")
    if settings.llm_provider == "fake":
        # log.debug("Returns it")
        return ModelAdapter(FakeProvider(responder=respond), model=STAND_IN, settings=settings)
    # log.debug("Returns the configured provider and model")
    return ModelAdapter(settings=settings)

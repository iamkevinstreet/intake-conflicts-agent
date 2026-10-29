########################################################################
#                backend/src/intake_agent/core/agent.py                #
########################################################################
#  Author:            Kevin Street                                     #
#  Created on:        2026-10-29                                       #
#  Last modified on:  2026-10-29                                       #
#  Purpose:           The agent loop: model calls and tool calls       #
#                     within step, tool-call and budget limits.        #
########################################################################
"""The agent loop: the model reads, calls tools and stops, in limits.

Each step is one model call. The model may ask for several tool calls
in a step; each runs through the toolbox, and the results go back in
the next step. The loop ends when the draft is sent for approval, when
the model stops calling tools, or at a limit: steps, tool calls or the
run's budget. Everything the loop spends is counted on a meter the
caller holds, so a run that fails part way still reports its cost.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from kds.llm import Completion, Message, ModelAdapter
from kds.logs import get_logger

from intake_agent.config import AppSettings
from intake_agent.core import prompt
from intake_agent.core.models import Outcome
from intake_agent.core.tools import Toolbox

# Module constants
log = get_logger(__name__)
# log.debug("Sets the longest stretch of the model's last words kept as a reason")
REASON_CHARS = 300
# log.debug("Names the outcome of a run that hit a limit or an error")
FAILED: Outcome = "failed"
# log.debug("Names the outcome of a run that stopped short of an approver")
INCOMPLETE: Outcome = "incomplete"


# log.debug("Defines the meter a run's spending is counted on")
@dataclass
class Meter:
    """Model calls, tokens and cost so far; the caller reads it."""

    # log.debug("Holds the model calls made")
    steps: int = 0
    # log.debug("Holds the tokens read")
    input_tokens: int = 0
    # log.debug("Holds the tokens written")
    output_tokens: int = 0
    # log.debug("Holds the cost so far")
    cost_usd: float = 0.0
    # log.debug("Holds whether every call had a price")
    priced: bool = True

    # log.debug("Defines adding one model call")
    def add(self, completion: Completion) -> None:
        """Count one call's tokens and cost."""
        # log.debug("Counts the step")
        self.steps += 1
        # log.debug("Adds the tokens read")
        self.input_tokens += completion.usage.input_tokens
        # log.debug("Adds the tokens written")
        self.output_tokens += completion.usage.output_tokens
        # log.debug("Notes a call with no price")
        if completion.cost_usd is None:
            # log.debug("Marks the total as incomplete")
            self.priced = False
        else:
            # log.debug("Adds the cost")
            self.cost_usd += completion.cost_usd

    # log.debug("Defines the cost to report: none if any call was unpriced")
    @property
    def cost(self) -> float | None:
        """Return the cost, or None when any call had no price."""
        # log.debug("Returns it")
        return round(self.cost_usd, 6) if self.priced else None


# log.debug("Defines how a run ended")
@dataclass(frozen=True)
class Ending:
    """The outcome, why, and the model's last words."""

    # log.debug("Holds the outcome")
    outcome: Outcome
    # log.debug("Holds why, in a sentence")
    reason: str
    # log.debug("Holds the model's last words")
    text: str = ""


# log.debug("Defines the agent")
class IntakeAgent:
    """Runs one intake through the model and the toolbox."""

    # log.debug("Defines the constructor")
    def __init__(self, adapter: ModelAdapter, settings: AppSettings) -> None:
        """Call the model through `adapter`, in `settings` limits."""
        # log.debug("Keeps the adapter")
        self.adapter = adapter
        # log.debug("Keeps the settings")
        self.settings = settings

    # log.debug("Defines one run")
    def run(self, email: str, toolbox: Toolbox, meter: Meter) -> Ending:
        """Loop until the draft is sent, the model stops, or a limit."""
        # log.debug("Starts the conversation with the fenced email")
        messages = [Message(role="user", content=prompt.user_message(email))]
        # log.debug("Takes one step at a time, up to the limit")
        for step in range(1, self.settings.agent_max_steps + 1):
            # log.debug("Stops when the run has spent its budget")
            if meter.cost_usd >= self.settings.agent_run_budget_usd:
                # log.debug("Ends the run as failed")
                return Ending(FAILED, "the run spent its budget")
            # log.debug("Asks the model for its next move")
            completion = self.adapter.complete(
                messages,
                system=prompt.SYSTEM,
                tools=list(prompt.TOOLS),
                max_tokens=self.settings.agent_max_tokens,
            )
            # log.debug("Counts what the call used")
            meter.add(completion)
            # log.debug("Writes the call to the audit log")
            toolbox.runlog.model_call(toolbox.run_id, step, completion)
            # log.debug("Ends when the model stops calling tools")
            if not completion.tool_calls:
                # log.debug("Works out how the run ended from what the tools saw")
                return _settle(toolbox, completion.text)
            # log.debug("Ends when this step would pass the tool-call limit")
            if toolbox.calls + len(completion.tool_calls) > self.settings.agent_max_tool_calls:
                # log.debug("Ends the run as failed")
                return Ending(FAILED, "the run reached its tool-call limit")
            # log.debug("Adds the model's turn to the conversation")
            messages.append(
                Message(
                    role="assistant", content=completion.text, tool_calls=completion.tool_calls
                )
            )
            # log.debug("Runs each tool call in order and adds its result")
            for call in completion.tool_calls:
                # log.debug("Runs the call")
                reply = toolbox.call(call.name, call.arguments, step=step)
                # log.debug("Adds the result for the model to read")
                messages.append(
                    Message(role="tool", content=json.dumps(reply.payload), tool_call_id=call.id)
                )
            # log.debug("Ends when the draft has gone to an approver")
            if toolbox.submitted:
                # log.debug("Ends the run as submitted")
                return Ending("submitted", "sent to an approver", completion.text)
        # log.debug("Ends the run as failed at the step limit")
        return Ending(FAILED, "the run reached its step limit")


# log.debug("Defines how a run that stopped by itself ended")
def _settle(toolbox: Toolbox, text: str) -> Ending:
    """Return the outcome of a run whose model stopped calling tools."""
    # log.debug("Reports a failed search as an incomplete check")
    if toolbox.search_failed:
        # log.debug("Returns incomplete")
        return Ending(INCOMPLETE, "a conflicts search failed, so nothing was drafted", text)
    # log.debug("Reports a draft that never went for approval")
    if toolbox.draft_id is not None:
        # log.debug("Returns incomplete")
        return Ending(INCOMPLETE, "the draft was saved but not sent for approval", text)
    # log.debug("Reports a run that drafted nothing, in the model's words")
    return Ending("no_draft", text.strip()[:REASON_CHARS] or "the agent saved no draft", text)

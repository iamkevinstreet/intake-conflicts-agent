// ########################################################################
// #                  frontend/src/pages/IntakePage.tsx                   #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The requester's page: paste an email, run the    #
// #                     agent, and see everything it did.                #
// ########################################################################
/** The requester's page: paste an email, run the agent, see what it did. */

import { useEffect, useState } from 'react';

import { api, describeError } from '../api';
import { DraftSummary } from '../components/DraftSummary';
import { EmailForm } from '../components/EmailForm';
import { FindingsTable } from '../components/FindingsTable';
import { RunSteps } from '../components/RunSteps';
import { Verdicts } from '../components/Verdicts';
import { OUTCOMES, money, nextStep, seconds } from '../format';
import type { Example, IntakeResponse, Persona, RunDetail } from '../types';

interface Props {
  persona: Persona;
}

// log.debug('Defines the intake page')
export function IntakePage({ persona }: Props) {
  // log.debug('Keeps the examples')
  const [examples, setExamples] = useState<Example[]>([]);
  // log.debug('Keeps the last run')
  const [result, setResult] = useState<IntakeResponse | null>(null);
  // log.debug('Keeps the last run with its calls')
  const [detail, setDetail] = useState<RunDetail | null>(null);
  // log.debug('Keeps whether a run is in progress')
  const [busy, setBusy] = useState(false);
  // log.debug('Keeps a problem to show')
  const [problem, setProblem] = useState<string | null>(null);
  // log.debug('Notes whether this person may run intakes')
  const allowed = persona.role === 'requester';

  // log.debug('Loads the examples for a requester')
  useEffect(() => {
    // log.debug('Skips them for anyone else')
    if (!allowed) {
      // log.debug('Leaves the effect')
      return;
    }
    // log.debug('Fetches them')
    api
      .examples(persona)
      .then(setExamples)
      .catch((error: unknown) => setProblem(describeError(error)));
  }, [persona, allowed]);

  // log.debug('Defines a run')
  const run = (email: string): void => {
    // log.debug('Marks the run as started and clears the last one')
    setBusy(true);
    // log.debug('Clears the last result')
    setResult(null);
    // log.debug('Clears the last steps')
    setDetail(null);
    // log.debug('Clears any problem')
    setProblem(null);
    // log.debug('Runs the intake, then fetches its audit trail')
    api
      .intake(persona, email)
      .then(async (response) => {
        // log.debug('Keeps the result')
        setResult(response);
        // log.debug('Fetches and keeps the steps')
        setDetail(await api.run(persona, response.run.id));
      })
      .catch((error: unknown) => setProblem(describeError(error)))
      .finally(() => setBusy(false));
  };

  // log.debug('Returns the page')
  return (
    <div className="ia-intake">
      <header className="ia-intro">
        <h1 className="ia-intro__title">New matter intake</h1>
        <p className="ia-intro__lede">
          Paste an intake email. The agent reads it, searches the firm&apos;s clients and the
          parties it is against, and drafts the matter for an approver. It cannot open the matter.
        </p>
      </header>
      {!allowed && <p className="ia-status">Switch to a requester above to run an intake.</p>}
      {allowed && (
        <div className="ia-intake__grid">
          <EmailForm examples={examples} busy={busy} onSubmit={run} />
          <div className="ia-intake__result" aria-live="polite">
            {problem && (
              <p className="ia-status ia-status--error" role="alert">
                {problem}
              </p>
            )}
            {result && <Outcome result={result} />}
            {result?.draft && (
              <>
                <Verdicts draft={result.draft.draft} />
                <h2 className="ia-section__title">What the searches found</h2>
                <FindingsTable findings={result.draft.draft.findings} />
                <h2 className="ia-section__title">The draft</h2>
                <DraftSummary record={result.draft} />
              </>
            )}
            {detail && (
              <>
                <h2 className="ia-section__title">Every step, from the audit log</h2>
                <RunSteps detail={detail} />
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// log.debug('Defines the outcome banner')
function Outcome({ result }: { result: IntakeResponse }) {
  // log.debug('Takes the run')
  const { run } = result;
  // log.debug('Returns the outcome, its reason, and what the run used')
  return (
    <div className={`ia-outcome ia-outcome--${run.outcome}`}>
      <p className="ia-outcome__title">{OUTCOMES[run.outcome]}</p>
      <p className="ia-outcome__reason">{nextStep(run.outcome, run.draft_id, run.reason)}</p>
      <p className="ia-outcome__numbers">
        {run.steps} model calls · {run.tool_calls} tool calls · {money(run.cost_usd)} ·{' '}
        {seconds(run.ms)} · run {run.id}
      </p>
    </div>
  );
}

// ########################################################################
// #                  frontend/src/pages/IntakePage.tsx                   #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the requester's page: paste an email, run the agent, and see
 * everything it did.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import { useEffect, useState } from 'react';

// Local
import { api, describeError } from '../api';
import { DraftSummary } from '../components/DraftSummary';
import { EmailForm } from '../components/EmailForm';
import { FindingsTable } from '../components/FindingsTable';
import { RunSteps } from '../components/RunSteps';
import { Verdicts } from '../components/Verdicts';
import { OUTCOMES, money, nextStep, seconds } from '../format';
import { required } from '../lib/required';
import type { Example, IntakeResponse, Persona, RunDetail } from '../types';

// ########################################################################
// #                             Intake page                              #
// ########################################################################
interface Props {
  persona?: Persona | null;
}

// log.debug('Defines the intake page')
/**
 * Shows the intake form, then the run's outcome, verdicts, findings,
 * draft and steps.
 *
 * @param props - The page's props.
 * @param props.persona - The made-up person acting. Required.
 * @returns The page.
 */
export function IntakePage({ persona = null }: Props = {}): React.JSX.Element {
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Notes whether this person may run intakes')
  const allowed = persona.role === 'requester';
  // log.debug('Keeps a problem to show')
  const [problem, setProblem] = useState<string | null>(null);
  // log.debug('Takes the examples, loaded for a requester')
  const examples = useExamples(persona, allowed, setProblem);
  // log.debug('Takes the last run, its steps, and the way to start one')
  const { result, detail, busy, run } = useRun(persona, setProblem);
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
          <IntakeResult problem={problem} result={result} detail={detail} />
        </div>
      )}
    </div>
  );
}

// log.debug('Defines the hook that loads the examples')
/**
 * Returns the made-up examples, loaded once for a requester.
 *
 * @param persona - The made-up person acting. Required.
 * @param allowed - Whether the person may run intakes; nobody else
 *   gets the examples.
 * @param onProblem - Shows a problem loading them. Required.
 * @returns The examples; none until they arrive, or for anyone else.
 */
function useExamples(
  persona: Persona | null = null,
  allowed = false,
  onProblem: ((problem: string | null) => void) | null = null,
): Example[] {
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Takes the problem handler, which the caller must give')
  onProblem = required({ onProblem });
  // log.debug('Keeps the examples')
  const [examples, setExamples] = useState<Example[]>([]);

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
      .catch((error: unknown) => onProblem(describeError(error)));
  }, [persona, allowed, onProblem]);

  // log.debug('Returns them')
  return examples;
}

interface RunState {
  result: IntakeResponse | null;
  detail: RunDetail | null;
  busy: boolean;
  run: (email?: string | null) => void;
}

// log.debug('Defines the hook that runs intakes')
/**
 * Runs intakes, keeping the last run, its steps, and whether one is in
 * progress.
 *
 * @param persona - The made-up person acting. Required.
 * @param onProblem - Shows a problem, or clears it with null. Required.
 * @returns The last run, its steps, whether a run is in progress, and
 *   the way to start one.
 */
function useRun(
  persona: Persona | null = null,
  onProblem: ((problem: string | null) => void) | null = null,
): RunState {
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Takes the problem handler, which the caller must give')
  onProblem = required({ onProblem });
  // log.debug('Keeps the last run')
  const [result, setResult] = useState<IntakeResponse | null>(null);
  // log.debug('Keeps the last run with its calls')
  const [detail, setDetail] = useState<RunDetail | null>(null);
  // log.debug('Keeps whether a run is in progress')
  const [busy, setBusy] = useState(false);

  // log.debug('Defines a run')
  /**
   * Runs the intake on the email, then fetches its audit trail.
   *
   * @param email - The pasted intake email. Required.
   */
  const run = (email: string | null = null): void => {
    // log.debug('Takes the email, which the caller must give')
    email = required({ email });
    // log.debug('Marks the run as started and clears the last one')
    setBusy(true);
    // log.debug('Clears the last result')
    setResult(null);
    // log.debug('Clears the last steps')
    setDetail(null);
    // log.debug('Clears any problem')
    onProblem(null);
    // log.debug('Runs the intake, then fetches its audit trail')
    api
      .intake(persona, email)
      .then(async (response) => {
        // log.debug('Keeps the result')
        setResult(response);
        // log.debug('Fetches and keeps the steps')
        setDetail(await api.run(persona, response.run.id));
      })
      .catch((error: unknown) => onProblem(describeError(error)))
      .finally(() => setBusy(false));
  };

  // log.debug('Returns the last run, its steps, whether one is running, and the way to start one')
  return { result, detail, busy, run };
}

interface ResultProps {
  problem?: string | null;
  result?: IntakeResponse | null;
  detail?: RunDetail | null;
}

// log.debug('Defines the result column')
/**
 * Shows any problem, then the run's outcome, verdicts, findings and
 * draft, and every step from the audit log.
 *
 * @param props - The column's props.
 * @param props.problem - A problem to show; null when there is none.
 * @param props.result - The last run; null before the first.
 * @param props.detail - The last run's calls; null until they arrive.
 * @returns The column.
 */
function IntakeResult({
  problem = null,
  result = null,
  detail = null,
}: ResultProps = {}): React.JSX.Element {
  // log.debug('Returns the problem, the outcome, the draft and the steps')
  return (
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
  );
}

// log.debug('Defines the outcome banner')
/**
 * Shows how the run ended, why, and what it used.
 *
 * @param props - The banner's props.
 * @param props.result - The intake's response. Required.
 * @returns The banner.
 */
function Outcome({ result = null }: { result?: IntakeResponse | null } = {}): React.JSX.Element {
  // log.debug('Takes the response, which the caller must give')
  result = required({ result });
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

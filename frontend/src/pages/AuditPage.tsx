// ########################################################################
// #                   frontend/src/pages/AuditPage.tsx                   #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the audit log: every run the person may see, and every model
 * and tool call the chosen run made.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import { useEffect, useState } from 'react';

// Local
import { api, describeError } from '../api';
import { RunSteps } from '../components/RunSteps';
import { OUTCOMES, money, nextStep, seconds, when } from '../format';
import { required } from '../lib/required';
import type { Persona, RunDetail, RunRecord } from '../types';

// ########################################################################
// #                              Audit page                              #
// ########################################################################
interface Props {
  persona?: Persona | null;
}

// log.debug('Defines the audit page')
/**
 * Shows the runs the person may see, and the calls of the one chosen.
 *
 * @param props - The page's props.
 * @param props.persona - The made-up person acting. Required.
 * @returns The page.
 */
export function AuditPage({ persona = null }: Props = {}): React.JSX.Element {
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Takes the runs, the run being read, any problem, and the way to open one')
  const { runs, detail, problem, open } = useRuns(persona);
  // log.debug('Returns the page')
  return (
    <div className="ia-audit">
      <header className="ia-intro">
        <h1 className="ia-intro__title">Audit log</h1>
        <p className="ia-intro__lede">
          One record per run, and one per model call and tool call: the arguments with contact
          details redacted, a hash of what came back, tokens, cost and time. The email itself is
          kept only as a hash. Requesters see their own runs; approvers see everyone&apos;s.
        </p>
      </header>
      {problem && (
        <p className="ia-status ia-status--error" role="alert">
          {problem}
        </p>
      )}
      <RunTable runs={runs} onOpen={open} />
      {runs.length === 0 && <p className="ia-status">No runs yet.</p>}
      {detail && <RunReport detail={detail} />}
    </div>
  );
}

interface Runs {
  runs: RunRecord[];
  detail: RunDetail | null;
  problem: string | null;
  open: (id?: string | null) => void;
}

// log.debug('Defines the hook that loads the runs and opens one')
/**
 * Loads the runs the person may see, and opens one to read its calls.
 *
 * @param persona - The made-up person acting. Required.
 * @returns The runs, the run being read, a problem to show, and the way
 *   to open a run.
 */
function useRuns(persona: Persona | null = null): Runs {
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Keeps the runs')
  const [runs, setRuns] = useState<RunRecord[]>([]);
  // log.debug('Keeps the run being read')
  const [detail, setDetail] = useState<RunDetail | null>(null);
  // log.debug('Keeps a problem to show')
  const [problem, setProblem] = useState<string | null>(null);

  // log.debug('Loads the runs the person may see; the page remounts for each person')
  useEffect(() => {
    // log.debug('Fetches the runs')
    api
      .runs(persona)
      .then(setRuns)
      .catch((error: unknown) => setProblem(describeError(error)));
  }, [persona]);

  // log.debug('Defines opening one run')
  /**
   * Fetches one run's calls and shows them.
   *
   * @param id - The run's id. Required.
   */
  const open = (id: string | null = null): void => {
    // log.debug('Takes the id, which the caller must give')
    id = required({ id });
    // log.debug('Fetches its calls')
    api
      .run(persona, id)
      .then(setDetail)
      .catch((error: unknown) => setProblem(describeError(error)));
  };

  // log.debug('Returns the runs, the run being read, any problem, and the way to open one')
  return { runs, detail, problem, open };
}

interface TableProps {
  runs?: RunRecord[];
  onOpen?: ((id: string) => void) | null;
}

// log.debug('Defines the table of runs')
/**
 * Lists the runs, newest first, each id a button that opens the run.
 *
 * @param props - The table's props.
 * @param props.runs - The runs the person may see.
 * @param props.onOpen - Opens a run to read its calls. Required.
 * @returns The table.
 */
function RunTable({ runs = [], onOpen = null }: TableProps = {}): React.JSX.Element {
  // log.debug('Takes the open handler, which the caller must give')
  onOpen = required({ onOpen });
  // log.debug('Returns a row for each run')
  return (
    <div className="ia-table-wrap">
      <table className="ia-table">
        <caption className="ia-visually-hidden">Runs, newest first</caption>
        <thead>
          <tr>
            <th scope="col">Run</th>
            <th scope="col">Requester</th>
            <th scope="col">Outcome</th>
            <th scope="col" className="ia-table__num">
              Model + tool calls
            </th>
            <th scope="col" className="ia-table__num">
              Cost
            </th>
            <th scope="col" className="ia-table__num">
              Time
            </th>
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <tr key={run.id}>
              <td>
                <button type="button" className="ia-link" onClick={() => onOpen(run.id)}>
                  {run.id}
                </button>
                <span className="ia-audit__when">{when(run.started_at)}</span>
              </td>
              <td>{run.requester_name}</td>
              <td>{OUTCOMES[run.outcome]}</td>
              <td className="ia-table__num">
                {run.steps} + {run.tool_calls}
              </td>
              <td className="ia-table__num">{money(run.cost_usd)}</td>
              <td className="ia-table__num">{seconds(run.ms)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// log.debug('Defines the report of one run')
/**
 * Shows how the chosen run ended and why, the email's hash and size,
 * the model, and every call the run made.
 *
 * @param props - The report's props.
 * @param props.detail - The run with its calls. Required.
 * @returns The report.
 */
function RunReport({ detail = null }: { detail?: RunDetail | null } = {}): React.JSX.Element {
  // log.debug('Takes the run, which the caller must give')
  detail = required({ detail });
  // log.debug('Returns the run, its reason, its hash and model, and its calls')
  return (
    <section className="ia-audit__detail" aria-label={`Run ${detail.run.id}`}>
      <h2 className="ia-section__title">
        {detail.run.id}: {OUTCOMES[detail.run.outcome]}
      </h2>
      <p className="ia-audit__reason">
        {nextStep(detail.run.outcome, detail.run.draft_id, detail.run.reason)}
      </p>
      <p className="ia-audit__hash">
        Email SHA-256 <code>{detail.run.email_sha256}</code>, {detail.run.email_chars} characters,
        model <code>{detail.run.model}</code>
      </p>
      <RunSteps detail={detail} />
    </section>
  );
}

// ########################################################################
// #                   frontend/src/pages/AuditPage.tsx                   #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The audit log: every run, and every model and    #
// #                     tool call each run made.                         #
// ########################################################################
/** The audit log: every run, and every call each run made. */

import { useEffect, useState } from 'react';

import { api, describeError } from '../api';
import { RunSteps } from '../components/RunSteps';
import { OUTCOMES, money, nextStep, seconds, when } from '../format';
import type { Persona, RunDetail, RunRecord } from '../types';

interface Props {
  persona: Persona;
}

// log.debug('Defines the audit page')
export function AuditPage({ persona }: Props) {
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
  const open = (id: string): void => {
    // log.debug('Fetches its calls')
    api
      .run(persona, id)
      .then(setDetail)
      .catch((error: unknown) => setProblem(describeError(error)));
  };

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
                  <button type="button" className="ia-link" onClick={() => open(run.id)}>
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
      {runs.length === 0 && <p className="ia-status">No runs yet.</p>}
      {detail && (
        <section className="ia-audit__detail" aria-label={`Run ${detail.run.id}`}>
          <h2 className="ia-section__title">
            {detail.run.id}: {OUTCOMES[detail.run.outcome]}
          </h2>
          <p className="ia-audit__reason">
            {nextStep(detail.run.outcome, detail.run.draft_id, detail.run.reason)}
          </p>
          <p className="ia-audit__hash">
            Email SHA-256 <code>{detail.run.email_sha256}</code>, {detail.run.email_chars}{' '}
            characters, model <code>{detail.run.model}</code>
          </p>
          <RunSteps detail={detail} />
        </section>
      )}
    </div>
  );
}

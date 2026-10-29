// ########################################################################
// #                 frontend/src/pages/ApprovalsPage.tsx                 #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The approver's page: pick a draft, weigh the     #
// #                     findings, decide, and open the matter.           #
// ########################################################################
/** The approver's page: pick a draft, weigh the findings, decide, open. */

import { useCallback, useEffect, useRef, useState } from 'react';

import { api, describeError } from '../api';
import { DecisionForm } from '../components/DecisionForm';
import { DraftList } from '../components/DraftList';
import { DraftSummary } from '../components/DraftSummary';
import { FindingsTable } from '../components/FindingsTable';
import { GatePanel } from '../components/GatePanel';
import { Verdicts } from '../components/Verdicts';
import type { Decision, DraftRecord, Persona } from '../types';

interface Props {
  persona: Persona;
}

// log.debug('Defines the approvals page')
export function ApprovalsPage({ persona }: Props) {
  // log.debug('Keeps the drafts')
  const [records, setRecords] = useState<DraftRecord[]>([]);
  // log.debug('Keeps the selected draft id')
  const [selected, setSelected] = useState<string | null>(null);
  // log.debug('Keeps whether an action is in progress')
  const [busy, setBusy] = useState(false);
  // log.debug('Keeps a problem to show')
  const [problem, setProblem] = useState<string | null>(null);
  // log.debug('Keeps whether the list shows only drafts waiting for a decision')
  const [waitingOnly, setWaitingOnly] = useState(true);
  // log.debug('Counts loads, so a slow older load cannot overwrite a newer one')
  const latest = useRef(0);

  // log.debug('Defines loading the drafts')
  const load = useCallback((): void => {
    // log.debug('Numbers this load')
    const mine = ++latest.current;
    // log.debug('Fetches the drafts the caller may see')
    api
      .drafts(persona)
      .then((list) => {
        // log.debug('Keeps them only if no newer load started')
        if (mine === latest.current) {
          // log.debug('Keeps the list')
          setRecords(list);
        }
      })
      .catch((error: unknown) => setProblem(describeError(error)));
  }, [persona]);

  // log.debug('Loads the drafts when the person changes')
  useEffect(load, [load]);

  // log.debug('Defines an action on the selected draft, then a reload')
  const act = (action: () => Promise<unknown>): void => {
    // log.debug('Marks the action as started')
    setBusy(true);
    // log.debug('Clears any problem')
    setProblem(null);
    // log.debug('Runs it, then reloads, showing any refusal')
    action()
      .then(load)
      .catch((error: unknown) => setProblem(describeError(error)))
      .finally(() => setBusy(false));
  };

  // log.debug('Finds the selected record')
  const record = records.find((r) => r.draft.id === selected) ?? null;
  // log.debug('Takes the drafts waiting for a decision')
  const waiting = records.filter((r) => r.status === 'pending');
  // log.debug('Returns the page')
  return (
    <div className="ia-review">
      <header className="ia-intro">
        <h1 className="ia-intro__title">Approvals</h1>
        <p className="ia-intro__lede">
          Each draft shows the agent&apos;s verdict beside the checks&apos;, every match the
          searches found, and the email itself. Only an approver can decide, never on their own
          draft, and a matter opens only after approval.
        </p>
      </header>
      {problem && (
        <p className="ia-status ia-status--error" role="alert">
          {problem}
        </p>
      )}
      <div className="ia-review__grid">
        <nav aria-label="Drafts">
          <div className="ia-filter" role="group" aria-label="Which drafts">
            <button
              type="button"
              className="ia-filter__option"
              aria-pressed={waitingOnly}
              onClick={() => setWaitingOnly(true)}
            >
              Waiting ({waiting.length})
            </button>
            <button
              type="button"
              className="ia-filter__option"
              aria-pressed={!waitingOnly}
              onClick={() => setWaitingOnly(false)}
            >
              All ({records.length})
            </button>
          </div>
          <DraftList
            records={waitingOnly ? waiting : records}
            selected={selected}
            onSelect={setSelected}
          />
        </nav>
        <article className="ia-review__detail" aria-live="polite">
          {record === null ? (
            <p className="ia-status">Pick a draft to review it.</p>
          ) : (
            <>
              <h2 className="ia-section__title">{record.draft.client}</h2>
              <Verdicts draft={record.draft} />
              <h3 className="ia-section__title">What the searches found</h3>
              <FindingsTable findings={record.draft.findings} />
              <DraftSummary record={record} />
              {persona.role === 'approver' && record.status === 'pending' && (
                <DecisionForm
                  key={record.draft.id}
                  record={record}
                  busy={busy}
                  onDecide={(decision: Decision, note: string) =>
                    act(() => api.decide(persona, record.draft.id, decision, note))
                  }
                />
              )}
              <GatePanel
                record={record}
                busy={busy || persona.role !== 'approver'}
                onOpen={() => act(() => api.open(persona, record.draft.id))}
              />
            </>
          )}
        </article>
      </div>
    </div>
  );
}

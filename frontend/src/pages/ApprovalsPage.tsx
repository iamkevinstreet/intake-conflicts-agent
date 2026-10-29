// ########################################################################
// #                 frontend/src/pages/ApprovalsPage.tsx                 #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the approver's page: pick a draft, weigh the findings, decide,
 * and open the matter.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import { useCallback, useEffect, useRef, useState } from 'react';

// Local
import { api, describeError } from '../api';
import { DecisionForm } from '../components/DecisionForm';
import { DraftList } from '../components/DraftList';
import { DraftSummary } from '../components/DraftSummary';
import { FindingsTable } from '../components/FindingsTable';
import { GatePanel } from '../components/GatePanel';
import { Verdicts } from '../components/Verdicts';
import { required } from '../lib/required';
import type { Decision, DraftRecord, Persona } from '../types';

// ########################################################################
// #                            Approvals page                            #
// ########################################################################
interface Props {
  persona?: Persona | null;
}

// log.debug('Defines the approvals page')
/**
 * Shows the drafts the person may see, and the chosen draft with its
 * decision and gate.
 *
 * @param props - The page's props.
 * @param props.persona - The made-up person acting. Required.
 * @returns The page.
 */
export function ApprovalsPage({ persona = null }: Props = {}): React.JSX.Element {
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Takes the drafts, whether an action is running, any problem, and the way to act')
  const { records, busy, problem, act } = useDrafts(persona);
  // log.debug('Keeps the selected draft id')
  const [selected, setSelected] = useState<string | null>(null);
  // log.debug('Keeps whether the list shows only drafts waiting for a decision')
  const [waitingOnly, setWaitingOnly] = useState(true);
  // log.debug('Finds the selected record')
  const record = records.find((r) => r.draft.id === selected) ?? null;
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
        <DraftPicker
          records={records}
          waitingOnly={waitingOnly}
          onFilter={setWaitingOnly}
          selected={selected}
          onSelect={setSelected}
        />
        <article className="ia-review__detail" aria-live="polite">
          {record === null ? (
            <p className="ia-status">Pick a draft to review it.</p>
          ) : (
            <DraftReview record={record} persona={persona} busy={busy} onAct={act} />
          )}
        </article>
      </div>
    </div>
  );
}

interface Drafts {
  records: DraftRecord[];
  busy: boolean;
  problem: string | null;
  act: (action?: (() => Promise<unknown>) | null) => void;
}

// log.debug('Defines the hook that loads the drafts and acts on them')
/**
 * Loads the drafts the person may see, and runs actions on them,
 * reloading after each.
 *
 * @param persona - The made-up person acting. Required.
 * @returns The drafts, whether an action is running, a problem to
 *   show, and the way to act on a draft.
 */
function useDrafts(persona: Persona | null = null): Drafts {
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Keeps the drafts')
  const [records, setRecords] = useState<DraftRecord[]>([]);
  // log.debug('Keeps whether an action is in progress')
  const [busy, setBusy] = useState(false);
  // log.debug('Keeps a problem to show')
  const [problem, setProblem] = useState<string | null>(null);
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
  /**
   * Runs an action on the selected draft, then reloads the list,
   * showing any refusal.
   *
   * @param action - The call to the API to make. Required.
   */
  const act = (action: (() => Promise<unknown>) | null = null): void => {
    // log.debug('Takes the action, which the caller must give')
    action = required({ action });
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

  // log.debug('Returns the drafts, whether an action is running, any problem, and the way to act')
  return { records, busy, problem, act };
}

interface PickerProps {
  records?: DraftRecord[];
  waitingOnly?: boolean;
  onFilter?: ((waitingOnly: boolean) => void) | null;
  selected?: string | null;
  onSelect?: ((id: string) => void) | null;
}

// log.debug('Defines the draft picker')
/**
 * Shows the filter, waiting or all, and the list of drafts to pick
 * from.
 *
 * @param props - The picker's props.
 * @param props.records - Every draft the person may see.
 * @param props.waitingOnly - Whether the list shows only the drafts
 *   waiting for a decision.
 * @param props.onFilter - Switches between waiting and all. Required.
 * @param props.selected - The picked draft's id; null for none.
 * @param props.onSelect - Picks a draft. Required.
 * @returns The picker.
 */
function DraftPicker({
  records = [],
  waitingOnly = true,
  onFilter = null,
  selected = null,
  onSelect = null,
}: PickerProps = {}): React.JSX.Element {
  // log.debug('Takes the filter handler, which the caller must give')
  onFilter = required({ onFilter });
  // log.debug('Takes the select handler, which the caller must give')
  onSelect = required({ onSelect });
  // log.debug('Takes the drafts waiting for a decision')
  const waiting = records.filter((r) => r.status === 'pending');
  // log.debug('Returns the filter and the list')
  return (
    <nav aria-label="Drafts">
      <div className="ia-filter" role="group" aria-label="Which drafts">
        <button
          type="button"
          className="ia-filter__option"
          aria-pressed={waitingOnly}
          onClick={() => onFilter(true)}
        >
          Waiting ({waiting.length})
        </button>
        <button
          type="button"
          className="ia-filter__option"
          aria-pressed={!waitingOnly}
          onClick={() => onFilter(false)}
        >
          All ({records.length})
        </button>
      </div>
      <DraftList
        records={waitingOnly ? waiting : records}
        selected={selected}
        onSelect={onSelect}
      />
    </nav>
  );
}

interface ReviewProps {
  record?: DraftRecord | null;
  persona?: Persona | null;
  busy?: boolean;
  onAct?: ((action: () => Promise<unknown>) => void) | null;
}

// log.debug('Defines the review of one draft')
/**
 * Shows the chosen draft's verdicts, findings and summary, the
 * decision while it waits for an approver, and the gate.
 *
 * @param props - The review's props.
 * @param props.record - The chosen draft. Required.
 * @param props.persona - The made-up person acting. Required.
 * @param props.busy - Whether an action is on its way.
 * @param props.onAct - Makes a call to the API on the draft, then
 *   reloads. Required.
 * @returns The review.
 */
function DraftReview({
  record = null,
  persona = null,
  busy = false,
  onAct = null,
}: ReviewProps = {}): React.JSX.Element {
  // log.debug('Takes the draft, which the caller must give')
  record = required({ record });
  // log.debug('Takes the person acting, which the caller must give')
  persona = required({ persona });
  // log.debug('Takes the action handler, which the caller must give')
  onAct = required({ onAct });
  // log.debug('Returns the draft, the decision while it waits, and the gate')
  return (
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
            onAct(() => api.decide(persona, record.draft.id, decision, note))
          }
        />
      )}
      <GatePanel
        record={record}
        busy={busy || persona.role !== 'approver'}
        onOpen={() => onAct(() => api.open(persona, record.draft.id))}
      />
    </>
  );
}

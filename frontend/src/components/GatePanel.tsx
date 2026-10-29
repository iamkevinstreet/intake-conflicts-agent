// ########################################################################
// #                frontend/src/components/GatePanel.tsx                 #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the gate: the decision record, and the button that opens the
 * matter, which only an approved draft allows.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { STATUSES, when } from '../format';
import { required } from '../lib/required';
import type { DraftRecord } from '../types';

// ########################################################################
// #                            Approval gate                             #
// ########################################################################
interface Props {
  record?: DraftRecord | null;
  busy?: boolean;
  onOpen?: (() => void) | null;
}

// log.debug('Defines the gate panel')
/**
 * Shows the draft's status, its decision, and the matter or the button
 * that opens it.
 *
 * @param props - The panel's props.
 * @param props.record - The draft whose gate to show. Required.
 * @param props.busy - Whether an opening is on its way.
 * @param props.onOpen - Asks the API to open the matter. Required.
 * @returns The panel.
 */
export function GatePanel({
  record = null,
  busy = false,
  onOpen = null,
}: Props = {}): React.JSX.Element {
  // log.debug('Takes the draft, which the caller must give')
  record = required({ record });
  // log.debug('Takes the open handler, which the caller must give')
  onOpen = required({ onOpen });
  // log.debug('Notes whether an approval record exists')
  const approved = record.approval?.decision === 'approved';
  // log.debug('Returns the decision record, the opened matter, or the button')
  return (
    <section className="ia-gate" aria-label="Open the matter">
      <p className="ia-gate__status">
        Status: <strong>{STATUSES[record.status]}</strong>
      </p>
      {record.approval && (
        <p className="ia-gate__record">
          {record.approval.decision === 'approved' ? 'Approved' : 'Rejected'} by{' '}
          {record.approval.approver_name}, {when(record.approval.decided_at)}
          {record.approval.note && <>: "{record.approval.note}"</>}
        </p>
      )}
      {record.matter ? (
        <p className="ia-gate__opened">
          Opened as <strong>{record.matter.number}</strong> by {record.matter.opened_by_name},{' '}
          {when(record.matter.opened_at)}.
        </p>
      ) : (
        <>
          <button
            type="button"
            className="ia-button"
            disabled={busy || !approved}
            onClick={onOpen}
          >
            Open the matter
          </button>
          {!approved && (
            <p className="ia-gate__hint">
              Opening needs an approval record from someone other than the requester. The server
              checks this, and so does the database.
            </p>
          )}
        </>
      )}
    </section>
  );
}

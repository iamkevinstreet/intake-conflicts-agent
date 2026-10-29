// ########################################################################
// #                frontend/src/components/GatePanel.tsx                 #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The gate: the decision record, and opening the   #
// #                     matter only once a draft is approved.            #
// ########################################################################
/** The gate: opening the matter, which only an approved draft allows. */

import { STATUSES, when } from '../format';
import type { DraftRecord } from '../types';

interface Props {
  record: DraftRecord;
  busy: boolean;
  onOpen: () => void;
}

// log.debug('Defines the gate panel')
export function GatePanel({ record, busy, onOpen }: Props) {
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

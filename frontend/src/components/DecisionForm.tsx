// ########################################################################
// #               frontend/src/components/DecisionForm.tsx               #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The approver's decision: approve or reject, with #
// #                     the reason a flagged draft needs.                #
// ########################################################################
/** The approver's decision: approve or reject, with a note. */

import { useState } from 'react';

import { MIN_REASON_CHARS } from '../config';
import type { Decision, DraftRecord } from '../types';

interface Props {
  record: DraftRecord;
  busy: boolean;
  onDecide: (decision: Decision, note: string) => void;
}

// log.debug('Defines the decision form')
export function DecisionForm({ record, busy, onDecide }: Props) {
  // log.debug('Keeps the note being written')
  const [note, setNote] = useState('');
  // log.debug('Notes whether the checks or the agent flagged anything')
  const flagged = record.draft.recommendation !== 'clear';
  // log.debug('Allows approving a flagged draft only with a reason')
  const canApprove = !busy && (!flagged || note.trim().length >= MIN_REASON_CHARS);
  // log.debug('Returns the form')
  return (
    <form className="ia-decision" onSubmit={(event) => event.preventDefault()}>
      <label className="ia-form__label" htmlFor="ia-note">
        {flagged ? 'Your reason (needed to approve past a flag)' : 'Note (optional)'}
      </label>
      <textarea
        id="ia-note"
        className="ia-decision__note"
        value={note}
        onChange={(event) => setNote(event.target.value)}
        rows={3}
        maxLength={500}
        placeholder={flagged ? 'For example: waiver signed by both clients, on file.' : ''}
      />
      <div className="ia-decision__buttons">
        <button
          type="button"
          className="ia-button"
          disabled={!canApprove}
          onClick={() => onDecide('approved', note.trim())}
        >
          Approve
        </button>
        <button
          type="button"
          className="ia-button ia-button--quiet"
          disabled={busy}
          onClick={() => onDecide('rejected', note.trim())}
        >
          Reject
        </button>
      </div>
    </form>
  );
}

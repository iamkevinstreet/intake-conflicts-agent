// ########################################################################
// #               frontend/src/components/DecisionForm.tsx               #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the approver's decision: approve or reject, with the reason a
 * flagged draft needs before it can be approved.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import { useState } from 'react';

// Local
import { CONFIG } from '../config';
import { required } from '../lib/required';
import type { Decision, DraftRecord } from '../types';

// ########################################################################
// #                           Global constants                           #
// ########################################################################
// log.debug('Takes the shortest reason for approving past a flag, from the config')
const MIN_REASON_CHARS = CONFIG.api.min_reason_chars;
// log.debug('Takes the longest decision note the API accepts, from the config')
const MAX_NOTE_CHARS = CONFIG.api.max_note_chars;

// ########################################################################
// #                            Decision form                             #
// ########################################################################
interface Props {
  record?: DraftRecord | null;
  busy?: boolean;
  onDecide?: ((decision: Decision, note: string) => void) | null;
}

// log.debug('Defines the decision form')
/**
 * Shows the note and the approve and reject buttons for one draft.
 *
 * @param props - The form's props.
 * @param props.record - The draft to decide. Required.
 * @param props.busy - Whether a decision is on its way.
 * @param props.onDecide - Sends the decision and the note. Required.
 * @returns The form.
 */
export function DecisionForm({
  record = null,
  busy = false,
  onDecide = null,
}: Props = {}): React.JSX.Element {
  // log.debug('Takes the draft, which the caller must give')
  record = required({ record });
  // log.debug('Takes the decision handler, which the caller must give')
  onDecide = required({ onDecide });
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
        maxLength={MAX_NOTE_CHARS}
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

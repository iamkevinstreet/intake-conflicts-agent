// ########################################################################
// #                        frontend/src/format.ts                        #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Writes values for people: verdicts, bands, outcomes and statuses in a
 * few words, and money, durations, times and tool arguments as text.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { CONFIG } from './config';
import { required } from './lib/required';
import type { Band, DraftStatus, Outcome, Recommendation } from './types';

// ########################################################################
// #                           Global constants                           #
// ########################################################################
// log.debug('Takes the milliseconds in a second, from the config')
const MS = CONFIG.units.ms_per_second;

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Sets the decimal places dollar amounts are shown with')
const CENTS_PLACES = 4;
// log.debug('Lists what each verdict means, in a few words')
export const VERDICTS: Readonly<Record<Recommendation, string>> = {
  clear: 'Clear',
  review: 'A person must decide',
  conflict: 'Conflict',
};
// log.debug('Lists what each band means')
export const BANDS: Readonly<Record<Band, string>> = {
  exact: 'Exact',
  likely: 'Likely the same',
  possible: 'Possibly the same',
};
// log.debug('Lists what each run outcome means for the requester')
export const OUTCOMES: Readonly<Record<Outcome, string>> = {
  running: 'Running',
  submitted: 'Sent to an approver',
  no_draft: 'Nothing drafted',
  incomplete: 'Check not completed',
  failed: 'Run failed',
};
// log.debug('Lists what each draft status means')
export const STATUSES: Readonly<Record<DraftStatus, string>> = {
  draft: 'Not sent',
  pending: 'Waiting for an approver',
  approved: 'Approved',
  rejected: 'Rejected',
  opened: 'Matter opened',
};

// ########################################################################
// #                             Display text                             #
// ########################################################################
// log.debug('Defines how a cost is written')
/**
 * Returns a cost as dollars, or a dash when it has no price.
 *
 * @param usd - The cost in dollars; null when the model has no price.
 * @returns The cost to four places, as runs cost fractions of a cent.
 */
export function money(usd: number | null = null): string {
  // log.debug('Writes an unpriced cost as a dash')
  if (usd === null) {
    // log.debug('Returns the dash')
    return '-';
  }
  // log.debug('Writes the dollars to four places, since runs cost fractions of a cent')
  return `$${usd.toFixed(CENTS_PLACES)}`;
}

// log.debug('Defines how a duration is written')
/**
 * Returns a duration in milliseconds under a second, else in seconds.
 *
 * @param ms - The duration, in milliseconds. Required.
 * @returns The duration with its unit.
 */
export function seconds(ms: number | null = null): string {
  // log.debug('Takes the duration, which the caller must give')
  ms = required({ ms });
  // log.debug('Writes a duration under a second in milliseconds')
  if (ms < MS) {
    // log.debug('Returns the milliseconds')
    return `${String(ms)} ms`;
  }
  // log.debug('Returns the seconds to one place')
  return `${(ms / MS).toFixed(1)} s`;
}

// log.debug('Defines the sentence that says where a run left its draft')
/**
 * Returns the sentence that says where a run left its draft.
 *
 * @param outcome - How the run ended. Required.
 * @param draftId - The draft the run saved; null when it saved none.
 * @param reason - The run's own reason, used for any other ending.
 *   Required.
 * @returns Where the draft waits after a submitted run, or the reason.
 */
export function nextStep(
  outcome: Outcome | null = null,
  draftId: string | null = null,
  reason: string | null = null,
): string {
  // log.debug('Takes the outcome, which the caller must give')
  outcome = required({ outcome });
  // log.debug('Takes the reason, which the caller must give')
  reason = required({ reason });
  // log.debug('Names the draft waiting for a decision after a submitted run')
  if (outcome === 'submitted' && draftId) {
    // log.debug('Returns the sentence')
    return `Draft ${draftId} is waiting for a person to decide. The agent cannot open it.`;
  }
  // log.debug('Returns the run reason otherwise')
  return reason;
}

// log.debug('Defines how a timestamp is written')
/**
 * Returns a timestamp in the reader's local format, to the minute.
 *
 * @param iso - The time as ISO 8601 text. Required.
 * @returns The date and time.
 */
export function when(iso: string | null = null): string {
  // log.debug('Takes the time, which the caller must give')
  iso = required({ iso });
  // log.debug('Returns the date and time in the local format, to the minute')
  return new Date(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' });
}

// log.debug('Defines how the arguments of a tool call are written in one line')
/**
 * Returns a tool call's arguments in one short line.
 *
 * @param args - The arguments as the audit log recorded them. Required.
 * @returns A search's name, a draft id, a draft's client and party
 *   count, or anything else as JSON.
 */
export function argumentsLine(args: Record<string, unknown> | null = null): string {
  // log.debug('Takes the arguments, which the caller must give')
  args = required({ args });
  // log.debug('Writes a search as its name alone')
  if (typeof args.name === 'string') {
    // log.debug('Returns the quoted name')
    return `"${args.name}"`;
  }
  // log.debug('Writes a draft id as itself')
  if (typeof args.draft_id === 'string') {
    // log.debug('Returns it')
    return args.draft_id;
  }
  // log.debug('Writes a draft as its client and parties')
  if (typeof args.client === 'string') {
    // log.debug('Returns the client and the number of other parties')
    const others = Array.isArray(args.adverse_parties) ? args.adverse_parties.length : 0;
    // log.debug('Returns the line')
    return `${args.client}, ${String(others)} other ${others === 1 ? 'party' : 'parties'}`;
  }
  // log.debug('Writes anything else as JSON')
  return JSON.stringify(args);
}

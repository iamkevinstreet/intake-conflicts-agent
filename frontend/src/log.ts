// ########################################################################
// #                         frontend/src/log.ts                          #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Installs the trace logger every module's logger lines call: once
 * turned on, each line prints the time since the page loaded as
 * HH:MM:SS, a dash, and what the line does.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { CONFIG } from './config';
import { required } from './lib/required';

// ########################################################################
// #                           Global constants                           #
// ########################################################################
// log.debug('Takes the milliseconds in a second, from the config')
const MS = CONFIG.units.ms_per_second;

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Notes when the page started, so each line shows elapsed time')
const STARTED = performance.now();
// log.debug('Sets the seconds in a minute and the minutes in an hour')
const SIXTY = 60;
// log.debug('Sets the seconds in an hour')
const HOUR_S = 3600;
// log.debug('Sets the digits in each part of the time')
const DIGITS = 2;

// ########################################################################
// #                             Trace logger                             #
// ########################################################################
// log.debug('Defines how elapsed time is written as HH:MM:SS')
/**
 * Returns the time since the page loaded as HH:MM:SS.
 *
 * @param now - The time to measure to, in milliseconds since the page's
 *   time origin.
 * @returns The elapsed time, each part two digits.
 */
export function elapsed(now: number = performance.now()): string {
  // log.debug('Converts the elapsed time to whole seconds')
  const total = Math.floor((now - STARTED) / MS);
  // log.debug('Splits it into hours, minutes and seconds')
  const parts = [Math.floor(total / HOUR_S), Math.floor((total % HOUR_S) / SIXTY), total % SIXTY];
  // log.debug('Returns the parts padded to two digits, joined by colons')
  return parts.map((part) => String(part).padStart(DIGITS, '0')).join(':');
}

// log.debug('Defines the logger the trace lines call')
export const logger = {
  /**
   * Prints one trace line: the elapsed time, a dash and the message.
   *
   * @param message - What the line does. Required.
   */
  debug(message: string | null = null): void {
    // log.debug('Takes the message, which the caller must give')
    message = required({ message });
    // log.debug('Prints the time, a dash and the message')
    console.debug(`${elapsed()} - ${message}`);
  },
};

// log.debug('Makes the logger global, so a trace line needs no import')
Object.assign(globalThis, { log: logger });

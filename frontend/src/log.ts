// ########################################################################
// #                         frontend/src/log.ts                          #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The trace logger: prints HH:MM:SS since page     #
// #                     load, a dash, and what the line does.            #
// ########################################################################
/** The trace logger: HH:MM:SS since the page loaded, a dash, the message. */

// log.debug('Notes when the page started, so each line shows elapsed time')
const STARTED = performance.now();
// log.debug('Sets the milliseconds in a second')
const MS = 1000;
// log.debug('Sets the seconds in a minute and the minutes in an hour')
const SIXTY = 60;
// log.debug('Sets the seconds in an hour')
const HOUR_S = 3600;
// log.debug('Sets the digits in each part of the time')
const DIGITS = 2;

// log.debug('Defines how elapsed time is written as HH:MM:SS')
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
  debug(message: string): void {
    // log.debug('Prints the time, a dash and the message')
    console.debug(`${elapsed()} - ${message}`);
  },
};

// log.debug('Makes the logger global, so a trace line needs no import')
Object.assign(globalThis, { log: logger });

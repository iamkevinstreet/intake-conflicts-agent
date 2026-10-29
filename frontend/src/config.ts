// ########################################################################
// #                        frontend/src/config.ts                        #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Frontend settings in one place: the API address, #
// #                     email limits, personas, thresholds.              #
// ########################################################################
/** Frontend settings: the only module that reads the build environment. */

import type { Persona } from './types';

// log.debug('Reads the API address; by default this origin, through the dev proxy')
export const API_BASE: string = import.meta.env.VITE_API_BASE ?? '/api/v1';
// log.debug('Sets the shortest email the API accepts')
export const MIN_EMAIL_CHARS = 20;
// log.debug('Sets the longest email the API accepts')
export const MAX_EMAIL_CHARS = 20_000;
// log.debug('Sets the shortest reason for approving past a flagged check')
export const MIN_REASON_CHARS = 10;
// log.debug('Sets the longest decision note the API accepts, as in settings.toml')
export const MAX_NOTE_CHARS = 500;
// log.debug('Lists the made-up people a developer can act as, in dev mode')
export const PERSONAS: readonly Persona[] = [
  { name: 'Avery Stone', role: 'requester' },
  { name: 'Casey Lin', role: 'requester' },
  { name: 'Jordan Reyes', role: 'approver' },
];
// log.debug('Names the provider that means the offline stand-in')
export const OFFLINE_PROVIDER = 'fake';
// log.debug('Sets the score thresholds the match meter marks, as in settings.toml')
export const THRESHOLDS = { possible: 80, likely: 92 } as const;

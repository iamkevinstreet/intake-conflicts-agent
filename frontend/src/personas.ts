// ########################################################################
// #                       frontend/src/personas.ts                       #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Lists the made-up people a developer can act as in dev mode, where
 * the API trusts the name and role headers the web app sends.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import type { Persona } from './types';

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Lists the made-up people a developer can act as, in dev mode')
export const PERSONAS: readonly Persona[] = [
  { name: 'Avery Stone', role: 'requester' },
  { name: 'Casey Lin', role: 'requester' },
  { name: 'Jordan Reyes', role: 'approver' },
];

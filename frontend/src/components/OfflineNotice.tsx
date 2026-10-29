// ########################################################################
// #              frontend/src/components/OfflineNotice.tsx               #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           A notice that fixed rules, not a model, are      #
// #                     playing the agent, and what they miss.           #
// ########################################################################
/** A notice that the offline stand-in, not a model, is playing the agent. */

import { OFFLINE_PROVIDER } from '../config';
import type { Health } from '../types';

interface Props {
  health: Health | null;
}

// log.debug('Defines the notice')
export function OfflineNotice({ health }: Props) {
  // log.debug('Shows nothing unless the stand-in is running')
  if (health?.provider !== OFFLINE_PROVIDER) {
    // log.debug('Returns nothing')
    return null;
  }
  // log.debug('Returns the notice')
  return (
    <p className="ia-notice" role="note">
      Offline mode: fixed rules play the agent, so no model is called and nothing leaves this
      machine. They miss companies named without a legal form, such as "Pinnacle Foods". Set{' '}
      <code>[llm] provider</code> to use a model.
    </p>
  );
}

// ########################################################################
// #              frontend/src/components/OfflineNotice.tsx               #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows a notice that fixed rules, not a model, are playing the agent,
 * and what they miss.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import type { Health } from '../types';

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Names the provider that means the offline stand-in')
const OFFLINE_PROVIDER = 'fake';

// ########################################################################
// #                            Offline notice                            #
// ########################################################################
interface Props {
  health?: Health | null;
}

// log.debug('Defines the notice')
/**
 * Shows the offline notice while the stand-in plays the agent.
 *
 * @param props - The notice's props.
 * @param props.health - The service's health report; null until it
 *   arrives.
 * @returns The notice, or nothing when a model is in use.
 */
export function OfflineNotice({ health = null }: Props = {}): React.JSX.Element | null {
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

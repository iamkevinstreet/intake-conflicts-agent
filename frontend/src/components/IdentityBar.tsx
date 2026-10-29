// ########################################################################
// #               frontend/src/components/IdentityBar.tsx                #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows who you are acting as: a made-up person in dev mode, or a note
 * in Entra ID mode.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { required } from '../lib/required';
import { PERSONAS } from '../personas';
import type { Health, Persona } from '../types';

// ########################################################################
// #                           Identity picker                            #
// ########################################################################
interface Props {
  health?: Health | null;
  persona?: Persona | null;
  onChange?: ((persona: Persona) => void) | null;
}

// log.debug('Defines the identity picker')
/**
 * Shows who you are acting as, and lets a developer switch person.
 *
 * @param props - The picker's props.
 * @param props.health - The service's health report; null until it
 *   arrives.
 * @param props.persona - The made-up person being acted as. Required.
 * @param props.onChange - Switches to another person. Required.
 * @returns The picker, or a note in Entra ID mode.
 */
export function IdentityBar({
  health = null,
  persona = null,
  onChange = null,
}: Props = {}): React.JSX.Element {
  // log.debug('Takes the person being acted as, which the caller must give')
  persona = required({ persona });
  // log.debug('Takes the change handler, which the caller must give')
  onChange = required({ onChange });
  // log.debug('Explains Entra ID mode, which this web app does not sign in to yet')
  if (health?.auth_mode === 'entra') {
    // log.debug('Returns the note')
    return (
      <p className="ia-identity ia-identity--note">
        This service checks Microsoft Entra ID tokens; signing in from this web app is not built
        yet.
      </p>
    );
  }
  // log.debug('Returns the dev picker')
  return (
    <label className="ia-identity">
      <span className="ia-identity__label">Acting as (dev)</span>
      <select
        className="ia-identity__select"
        value={persona.name}
        onChange={(event) => {
          // log.debug('Finds the chosen person')
          const chosen = PERSONAS.find((p) => p.name === event.target.value);
          // log.debug('Switches to them')
          if (chosen) {
            // log.debug('Hands the choice up')
            onChange(chosen);
          }
        }}
      >
        {PERSONAS.map((p) => (
          <option key={p.name} value={p.name}>
            {p.name}, {p.role}
          </option>
        ))}
      </select>
    </label>
  );
}

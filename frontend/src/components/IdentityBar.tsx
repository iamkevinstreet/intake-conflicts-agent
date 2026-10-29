// ########################################################################
// #               frontend/src/components/IdentityBar.tsx                #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Who you are acting as: a made-up person in dev   #
// #                     mode, or a note in Entra ID mode.                #
// ########################################################################
/** Who you are acting as: a made-up person in dev mode, or a note for Entra ID. */

import { PERSONAS } from '../config';
import type { Health, Persona } from '../types';

interface Props {
  health: Health | null;
  persona: Persona;
  onChange: (persona: Persona) => void;
}

// log.debug('Defines the identity picker')
export function IdentityBar({ health, persona, onChange }: Props) {
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

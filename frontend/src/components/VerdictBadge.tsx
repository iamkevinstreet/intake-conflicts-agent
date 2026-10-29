// ########################################################################
// #               frontend/src/components/VerdictBadge.tsx               #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           A verdict as a coloured label: conflict, a       #
// #                     person to decide, or clear.                      #
// ########################################################################
/** A verdict as a coloured label: conflict, a person to decide, or clear. */

import { VERDICTS } from '../format';
import type { Recommendation } from '../types';

interface Props {
  verdict: Recommendation;
  label?: string;
}

// log.debug('Defines the verdict badge')
export function VerdictBadge({ verdict, label }: Props) {
  // log.debug('Returns the badge, labelled if a label is given')
  return (
    <span className={`ia-verdict ia-verdict--${verdict}`}>
      {label && <span className="ia-verdict__label">{label}</span>}
      {VERDICTS[verdict]}
    </span>
  );
}

// ########################################################################
// #                frontend/src/components/MatchMeter.tsx                #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           A name-match score on a 0 to 100 bar, with the   #
// #                     possible and likely thresholds marked.           #
// ########################################################################
/** A match score on a 0 to 100 bar, with the two thresholds marked. */

import { BANDS } from '../format';
import { THRESHOLDS } from '../config';
import type { Match } from '../types';

interface Props {
  match: Match;
}

// log.debug('Defines the meter')
export function MatchMeter({ match }: Props) {
  // log.debug('Returns the bar, its marks and the band in words')
  return (
    <span className="ia-meter">
      <span
        className={`ia-meter__bar ia-meter__bar--${match.band}`}
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={match.score}
        aria-label={`Name match score ${String(match.score)} of 100`}
      >
        <span className="ia-meter__fill" style={{ width: `${String(match.score)}%` }} />
        <span className="ia-meter__mark" style={{ left: `${String(THRESHOLDS.possible)}%` }} />
        <span className="ia-meter__mark" style={{ left: `${String(THRESHOLDS.likely)}%` }} />
      </span>
      <span className="ia-meter__text">
        {match.score} · {BANDS[match.band]}
      </span>
    </span>
  );
}

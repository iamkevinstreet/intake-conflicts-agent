// ########################################################################
// #                frontend/src/components/MatchMeter.tsx                #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows a name-match score on a 0 to 100 bar, with the possible and
 * likely thresholds marked.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { CONFIG } from '../config';
import { BANDS } from '../format';
import { required } from '../lib/required';
import type { Match } from '../types';

// ########################################################################
// #                           Global constants                           #
// ########################################################################
// log.debug('Takes the score from which a person must decide, from the config')
const POSSIBLE = CONFIG.match.possible;
// log.debug('Takes the score from which two names are likely one party, from the config')
const LIKELY = CONFIG.match.likely;

// ########################################################################
// #                             Match meter                              #
// ########################################################################
interface Props {
  match?: Match | null;
}

// log.debug('Defines the meter')
/**
 * Shows one match's score on a bar marked at both thresholds.
 *
 * @param props - The meter's props.
 * @param props.match - The match whose score to show. Required.
 * @returns The bar, its marks and the band in words.
 */
export function MatchMeter({ match = null }: Props = {}): React.JSX.Element {
  // log.debug('Takes the match, which the caller must give')
  match = required({ match });
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
        <span className="ia-meter__mark" style={{ left: `${String(POSSIBLE)}%` }} />
        <span className="ia-meter__mark" style={{ left: `${String(LIKELY)}%` }} />
      </span>
      <span className="ia-meter__text">
        {match.score} · {BANDS[match.band]}
      </span>
    </span>
  );
}

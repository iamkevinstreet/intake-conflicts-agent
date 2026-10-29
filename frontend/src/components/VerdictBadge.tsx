// ########################################################################
// #               frontend/src/components/VerdictBadge.tsx               #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows a verdict as a coloured label: conflict, a person to decide, or
 * clear.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { VERDICTS } from '../format';
import { required } from '../lib/required';
import type { Recommendation } from '../types';

// ########################################################################
// #                            Verdict badge                             #
// ########################################################################
interface Props {
  verdict?: Recommendation | null;
  label?: string;
}

// log.debug('Defines the verdict badge')
/**
 * Shows a verdict in a few words, coloured by how serious it is.
 *
 * @param props - The badge's props.
 * @param props.verdict - The verdict to show. Required.
 * @param props.label - Words before the verdict; empty shows none.
 * @returns The badge.
 */
export function VerdictBadge({ verdict = null, label = '' }: Props = {}): React.JSX.Element {
  // log.debug('Takes the verdict, which the caller must give')
  verdict = required({ verdict });
  // log.debug('Returns the badge, labelled if a label is given')
  return (
    <span className={`ia-verdict ia-verdict--${verdict}`}>
      {label && <span className="ia-verdict__label">{label}</span>}
      {VERDICTS[verdict]}
    </span>
  );
}

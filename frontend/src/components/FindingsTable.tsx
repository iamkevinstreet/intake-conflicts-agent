// ########################################################################
// #              frontend/src/components/FindingsTable.tsx               #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows every match the run's searches found for the draft's parties:
 * the firm's record, how alike the names are, and why it matters.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { required } from '../lib/required';
import type { Finding } from '../types';
import { MatchMeter } from './MatchMeter';
import { VerdictBadge } from './VerdictBadge';

// ########################################################################
// #                            Findings table                            #
// ########################################################################
interface Props {
  findings?: Finding[];
}

// log.debug('Defines how a matched record is described')
/**
 * Returns what the firm's record is, in a few words.
 *
 * @param finding - The finding whose record to describe. Required.
 * @returns A client's standing, or the matter an adverse party was in,
 *   its status and the firm's client there.
 */
function record(finding: Finding | null = null): string {
  // log.debug('Takes the finding, which the caller must give')
  finding = required({ finding });
  // log.debug('Describes a client by its standing')
  if (finding.match.kind === 'client') {
    // log.debug('Returns current or former client')
    return `${finding.match.status} client`;
  }
  // log.debug('Describes an adverse party by its matter')
  return `against us in ${finding.match.matter ?? 'a matter'} (${finding.match.status}), for ${
    finding.match.matter_client ?? 'a client'
  }`;
}

// log.debug('Defines the findings table')
/**
 * Shows every finding: the party, the firm's record, the name match and
 * what it means.
 *
 * @param props - The table's props.
 * @param props.findings - The draft's findings; none shows a note.
 * @returns The table, or a note that the searches found nothing.
 */
export function FindingsTable({ findings = [] }: Props = {}): React.JSX.Element {
  // log.debug('Says so plainly when the searches found nothing')
  if (findings.length === 0) {
    // log.debug('Returns the empty state')
    return (
      <p className="ia-findings__none">
        No client or adverse party is close to any name on this draft.
      </p>
    );
  }
  // log.debug('Returns one row per finding')
  return (
    <table className="ia-table ia-findings">
      <caption className="ia-visually-hidden">Matches found by the conflicts searches</caption>
      <thead>
        <tr>
          <th scope="col">Party in the email</th>
          <th scope="col">Firm record</th>
          <th scope="col">Name match</th>
          <th scope="col">Means</th>
        </tr>
      </thead>
      <tbody>
        {findings.map((finding) => (
          <tr key={`${finding.side}-${finding.party}-${String(finding.match.id)}`}>
            <td>
              <span className="ia-findings__party">{finding.party}</span>
              <span className="ia-findings__side">
                {finding.side === 'client' ? 'prospective client' : 'other side'}
              </span>
            </td>
            <td>
              <span className="ia-findings__party">{finding.match.name}</span>
              <span className="ia-findings__side">{record(finding)}</span>
            </td>
            <td>
              <MatchMeter match={finding.match} />
            </td>
            <td>
              <VerdictBadge verdict={finding.severity} />
              <span className="ia-findings__why">{finding.why}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

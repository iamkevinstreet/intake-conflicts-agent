// ########################################################################
// #                 frontend/src/components/Verdicts.tsx                 #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Shows the verdict the approver sees beside the two it comes from: the
 * agent's and the checks'.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Local
import { required } from '../lib/required';
import type { Draft } from '../types';
import { VerdictBadge } from './VerdictBadge';

// ########################################################################
// #                          Verdict comparison                          #
// ########################################################################
interface Props {
  draft?: Draft | null;
}

// log.debug('Defines the verdicts block')
/**
 * Shows the verdict an approver sees, and the agent's and the checks'.
 *
 * @param props - The block's props.
 * @param props.draft - The draft whose verdicts to show. Required.
 * @returns The block, with a note when the checks overruled the agent.
 */
export function Verdicts({ draft = null }: Props = {}): React.JSX.Element {
  // log.debug('Takes the draft, which the caller must give')
  draft = required({ draft });
  // log.debug('Notes whether the checks overruled a milder agent')
  const overruled = draft.recommendation !== draft.agent_recommendation;
  // log.debug('Returns the shown verdict, then its two sources')
  return (
    <section className="ia-verdicts" aria-label="Verdict">
      <p className="ia-verdicts__shown">
        <span className="ia-verdicts__label">Shown to the approver</span>
        <VerdictBadge verdict={draft.recommendation} />
      </p>
      <dl className="ia-verdicts__sources">
        <div>
          <dt>The agent said</dt>
          <dd>
            <VerdictBadge verdict={draft.agent_recommendation} />
          </dd>
        </div>
        <div>
          <dt>The checks found</dt>
          <dd>
            <VerdictBadge verdict={draft.checks_recommendation} />
          </dd>
        </div>
      </dl>
      {overruled && (
        <p className="ia-verdicts__note">
          The checks found more than the agent reported, so the stricter verdict is shown.
        </p>
      )}
    </section>
  );
}

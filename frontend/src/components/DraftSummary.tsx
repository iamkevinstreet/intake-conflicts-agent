// ########################################################################
// #               frontend/src/components/DraftSummary.tsx               #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The agent's reading of the email: parties,       #
// #                     matter, timing, warnings, reasons, the email.    #
// ########################################################################
/** The agent's reading of the email: parties, matter, timing, its reasons. */

import type { DraftRecord } from '../types';

interface Props {
  record: DraftRecord;
}

// log.debug('Defines the draft summary')
export function DraftSummary({ record }: Props) {
  // log.debug('Takes the draft')
  const { draft } = record;
  // log.debug('Returns the reading, any warnings, the reasons and the email')
  return (
    <section className="ia-draft" aria-label="Draft matter">
      <dl className="ia-draft__facts">
        <div>
          <dt>Prospective client</dt>
          <dd>{draft.client}</dd>
        </div>
        <div>
          <dt>Other side</dt>
          <dd>
            {draft.adverse_parties.length > 0 ? draft.adverse_parties.join('; ') : 'None named'}
          </dd>
        </div>
        <div>
          <dt>Matter</dt>
          <dd>{draft.matter_type}</dd>
        </div>
        <div>
          <dt>Timing asked for</dt>
          <dd>{draft.timeline || 'None given'}</dd>
        </div>
      </dl>
      {draft.warnings.length > 0 && (
        <div className="ia-draft__warning" role="note">
          <p className="ia-draft__warning-title">
            The email gives orders to the agent. The gate does not depend on the agent obeying, but
            you should know:
          </p>
          <ul>
            {draft.warnings.map((line) => (
              <li key={line}>
                <q>{line}</q>
              </li>
            ))}
          </ul>
        </div>
      )}
      <h3 className="ia-draft__heading">The agent's summary</h3>
      <p className="ia-draft__prose">{draft.summary}</p>
      <h3 className="ia-draft__heading">The agent's reasons</h3>
      <p className="ia-draft__prose">{draft.agent_reasoning}</p>
      {record.note && (
        <>
          <h3 className="ia-draft__heading">Its note to the approver</h3>
          <p className="ia-draft__prose">{record.note}</p>
        </>
      )}
      <details className="ia-draft__email">
        <summary>The intake email, as pasted</summary>
        <pre className="ia-draft__email-text">{draft.email}</pre>
      </details>
    </section>
  );
}

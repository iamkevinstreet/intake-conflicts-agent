// ########################################################################
// #                frontend/src/components/DraftList.tsx                 #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The list of drafts to pick from: client, matter, #
// #                     verdict, status, who asked and when.             #
// ########################################################################
/** A list of drafts to pick from: client, matter, verdict, who asked. */

import { STATUSES, when } from '../format';
import type { DraftRecord } from '../types';
import { VerdictBadge } from './VerdictBadge';

interface Props {
  records: DraftRecord[];
  selected: string | null;
  onSelect: (id: string) => void;
}

// log.debug('Defines the list')
export function DraftList({ records, selected, onSelect }: Props) {
  // log.debug('Says so when there is nothing to review')
  if (records.length === 0) {
    // log.debug('Returns the empty state')
    return <p className="ia-list__none">No drafts here yet. Run an intake as a requester.</p>;
  }
  // log.debug('Returns one button per draft')
  return (
    <ul className="ia-list">
      {records.map((record) => (
        <li key={record.draft.id}>
          <button
            type="button"
            className="ia-list__item"
            aria-current={record.draft.id === selected ? 'true' : undefined}
            onClick={() => onSelect(record.draft.id)}
          >
            <span className="ia-list__client">{record.draft.client}</span>
            <span className="ia-list__matter">{record.draft.matter_type}</span>
            <VerdictBadge verdict={record.draft.recommendation} />
            <span className="ia-list__meta">
              {STATUSES[record.status]} · {record.draft.requester_name} ·{' '}
              {when(record.draft.created_at)}
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

// ########################################################################
// #                frontend/tests/ApprovalsPage.test.tsx                 #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Tests the approver's page: the reason rule, the decision and the
 * gate.
 */

// ########################################################################
// #                               Imports                                #
// ########################################################################
// Third-party
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

// Local
import { ApiError, api } from '../src/api';
import { ApprovalsPage } from '../src/pages/ApprovalsPage';
import type { DraftRecord } from '../src/types';
import { PENDING } from './fixtures';

// ########################################################################
// #                           Local constants                            #
// ########################################################################
// log.debug('Sets the approver the page acts as')
const JORDAN = { name: 'Jordan Reyes', role: 'approver' } as const;
// log.debug('Sets a reason long enough to approve past the flag')
const REASON = 'Waiver signed by both clients, on file.';
// log.debug('Sets the approval record an approved draft carries')
const APPROVAL = {
  approver: 'dev:jordan-reyes',
  approver_name: 'Jordan Reyes',
  decision: 'approved',
  note: REASON,
  decided_at: '2026-10-29T12:05:00+00:00',
} as const;

// ########################################################################
// #                         Approvals page tests                         #
// ########################################################################
// log.debug('Describes the approvals page')
describe('ApprovalsPage', () => {
  // log.debug('Checks the gate stays shut until approval, then opens')
  it('needs a reason, then approves, then opens the matter', async () => {
    // log.debug('Builds the approved version of the draft')
    const approved: DraftRecord = { ...PENDING, status: 'approved', approval: APPROVAL };
    // log.debug('Stubs the list: pending first, approved after the decision')
    vi.spyOn(api, 'drafts').mockResolvedValueOnce([PENDING]).mockResolvedValue([approved]);
    // log.debug('Stubs the decision')
    const decide = vi.spyOn(api, 'decide').mockResolvedValue(approved);
    // log.debug('Stubs the opening')
    const open = vi.spyOn(api, 'open').mockResolvedValue({
      number: 'NM-00001',
      opened_by: 'dev:jordan-reyes',
      opened_by_name: 'Jordan Reyes',
      opened_at: '2026-10-29T12:06:00+00:00',
    });
    // log.debug('Renders the page')
    render(<ApprovalsPage persona={JORDAN} />);
    // log.debug('Picks the draft')
    await userEvent.click(await screen.findByRole('button', { name: /Juniper Hollow Farms/ }));
    // log.debug('Checks the gate is shut and approving needs a reason')
    expect(screen.getByRole('button', { name: 'Open the matter' })).toBeDisabled();
    // log.debug('Checks approve is off with no reason')
    expect(screen.getByRole('button', { name: 'Approve' })).toBeDisabled();
    // log.debug('Writes the reason')
    await userEvent.type(screen.getByLabelText(/Your reason/), REASON);
    // log.debug('Clicks approve')
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }));
    // log.debug('Checks the decision was sent with the reason')
    expect(decide).toHaveBeenCalledWith(JORDAN, PENDING.draft.id, 'approved', REASON);
    // log.debug('Opens the now-approved matter')
    await userEvent.click(await screen.findByRole('button', { name: 'Open the matter' }));
    // log.debug('Checks the opening was asked for')
    expect(open).toHaveBeenCalledWith(JORDAN, PENDING.draft.id);
  });

  // log.debug('Checks a refusal from the server is shown')
  it('shows the gate refusal the server gives', async () => {
    // log.debug('Stubs an approved draft')
    vi.spyOn(api, 'drafts').mockResolvedValue([
      { ...PENDING, status: 'approved', approval: APPROVAL },
    ]);
    // log.debug('Stubs the server refusing to open')
    vi.spyOn(api, 'open').mockRejectedValue(new ApiError(409, 'already open', 'req-1'));
    // log.debug('Renders the page')
    render(<ApprovalsPage persona={JORDAN} />);
    // log.debug('Shows every draft, not only those waiting')
    await userEvent.click(await screen.findByRole('button', { name: /^All/ }));
    // log.debug('Picks the approved draft')
    await userEvent.click(screen.getByRole('button', { name: /Juniper Hollow Farms/ }));
    // log.debug('Clicks open')
    await userEvent.click(screen.getByRole('button', { name: 'Open the matter' }));
    // log.debug('Checks the explanation appears')
    expect(await screen.findByRole('alert')).toHaveTextContent('already open (request req-1)');
  });
});

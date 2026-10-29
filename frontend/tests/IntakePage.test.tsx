// ########################################################################
// #                  frontend/tests/IntakePage.test.tsx                  #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Tests the requester's page end to end against a  #
// #                     stubbed API.                                     #
// ########################################################################
/** Tests the requester's page end to end against a stubbed API. */

import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { api } from '../src/api';
import { IntakePage } from '../src/pages/IntakePage';
import { DETAIL, EXAMPLES, SUBMITTED } from './fixtures';

// log.debug('Sets the requester the page acts as')
const AVERY = { name: 'Avery Stone', role: 'requester' } as const;

// log.debug('Describes the intake page')
describe('IntakePage', () => {
  // log.debug('Checks a run shows its outcome, the overruled verdict and the steps')
  it('shows the outcome, the stricter verdict and every step', async () => {
    // log.debug('Stubs the examples')
    vi.spyOn(api, 'examples').mockResolvedValue(EXAMPLES);
    // log.debug('Stubs the intake')
    const intake = vi.spyOn(api, 'intake').mockResolvedValue(SUBMITTED);
    // log.debug('Stubs the audit trail')
    vi.spyOn(api, 'run').mockResolvedValue(DETAIL);
    // log.debug('Renders the page')
    render(<IntakePage persona={AVERY} />);
    // log.debug('Loads the example into the form')
    await userEvent.click(await screen.findByRole('button', { name: EXAMPLES[0]?.title ?? '' }));
    // log.debug('Runs the intake')
    await userEvent.click(screen.getByRole('button', { name: 'Run the intake' }));
    // log.debug('Checks the outcome banner')
    expect(await screen.findByText('Sent to an approver')).toBeVisible();
    // log.debug('Checks the checks overruled the agent')
    expect(screen.getByText(/stricter verdict is shown/)).toBeVisible();
    // log.debug('Checks the finding names the firm record')
    expect(screen.getByText('ACME Logistics LLC')).toBeVisible();
    // log.debug('Checks the steps list shows the search')
    expect(screen.getByText('search_clients')).toBeVisible();
    // log.debug('Checks the email was sent as the requester')
    expect(intake).toHaveBeenCalledWith(AVERY, EXAMPLES[0]?.email.trim());
  });

  // log.debug('Checks an approver is told to switch')
  it('asks an approver to switch to a requester', () => {
    // log.debug('Renders the page as an approver')
    render(<IntakePage persona={{ name: 'Jordan Reyes', role: 'approver' }} />);
    // log.debug('Checks the message')
    expect(screen.getByText(/Switch to a requester/)).toBeVisible();
  });

  // log.debug('Checks a short email cannot be sent')
  it('keeps the run button off for a short email', async () => {
    // log.debug('Stubs the examples')
    vi.spyOn(api, 'examples').mockResolvedValue([]);
    // log.debug('Renders the page')
    render(<IntakePage persona={AVERY} />);
    // log.debug('Types a few words')
    await userEvent.type(screen.getByLabelText('Intake email'), 'Too short');
    // log.debug('Checks the button is off')
    expect(screen.getByRole('button', { name: 'Run the intake' })).toBeDisabled();
  });
});

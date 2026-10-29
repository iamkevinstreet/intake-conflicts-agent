// ########################################################################
// #                      frontend/tests/fixtures.ts                      #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Made-up API responses the page tests stub the    #
// #                     client with.                                     #
// ########################################################################
/** Made-up API responses the page tests stub the client with. */

import type { DraftRecord, Example, IntakeResponse, RunDetail } from '../src/types';

// log.debug('Sets a pending draft whose checks found a conflict the agent missed')
export const PENDING: DraftRecord = {
  draft: {
    id: 'D-0123456789',
    run_id: 'R-0123456789',
    requester: 'dev:avery-stone',
    requester_name: 'Avery Stone',
    created_at: '2026-10-29T12:00:00+00:00',
    client: 'Juniper Hollow Farms LLC',
    adverse_parties: ['Acme Logistic Inc.'],
    matter_type: 'wage claim cross-claim',
    timeline: 'answer due in 21 days',
    summary: 'A farm wants a cross-claim against its staffing supplier.',
    agent_recommendation: 'clear',
    agent_reasoning: 'No client of the firm is named.',
    findings: [
      {
        party: 'Acme Logistic Inc.',
        side: 'adverse',
        match: {
          kind: 'client',
          id: 1,
          name: 'ACME Logistics LLC',
          score: 96,
          band: 'likely',
          status: 'current',
        },
        severity: 'conflict',
        why: 'the other side is a current client',
      },
    ],
    checks_recommendation: 'conflict',
    recommendation: 'conflict',
    warnings: [],
    email: 'Made-up intake email.',
    email_sha256: 'a'.repeat(64),
  },
  status: 'pending',
  note: 'Please look at the Acme match.',
  approval: null,
  matter: null,
};

// log.debug('Sets the intake response that produced it')
export const SUBMITTED: IntakeResponse = {
  run: {
    id: 'R-0123456789',
    requester: 'dev:avery-stone',
    requester_name: 'Avery Stone',
    started_at: '2026-10-29T12:00:00+00:00',
    finished_at: '2026-10-29T12:00:03+00:00',
    email_sha256: 'a'.repeat(64),
    email_chars: 400,
    model: 'fake-model',
    outcome: 'submitted',
    reason: 'sent to an approver',
    draft_id: 'D-0123456789',
    steps: 3,
    tool_calls: 4,
    input_tokens: 2400,
    output_tokens: 300,
    cost_usd: 0,
    ms: 3000,
  },
  draft: PENDING,
  text: '',
};

// log.debug('Sets the run detail for the steps list')
export const DETAIL: RunDetail = {
  run: SUBMITTED.run,
  model_calls: [
    {
      step: 1,
      input_tokens: 800,
      output_tokens: 100,
      cost_usd: 0,
      ms: 900,
      stop_reason: 'tool_use',
    },
  ],
  tool_calls: [
    {
      seq: 1,
      step: 1,
      tool: 'search_clients',
      arguments: { name: 'Acme Logistic Inc.' },
      ok: true,
      error: '',
      result_sha256: 'b'.repeat(64),
      ms: 3,
      at: '2026-10-29T12:00:01+00:00',
    },
  ],
};

// log.debug('Sets one example email')
export const EXAMPLES: Example[] = [
  { id: 's04', title: 'A client name, typed differently', email: 'We need help. '.repeat(3) },
];

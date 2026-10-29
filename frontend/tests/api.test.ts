// ########################################################################
// #                      frontend/tests/api.test.ts                      #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           Tests the API client's identity headers and      #
// #                     errors, and the formatting helpers.              #
// ########################################################################
/** Tests the API client: identity headers and error explanations. */

import { describe, expect, it, vi } from 'vitest';

import { ApiError, api, describeError } from '../src/api';
import { argumentsLine, money } from '../src/format';

// log.debug('Describes the client')
describe('api', () => {
  // log.debug('Checks every call says who is acting')
  it('sends the dev identity headers', async () => {
    // log.debug('Stubs fetch to answer an empty list')
    const fetcher = vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response('[]'));
    // log.debug('Lists the runs as a requester')
    await api.runs({ name: 'Avery Stone', role: 'requester' });
    // log.debug('Reads the headers sent')
    const headers = new Headers(fetcher.mock.calls[0]?.[1]?.headers);
    // log.debug('Checks both identity headers')
    expect([headers.get('X-Dev-User'), headers.get('X-Dev-Role')]).toEqual([
      'Avery Stone',
      'requester',
    ]);
  });

  // log.debug('Checks a refusal carries its message and request id')
  it('explains a refusal with its request id', async () => {
    // log.debug('Stubs fetch to refuse')
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'no approval record' }), {
        status: 409,
        headers: { 'X-Request-ID': 'req-9' },
      }),
    );
    // log.debug('Tries to open a matter and keeps the error')
    const error = await api
      .open({ name: 'Jordan Reyes', role: 'approver' }, 'D-0123456789')
      .catch((caught: unknown) => caught);
    // log.debug('Checks the error and its explanation')
    expect([error instanceof ApiError, describeError(error)]).toEqual([
      true,
      'no approval record (request req-9)',
    ]);
  });
});

// log.debug('Describes the formatting helpers')
describe('format', () => {
  // log.debug('Checks costs and tool arguments read well')
  it('writes money and tool arguments for people', () => {
    // log.debug('Checks a cost, an unpriced cost and three kinds of arguments')
    expect([
      money(0.0123),
      money(null),
      argumentsLine({ name: 'Acme' }),
      argumentsLine({ draft_id: 'D-1' }),
      argumentsLine({ client: 'Falcon', adverse_parties: ['A', 'B'] }),
    ]).toEqual(['$0.0123', '-', '"Acme"', 'D-1', 'Falcon, 2 other parties']);
  });
});

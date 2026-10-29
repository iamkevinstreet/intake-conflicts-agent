// ########################################################################
// #                         frontend/src/api.ts                          #
// ########################################################################
// #  Author:            Kevin Street                                     #
// #  Created on:        2026-10-29                                       #
// #  Last modified on:  2026-10-29                                       #
// #  Purpose:           The API client: one function per route, the dev  #
// #                     identity headers, and errors that say why.       #
// ########################################################################
/** The API client: one function per route, and errors that say what happened. */

import { API_BASE } from './config';
import type {
  Actor,
  Decision,
  DraftRecord,
  DraftStatus,
  Example,
  Health,
  IntakeResponse,
  NewMatter,
  Persona,
  RunDetail,
  RunRecord,
} from './types';

// log.debug('Names the header that carries the request id')
const REQUEST_ID = 'X-Request-ID';

// log.debug('Defines the error every failed call raises')
export class ApiError extends Error {
  // log.debug('Defines the constructor with the status and request id')
  constructor(
    readonly status: number,
    message: string,
    readonly requestId: string | null,
  ) {
    // log.debug('Passes the message to Error')
    super(message);
    // log.debug('Names the error for logs and tests')
    this.name = 'ApiError';
  }
}

// log.debug('Defines the headers that say who is acting, in dev mode')
export function identity(persona: Persona): Record<string, string> {
  // log.debug('Returns the name and role headers the dev sign-in reads')
  return { 'X-Dev-User': persona.name, 'X-Dev-Role': persona.role };
}

// log.debug('Defines one call to the API')
async function call<T>(path: string, persona: Persona | null, init: RequestInit = {}): Promise<T> {
  // log.debug('Copies the given headers, whatever form they came in')
  const headers = new Headers(init.headers);
  // log.debug('Marks the body as JSON')
  headers.set('Content-Type', 'application/json');
  // log.debug('Adds who is acting, when someone is')
  if (persona !== null) {
    // log.debug('Sets each identity header')
    for (const [name, value] of Object.entries(identity(persona))) {
      // log.debug('Sets the header')
      headers.set(name, value);
    }
  }
  // log.debug('Sends the request')
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  // log.debug('Throws with the server explanation when the call failed')
  if (!response.ok) {
    // log.debug('Throws the error with its status and request id')
    throw new ApiError(response.status, await detail(response), response.headers.get(REQUEST_ID));
  }
  // log.debug('Returns the parsed body')
  return (await response.json()) as T;
}

// log.debug('Defines how a failed response is explained')
async function detail(response: Response): Promise<string> {
  // log.debug('Sets the fallback explanation')
  const fallback = `The request failed with status ${response.status}.`;
  // log.debug('Reads the body, which may not be JSON')
  try {
    // log.debug('Parses the body')
    const body = (await response.json()) as { detail?: unknown };
    // log.debug('Returns a plain message as it is')
    if (typeof body.detail === 'string') {
      // log.debug('Returns it')
      return body.detail;
    }
    // log.debug('Joins a list of validation messages')
    if (Array.isArray(body.detail)) {
      // log.debug('Returns each message, joined')
      return body.detail.map((item: { msg?: string }) => item.msg ?? '').join('; ');
    }
    // log.debug('Returns the fallback for any other body')
    return fallback;
  } catch {
    // log.debug('Returns the fallback when the body is not JSON')
    return fallback;
  }
}

// log.debug('Defines one function per route')
export const api = {
  health: (): Promise<Health> => call('/health', null),
  me: (persona: Persona): Promise<Actor> => call('/me', persona),
  examples: (persona: Persona): Promise<Example[]> => call('/examples', persona),
  intake: (persona: Persona, email: string): Promise<IntakeResponse> =>
    call('/intake', persona, { method: 'POST', body: JSON.stringify({ email }) }),
  drafts: (persona: Persona, status?: DraftStatus): Promise<DraftRecord[]> =>
    call(status ? `/drafts?status=${status}` : '/drafts', persona),
  draft: (persona: Persona, id: string): Promise<DraftRecord> =>
    call(`/drafts/${encodeURIComponent(id)}`, persona),
  decide: (persona: Persona, id: string, decision: Decision, note: string): Promise<DraftRecord> =>
    call(`/drafts/${encodeURIComponent(id)}/decision`, persona, {
      method: 'POST',
      body: JSON.stringify({ decision, note }),
    }),
  open: (persona: Persona, id: string): Promise<NewMatter> =>
    call(`/drafts/${encodeURIComponent(id)}/open`, persona, { method: 'POST' }),
  runs: (persona: Persona): Promise<RunRecord[]> => call('/runs', persona),
  run: (persona: Persona, id: string): Promise<RunDetail> =>
    call(`/runs/${encodeURIComponent(id)}`, persona),
};

// log.debug('Defines the sentence shown when a call fails')
export function describeError(error: unknown): string {
  // log.debug('Explains an API error with its request id, for support')
  if (error instanceof ApiError) {
    // log.debug('Returns the server explanation and the request id')
    return error.requestId ? `${error.message} (request ${error.requestId})` : error.message;
  }
  // log.debug('Explains a network failure: the service did not answer')
  return 'The service did not answer. Check that the backend is running with make run.';
}

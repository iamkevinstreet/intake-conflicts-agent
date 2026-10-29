// ########################################################################
// #                        frontend/src/types.ts                         #
// ########################################################################
/**
 * Author:            Kevin Street
 * Created on:        2026-10-29
 * Last modified on:  2026-10-29
 *
 * Defines the API's shapes in TypeScript, as the backend's pydantic
 * models return them.
 */

// ########################################################################
// #                              API shapes                              #
// ########################################################################
export type Recommendation = 'clear' | 'review' | 'conflict';

export type Severity = 'review' | 'conflict';

export type Band = 'exact' | 'likely' | 'possible';

export type Role = 'requester' | 'approver';

export type DraftStatus = 'draft' | 'pending' | 'approved' | 'rejected' | 'opened';

export type Outcome = 'running' | 'submitted' | 'no_draft' | 'incomplete' | 'failed';

export type Decision = 'approved' | 'rejected';

export interface Actor {
  user_id: string;
  name: string;
  roles: Role[];
}

export interface Match {
  kind: 'client' | 'adverse_party';
  id: number;
  name: string;
  score: number;
  band: Band;
  status: string;
  matter?: string | null;
  matter_client?: string | null;
}

export interface Finding {
  party: string;
  side: 'client' | 'adverse';
  match: Match;
  severity: Severity;
  why: string;
}

export interface Draft {
  id: string;
  run_id: string;
  requester: string;
  requester_name: string;
  created_at: string;
  client: string;
  adverse_parties: string[];
  matter_type: string;
  timeline: string;
  summary: string;
  agent_recommendation: Recommendation;
  agent_reasoning: string;
  findings: Finding[];
  checks_recommendation: Recommendation;
  recommendation: Recommendation;
  warnings: string[];
  email: string;
  email_sha256: string;
}

export interface Approval {
  approver: string;
  approver_name: string;
  decision: Decision;
  note: string;
  decided_at: string;
}

export interface NewMatter {
  number: string;
  opened_by: string;
  opened_by_name: string;
  opened_at: string;
}

export interface DraftRecord {
  draft: Draft;
  status: DraftStatus;
  note: string;
  approval: Approval | null;
  matter: NewMatter | null;
}

export interface RunRecord {
  id: string;
  requester: string;
  requester_name: string;
  started_at: string;
  finished_at: string | null;
  email_sha256: string;
  email_chars: number;
  model: string;
  outcome: Outcome;
  reason: string;
  draft_id: string | null;
  steps: number;
  tool_calls: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
  ms: number;
}

export interface ModelCall {
  step: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number | null;
  ms: number;
  stop_reason: string;
}

export interface ToolCall {
  seq: number;
  step: number;
  tool: string;
  arguments: Record<string, unknown>;
  ok: boolean;
  error: string;
  result_sha256: string;
  ms: number;
  at: string;
}

export interface RunDetail {
  run: RunRecord;
  model_calls: ModelCall[];
  tool_calls: ToolCall[];
}

export interface IntakeResponse {
  run: RunRecord;
  draft: DraftRecord | null;
  text: string;
}

export interface Example {
  id: string;
  title: string;
  email: string;
}

export interface Health {
  status: 'ok';
  version: string;
  auth_mode: 'dev' | 'entra';
  provider: string;
  model: string;
  firm: Record<string, number>;
}

/** A person to act as in dev mode: the name and role sent as headers. */
export interface Persona {
  name: string;
  role: Role;
}

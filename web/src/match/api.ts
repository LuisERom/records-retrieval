// Types mirror the Pydantic models in api.py.

export interface Location {
  npi: string;
  name: string;
  address: string;
  city: string;
  zip: string;
  phone: string;
  fax: string;
  taxonomy: string;
  is_pharmacy: boolean;
  score: number | null;
}

export interface Evaluation {
  query_id: string;
  split: string;
  expected: Location[];
  label_method: string;
  note: string;
  matcher_correct: boolean;
  matcher_strict_correct: boolean;
  baseline_correct: boolean;
}

export type Reason = "no_candidates" | "low_score" | "too_close";

export interface MatchResponse {
  answered: boolean;
  npi: string | null;
  reason: Reason | null;
  confidence: number;
  margin: number;
  min_score: number;
  min_margin: number;
  top: Location | null;
  same_in_registry: Location[];
  runners_up: Location[];
  baseline: Location | null;
  evaluation: Evaluation | null;
}

export interface Query {
  id: string;
  split: string;
  name: string;
  address: string;
  zip: string;
  expected_npi: string;
  label_method: string;
  note: string;
}

export interface Health {
  npis: number;
  locations: number;
  queries: number;
  min_score: number;
  min_margin: number;
}

export interface MatchInput {
  name: string;
  address: string;
  zip: string;
  query_id?: string;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, init);
  if (!r.ok) {
    let detail = `${r.status} ${r.statusText}`;
    try {
      const body = await r.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new Error(detail);
  }
  return (await r.json()) as T;
}

export const getHealth = () => call<Health>("/api/health");
export const getQueries = () => call<Query[]>("/api/queries?split=test");
export const postMatch = (body: MatchInput) =>
  call<MatchResponse>("/api/match", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

export interface ExplainCandidate {
  npi: string;
  name: string;
  address: string;
  taxonomy: string;
  name_forward: number;
  name_reverse: number;
  name_score: number;
  address_score: number | null;
  total: number;
  same_as_top: boolean;
}

export interface Explain {
  typed_name: string;
  typed_address: string;
  typed_zip: string;
  name_tokens: string[];
  house: string;
  street: string[];
  zip: string;
  blocked_by: string;
  pharmacies_skipped: number;
  candidates_considered: number;
  locations_total: number;
  weights: { name: number; address: number; reverse_share_of_name: number };
  candidates: ExplainCandidate[];
  min_score: number;
  min_margin: number;
  top_score: number;
  next_different_score: number;
  margin: number;
  answered: boolean;
  reason: string | null;
  baseline_name: string | null;
}

export const postExplain = (body: MatchInput) =>
  call<Explain>("/api/match/explain", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

// Types mirror the Pydantic models in api.py.

export interface CaseInfo {
  split: string;
  case: string;
  pages: number;
  patient: string;
  accident_date: string;
}

export interface PageInfo {
  page: number;
  kept: boolean;
  copy_of: number;
  mechanism: string;
  doc_kind: string;
  key_says_duplicate: boolean;
  correct: boolean;
}

export interface Group {
  kept: number;
  copies: number[];
  label: string;
}

export interface DedupView {
  pages: PageInfo[];
  groups: Group[];
  total: number;
  kept: number;
  removed: number;
  key_duplicates: number;
  lost: string[];
}

export interface Citation {
  page: number;
  quote: string;
}

export interface Entry {
  date: string;
  provider: string;
  kind: string;
  summary: string;
  diagnosis_codes: string[];
  procedure_codes: string[];
  citations: Citation[];
  matches_key: boolean;
}

export interface Dropped {
  date: string;
  provider: string;
  kind: string;
  reason: string;
}

export interface ChronologyView {
  source: "claude" | "oracle";
  note: string;
  entries: Entry[];
  dropped: Dropped[];
  events_in_key: number;
  events_found: number;
  usage: { input_tokens?: number; output_tokens?: number; calls?: number };
}

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return (await r.json()) as T;
}

const base = (split: string, c: string) => `/api/cases/${encodeURIComponent(split)}/${encodeURIComponent(c)}`;

export const getCases = () => get<CaseInfo[]>("/api/cases");
export const getDedup = (s: string, c: string) => get<DedupView>(`${base(s, c)}/dedup`);
export const getChronology = (s: string, c: string) => get<ChronologyView>(`${base(s, c)}/chronology`);
export const pageUrl = (s: string, c: string, n: number) => `${base(s, c)}/pages/${n}.png`;
export const getHighlight = (s: string, c: string, n: number, quote: string) =>
  get<Box[]>(`${base(s, c)}/pages/${n}/highlight?quote=${encodeURIComponent(quote)}`);

export interface Count {
  label: string;
  pages: number;
}

export interface PairView {
  a: number;
  b: number;
  a_how: string;
  b_how: string;
  phrases_a: number;
  phrases_b: number;
  shared: number;
  containment: number;
  numbers_only_a: string[];
  numbers_only_b: string[];
  duplicate: boolean;
  why: string;
}

export interface WalkthroughData {
  pages: number;
  originals_in_key: number;
  by_source: Count[];
  by_how: Count[];
  clean_page: number;
  clean_kept_page: number;
  clean_lines: { text: string; removed: boolean }[];
  ocr_pairs: string[][];
  duplicate_pair: PairView;
  hard_negative: PairView | null;
  groups: number;
  removed: number;
  kept: number;
  largest: { label: string; copies: number; kept: number };
  batch_size: number;
  batches: number;
  min_containment: number;
}

export interface Check {
  check: string;
  ok: boolean;
  detail: string;
}

export interface CheckedEntry {
  date: string;
  kind: string;
  provider: string;
  summary: string;
  checks: Check[];
  kept: boolean;
  reason: string;
}

export interface CheckerDemo {
  passing: CheckedEntry | null;
  offered: number;
  kept: number;
  kept_wrong: number;
  falsified: CheckedEntry[];
}

export const getWalkthrough = (s: string, c: string) => get<WalkthroughData>(`${base(s, c)}/walkthrough`);
export const getCheckerDemo = (s: string, c: string) => get<CheckerDemo>(`${base(s, c)}/checker-demo`);

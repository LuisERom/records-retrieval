import { FormEvent, useEffect, useRef, useState } from "react";
import MatchWalkthrough from "./MatchWalkthrough";
import {
  getHealth,
  getQueries,
  postMatch,
  type Health,
  type Location,
  type MatchInput,
  type MatchResponse,
  type Query,
} from "./api";

// Hand-picked to show each behavior; any typed query works the same way.
const EXAMPLES: { label: string; shows: string; input: MatchInput }[] = [
  { label: "Misspelled name", shows: "A typo still finds the right clinic.", input: { name: "NYU Fertlity Center", address: "660 1st Ave", zip: "10016" } },
  { label: "Name only on a pharmacy record", shows: "The name belongs to a pharmacy; v2 skips it and finds the clinic.", input: { name: "NYU Langone ortho", address: "333 E 38th St", zip: "10016" } },
  { label: "Registry twins", shows: "Two records the registry itself can't tell apart.", input: { name: "NYU Hematology Associates", address: "160 E 34th St", zip: "10016" } },
  { label: "Old hospital name", shows: "A hospital still filed under its pre-merger name.", input: { name: "Winthrop University Hospital", address: "259 First St", zip: "11501" } },
  { label: "Not NYU Langone", shows: "A different health system: it should refuse.", input: { name: "Mount Sinai cardiology", address: "1 Gustave L Levy Pl", zip: "10029" } },
];

const LABEL_METHODS: Record<string, string> = {
  written_from_record: "written from this record",
  hospital_any_of: "a hospital campus filed under several NPIs; any of them counts",
  registry_near_duplicate: "one practice filed under several NPIs with slightly different names",
  any_of_judgment: "genuinely ambiguous; any listed record counts",
  not_in_registry: "no right record in the registry; the right answer is to abstain",
};

export default function App({ tour = false }: { tour?: boolean }) {
  const [form, setForm] = useState<MatchInput>({ name: "", address: "", zip: "" });
  const [queryId, setQueryId] = useState<string | null>(null);
  const [result, setResult] = useState<MatchResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [queries, setQueries] = useState<Query[]>([]);
  const [ran, setRan] = useState<MatchInput | null>(null);
  const [explain, setExplain] = useState(false);
  const explainRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getHealth().then(setHealth).catch((e: Error) => setError(`Could not reach the API: ${e.message}`));
    getQueries().then(setQueries).catch(() => setQueries([]));
  }, []);

  // The tour: run the first example and open its walkthrough.
  useEffect(() => {
    if (!tour) return;
    const ex = EXAMPLES[0].input;
    setForm(ex);
    setQueryId(null);
    run(ex).then(() => setExplain(true));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tour]);

  useEffect(() => {
    if (explain) explainRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [explain, ran]);

  async function run(input: MatchInput) {
    setLoading(true);
    setError(null);
    setRan({ name: input.name, address: input.address, zip: input.zip });
    try {
      setResult(await postMatch(input));
    } catch (e) {
      setResult(null);
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }

  function edit(field: keyof MatchInput, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
    setQueryId(null); // an edited query no longer has a label to score against
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!form.name.trim()) return;
    run({ ...form, query_id: queryId ?? undefined });
  }

  function tryExample(input: MatchInput) {
    setForm(input);
    setQueryId(null);
    run(input);
  }

  function randomTestQuery() {
    if (!queries.length) return;
    const q = queries[Math.floor(Math.random() * queries.length)];
    const input = { name: q.name, address: q.address, zip: q.zip };
    setForm(input);
    setQueryId(q.id);
    run({ ...input, query_id: q.id });
  }

  return (
    <div className="page">
      <header>
        <h1>Find the provider</h1>
        <p className="lede">
          Type a provider the way an intake form would. The matcher finds the NYU Langone location in the public
          NPI Registry, or says it can't tell instead of guessing.
        </p>
        {health && (
          <p className="meta">
            {health.npis} NPIs at {health.locations} practice locations. Answers only when the score is at least{" "}
            {health.min_score} and at least {health.min_margin} ahead of the next different record.
          </p>
        )}
      </header>

      <form className="card form" onSubmit={submit}>
        <label>
          Provider name
          <input
            value={form.name}
            onChange={(e) => edit("name", e.target.value)}
            placeholder="NYU Langone ortho"
            autoFocus
            required
          />
        </label>
        <div className="row">
          <label className="grow">
            Street address
            <input value={form.address} onChange={(e) => edit("address", e.target.value)} placeholder="333 E 38th St" />
          </label>
          <label className="zip">
            ZIP
            <input value={form.zip} onChange={(e) => edit("zip", e.target.value)} placeholder="10016" inputMode="numeric" />
          </label>
        </div>
        <div className="actions">
          <button type="submit" disabled={loading || !form.name.trim()}>
            {loading ? "Matching…" : "Match"}
          </button>
          <button type="button" className="secondary" onClick={randomTestQuery} disabled={loading || !queries.length}>
            Random held-out test query
          </button>
          {queryId && <span className="tag">test query {queryId}: scored against its label</span>}
        </div>
        <div className="examples-head">Or start from a ready-made example, each picked to show one behavior:</div>
        <div className="examples-grid">
          {EXAMPLES.map((ex) => (
            <button key={ex.label} type="button" className="example" onClick={() => tryExample(ex.input)} disabled={loading}>
              <strong>{ex.label}</strong>
              <span>{ex.shows}</span>
            </button>
          ))}
        </div>
      </form>

      {error && <div className="card error">{error}</div>}
      {result && ran && (
        <div className="explain-bar">
          <button type="button" className={explain ? "secondary" : ""} onClick={() => setExplain(!explain)}>
            {explain ? "Hide the step-by-step" : "How did it decide? See it step by step"}
          </button>
        </div>
      )}
      <div ref={explainRef}>{explain && ran && <MatchWalkthrough input={ran} onClose={() => setExplain(false)} />}</div>
      {result && <Result r={result} />}

      <footer>
        Public NPI Registry data, cached. No patient data. The test queries were written for this project, not taken
        from real intake. Source and evaluation: <code>python evaluate.py</code>.
      </footer>
    </div>
  );
}

function Result({ r }: { r: MatchResponse }) {
  return (
    <section className="result">
      {r.evaluation && <Verdict r={r} />}

      {r.answered && r.top ? (
        <div className="card">
          <div className="status ok">Match</div>
          <LocationView loc={r.top} big />
          {r.top.is_pharmacy && (
            <p className="warn">
              This is a pharmacy record. A records request should not go here; the strict scoring counts this answer
              as wrong.
            </p>
          )}
          {r.same_in_registry.length > 0 && (
            <div className="twins">
              <h3>The registry can't tell these apart</h3>
              <p className="muted">
                Same name on the door and same street address as the match, under a different NPI. Returned together
                instead of picking one at random.
              </p>
              {r.same_in_registry.map((l) => (
                <LocationView key={l.npi} loc={l} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="card">
          <div className="status none">No confident match</div>
          <p>{reasonText(r)}</p>
          {r.top && (
            <>
              <h3>Closest record (not returned)</h3>
              <LocationView loc={r.top} />
            </>
          )}
        </div>
      )}

      <div className="card">
        <h3>Scores</h3>
        <Meter label="Confidence" value={r.confidence} threshold={r.min_score} />
        <Meter label="Lead over next different record" value={r.margin} threshold={r.min_margin} max={0.3} />
      </div>

      {r.runners_up.length > 0 && (
        <div className="card">
          <h3>Runners-up</h3>
          {r.runners_up.map((l) => (
            <LocationView key={l.npi} loc={l} />
          ))}
        </div>
      )}

      {r.baseline && (
        <div className="card">
          <h3>Closest-name baseline would pick</h3>
          <p className="muted">Fuzzy match on the name alone, ignoring the address, never abstaining.</p>
          <LocationView loc={r.baseline} />
        </div>
      )}
    </section>
  );
}

function Verdict({ r }: { r: MatchResponse }) {
  const ev = r.evaluation!;
  const strictDiffers = ev.matcher_correct !== ev.matcher_strict_correct;
  return (
    <div className={`card verdict ${ev.matcher_strict_correct ? "good" : "bad"}`}>
      <h3>
        Test query {ev.query_id}:{" "}
        {ev.matcher_strict_correct ? "matcher right" : r.answered ? "matcher wrong" : "matcher abstained"}
        {strictDiffers && " (counted right by the label, wrong by the strict reading)"}
      </h3>
      <p>
        Baseline: {ev.baseline_correct ? "right" : "wrong"}. Label: {LABEL_METHODS[ev.label_method] ?? ev.label_method}.
        {ev.note && <> Note: {ev.note}</>}
      </p>
      {ev.expected.length > 0 ? (
        <div className="expected">
          <span className="muted">Labeled answer{ev.expected.length > 1 ? "s" : ""}:</span>
          {ev.expected.map((l) => (
            <span key={l.npi} className="pill">
              {l.name} · {l.npi}
            </span>
          ))}
        </div>
      ) : (
        <p className="muted">Labeled answer: none (the right answer is "no confident match").</p>
      )}
    </div>
  );
}

function reasonText(r: MatchResponse): string {
  switch (r.reason) {
    case "no_candidates":
      return "No record in the registry cache to compare against.";
    case "low_score":
      return `The best record scored ${r.confidence}, below the ${r.min_score} needed to answer.`;
    case "too_close":
      return `The best record scored ${r.confidence}, but the next different record is only ${r.margin} behind (it needs ${r.min_margin}). Too close to call.`;
    default:
      return "";
  }
}

function LocationView({ loc, big }: { loc: Location; big?: boolean }) {
  return (
    <div className={`loc ${big ? "big" : ""}`}>
      <div className="loc-head">
        <span className="loc-name">{loc.name}</span>
        {loc.is_pharmacy && <span className="badge">pharmacy</span>}
        {loc.score !== null && <span className="score">score {loc.score}</span>}
      </div>
      <div>
        {loc.address}, {loc.city} {loc.zip}
      </div>
      <div className="muted">
        {loc.taxonomy || "no taxonomy listed"} · NPI{" "}
        <a href={`https://npiregistry.cms.hhs.gov/provider-view/${loc.npi}`} target="_blank" rel="noreferrer">
          {loc.npi}
        </a>
      </div>
      <div className="muted">
        Phone {loc.phone || "not listed"} · Fax {loc.fax || "not listed"}
      </div>
    </div>
  );
}

function Meter({ label, value, threshold, max = 1 }: { label: string; value: number; threshold: number; max?: number }) {
  const pct = (x: number) => `${Math.max(0, Math.min(100, (x / max) * 100))}%`;
  const pass = value >= threshold;
  return (
    <div className="meter">
      <div className="meter-label">
        <span>{label}</span>
        <span className={pass ? "pass" : "fail"}>
          {value} {pass ? "≥" : "<"} {threshold}
        </span>
      </div>
      <div className="track">
        <div className={`fill ${pass ? "pass" : "fail"}`} style={{ width: pct(value) }} />
        <div className="mark" style={{ left: pct(threshold) }} title={`threshold ${threshold}`} />
      </div>
    </div>
  );
}

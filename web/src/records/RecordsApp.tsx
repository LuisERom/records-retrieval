import { useEffect, useMemo, useState } from "react";
import { getCases, getChronology, getDedup, type CaseInfo, type ChronologyView, type DedupView, type Entry } from "./api";
import { KIND_LABEL, mechanismLabel, PageViewer, type Cite, type Sel } from "./shared";
import RecordsWalkthrough from "./RecordsWalkthrough";


export default function App({ tour = false }: { tour?: boolean }) {
  const [cases, setCases] = useState<CaseInfo[]>([]);
  const [sel, setSel] = useState<Sel | null>(null);
  const [tab, setTab] = useState<"how" | "chronology" | "duplicates">(tour ? "how" : "chronology");
  useEffect(() => {
    if (tour) setTab("how");
  }, [tour]);
  const [dedup, setDedup] = useState<DedupView | null>(null);
  const [chron, setChron] = useState<ChronologyView | null>(null);
  const [cite, setCite] = useState<Cite | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getCases()
      .then((cs) => {
        setCases(cs);
        const first = cs.find((c) => c.split === "test2") ?? cs[0];
        if (first) setSel({ split: first.split, case: first.case });
      })
      .catch((e: Error) => setError(`Could not reach the API: ${e.message}`));
  }, []);

  useEffect(() => {
    if (!sel) return;
    setLoading(true);
    setDedup(null);
    setChron(null);
    setCite(null);
    Promise.all([getDedup(sel.split, sel.case), getChronology(sel.split, sel.case)])
      .then(([d, c]) => {
        setDedup(d);
        setChron(c);
        const e = c.entries[0];
        if (e?.citations[0]) setCite({ page: e.citations[0].page, quote: e.citations[0].quote });
        setError(null);
      })
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [sel]);

  const info = sel && cases.find((c) => c.split === sel.split && c.case === sel.case);

  return (
    <div className="page">
      <header>
        <div className="title">
          <h1>Process the records</h1>
          <p className="muted">
            Duplicate pages removed, then a dated timeline where every entry is
            checked against the page it cites. Synthetic case files; no real patient data.
          </p>
        </div>
        <label className="picker">
          Case file
          <select
            value={sel ? `${sel.split}|${sel.case}` : ""}
            onChange={(e) => {
              const [split, c] = e.target.value.split("|");
              setSel({ split, case: c });
            }}
          >
            {["test2", "alt2", "alt3", "alt4", "alt5"].map((s) => (
              <optgroup key={s} label={{ test2: "Main test set (this repo's generator)", alt2: "Independent set 2 (never-seen generator)", alt3: "Independent set 3 (never-seen generator)", alt4: "Independent set 4 (never-seen generator)", alt5: "Independent set 5 (never-seen generator)" }[s] ?? s}>
                {cases
                  .filter((c) => c.split === s)
                  .map((c) => (
                    <option key={c.case} value={`${c.split}|${c.case}`}>
                      {c.patient} · {c.pages} pages
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
        </label>
      </header>

      {error && <div className="card error">{error}</div>}
      {loading && <div className="card muted">Removing duplicate pages and checking the timeline for this case file. This takes 10 to 20 seconds the first time.</div>}

      {dedup && chron && sel && info && (
        <>
          <section className="stats">
            <Stat label="Pages received" value={dedup.total} />
            <Stat label="Duplicates removed" value={dedup.removed} sub={`${Math.floor((1000 * dedup.removed) / dedup.total) / 10}% of the file`} />
            <Stat label="Pages kept" value={dedup.kept} />
            <Stat
              label="Unique pages lost"
              value={dedup.lost.length}
              sub="by the answer key"
              tone={dedup.lost.length ? "bad" : "good"}
            />
            <Stat label="Timeline entries" value={chron.entries.length} sub={`${chron.events_found} of ${chron.events_in_key} encounters in the key`} />
            <Stat label="Dropped by the checker" value={chron.dropped.length} tone={chron.dropped.length ? "warn" : undefined} />
          </section>

          <nav className="tabs">
            <button className={tab === "chronology" ? "on" : ""} onClick={() => setTab("chronology")}>
              Timeline ({chron.entries.length} entries)
            </button>
            <button className={tab === "duplicates" ? "on" : ""} onClick={() => setTab("duplicates")}>
              Duplicates ({dedup.groups.length} groups)
            </button>
            <button className={tab === "how" ? "on" : ""} onClick={() => setTab("how")}>
              How it works (step by step)
            </button>
          </nav>

          {tab === "how" && <RecordsWalkthrough sel={sel} dedup={dedup} chron={chron} goTo={setTab} />}
          {tab === "chronology" && <ChronologyTab sel={sel} chron={chron} dedup={dedup} cite={cite} setCite={setCite} />}
          {tab === "duplicates" && <DuplicatesTab sel={sel} dedup={dedup} />}
        </>
      )}
    </div>
  );
}

function Stat({ label, value, sub, tone }: { label: string; value: number; sub?: string; tone?: "good" | "bad" | "warn" }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

function ChronologyTab({
  sel,
  chron,
  dedup,
  cite,
  setCite,
}: {
  sel: Sel;
  chron: ChronologyView;
  dedup: DedupView;
  cite: Cite | null;
  setCite: (c: Cite) => void;
}) {
  return (
    <div className="split">
      <div className="left">
        <div className={`source ${chron.source}`}>
          <strong>{chron.source === "claude" ? "Claude" : "Oracle"}</strong> {chron.note}
        </div>
        <ol className="timeline">
          {chron.entries.map((e, i) => (
            <EntryRow key={i} e={e} cite={cite} setCite={setCite} />
          ))}
        </ol>
        {chron.dropped.length > 0 && (
          <div className="card">
            <h3>Dropped by the checker</h3>
            <p className="muted">Entries whose quote, date or code was not on the cited page, even after one repair.</p>
            <ul className="dropped">
              {chron.dropped.map((d, i) => (
                <li key={i}>
                  <strong>
                    {d.date} · {KIND_LABEL[d.kind] ?? d.kind}
                  </strong>{" "}
                  {d.provider}
                  <div className="muted">{d.reason}</div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      <div className="right">
        {cite ? (
          <PageViewer sel={sel} dedup={dedup} page={cite.page} quote={cite.quote} onGoto={(p) => setCite({ page: p, quote: null })} />
        ) : (
          <div className="card muted">Pick a citation to see its page.</div>
        )}
      </div>
    </div>
  );
}

function EntryRow({ e, cite, setCite }: { e: Entry; cite: Cite | null; setCite: (c: Cite) => void }) {
  const active = cite && e.citations.some((c) => c.page === cite.page && c.quote === cite.quote);
  return (
    <li className={`entry ${active ? "active" : ""}`}>
      <div className="entry-head">
        <span className="date">{e.date}</span>
        <span className={`kind k-${e.kind}`}>{KIND_LABEL[e.kind] ?? e.kind}</span>
        <span className="provider">{e.provider}</span>
      </div>
      <div className="summary">{e.summary}</div>
      {(e.diagnosis_codes.length > 0 || e.procedure_codes.length > 0) && (
        <div className="codes">
          {e.diagnosis_codes.map((c) => (
            <span key={c} className="code">
              {c}
            </span>
          ))}
          {e.procedure_codes.map((c) => (
            <span key={c} className="code cpt">
              {c}
            </span>
          ))}
        </div>
      )}
      <div className="cites">
        {e.citations.map((c, i) => (
          <button
            key={i}
            className={`cite ${cite && cite.page === c.page && cite.quote === c.quote ? "on" : ""}`}
            onClick={() => setCite({ page: c.page, quote: c.quote })}
            title={c.quote}
          >
            p. {c.page}
          </button>
        ))}
      </div>
    </li>
  );
}


function DuplicatesTab({ sel, dedup }: { sel: Sel; dedup: DedupView }) {
  const groups = useMemo(() => [...dedup.groups].sort((a, b) => b.copies.length - a.copies.length || a.kept - b.kept), [dedup]);
  const [g, setG] = useState(0);
  const [copy, setCopy] = useState<number | null>(null);
  const [zoom, setZoom] = useState(1);
  const wrong = dedup.pages.filter((p) => !p.correct);
  const group = groups[g];
  const shown = copy ?? group?.copies[0] ?? null;

  return (
    <div className="split dup">
      <div className="left">
        <div className="card">
          <p className="small">
            Each group is one page of the record and the copies of it found elsewhere in the file. The most complete copy
            is kept. Pages whose decision disagrees with the answer key:{" "}
            <strong className={wrong.length ? "wrong" : "right"}>{wrong.length}</strong>
            {dedup.lost.length > 0 && <> · originals with no copy kept: {dedup.lost.join(", ")}</>}
          </p>
        </div>
        <ul className="groups">
          {groups.map((gr, i) => (
            <li key={gr.kept}>
              <button
                className={i === g ? "on" : ""}
                onClick={() => {
                  setG(i);
                  setCopy(null);
                }}
              >
                <span className="glabel">{gr.label || `Page ${gr.kept}`}</span>
                <span className="muted">
                  kept p. {gr.kept} · {gr.copies.length} cop{gr.copies.length === 1 ? "y" : "ies"} removed
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
      <div className="right">
        {group && (
          <>
            <div className="card copies">
              <span className="muted small">Removed copies:</span>
              {group.copies.map((p) => (
                <button key={p} className={`cite ${p === shown ? "on" : ""}`} onClick={() => setCopy(p)}>
                  p. {p} · {mechanismLabel(dedup.pages[p - 1]?.mechanism ?? "")}
                </button>
              ))}
            </div>
            <div className="compare">
              <PageViewer sel={sel} dedup={dedup} page={group.kept} quote={null} onGoto={() => {}} compact zoom={zoom} onZoom={setZoom} />
              {shown && <PageViewer sel={sel} dedup={dedup} page={shown} quote={null} onGoto={() => {}} compact zoom={zoom} onZoom={setZoom} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

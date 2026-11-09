import { useEffect, useState } from "react";
import Walkthrough, { Tokens, Verdict, type Step } from "../Walkthrough";
import { getCheckerDemo, getWalkthrough, type CheckedEntry, type CheckerDemo, type ChronologyView, type DedupView, type PairView, type WalkthroughData } from "./api";
import { KIND_LABEL, mechanismLabel, PageViewer, type Sel } from "./shared";

function Bars({ items, total }: { items: { label: string; pages: number }[]; total: number }) {
  return (
    <div>
      {items.map((it) => (
        <div className="wt-bar" key={it.label}>
          <span className="lbl" title={it.label}>
            {it.label}
          </span>
          <span className="bar">
            <div style={{ width: `${(100 * it.pages) / total}%` }} />
          </span>
          <span className="v">{it.pages}</span>
        </div>
      ))}
    </div>
  );
}

function Pair({ sel, dedup, p, highlightA, highlightB }: { sel: Sel; dedup: DedupView; p: PairView; highlightA?: string; highlightB?: string }) {
  return (
    <>
      <div className="wt-kv">
        <span>Phrases on each page</span>
        <span>
          p. {p.a}: {p.phrases_a} · p. {p.b}: {p.phrases_b}
        </span>
        <span>Shared phrases</span>
        <span>
          {p.shared} = <strong>{Math.floor(p.containment * 100)}%</strong> of the shorter page
        </span>
        <span>Numbers only on p. {p.a}</span>
        <Tokens items={p.numbers_only_a} tone={p.numbers_only_a.length ? "del" : "plain"} />
        <span>Numbers only on p. {p.b}</span>
        <Tokens items={p.numbers_only_b} tone={p.numbers_only_b.length ? "del" : "plain"} />
      </div>
      <Verdict ok={p.duplicate}>{p.why}</Verdict>
      <div className="wt-two" style={{ marginTop: 10 }}>
        <PageViewer sel={sel} dedup={dedup} page={p.a} quote={highlightA ?? null} onGoto={() => {}} compact />
        <PageViewer sel={sel} dedup={dedup} page={p.b} quote={highlightB ?? null} onGoto={() => {}} compact />
      </div>
    </>
  );
}

function CheckList({ e }: { e: CheckedEntry }) {
  return (
    <div className="card checked">
      <div>
        <strong>
          {e.date} · {KIND_LABEL[e.kind] ?? e.kind}
        </strong>{" "}
        <span className="muted">{e.provider}</span>
      </div>
      <div className="small">{e.summary}</div>
      <ul className="checks">
        {e.checks.map((c, k) => (
          <li key={k} className={c.ok ? "ok" : "bad"}>
            <span className="mark">{c.ok ? "✓" : "✗"}</span> {c.check}
            <div className="muted small">{c.detail}</div>
          </li>
        ))}
      </ul>
      <div className={e.kept ? "right small" : "wrong small"}>{e.kept ? "Kept in the timeline." : `Dropped: ${e.reason}`}</div>
    </div>
  );
}

export default function RecordsWalkthrough({
  sel,
  dedup,
  chron,
  goTo,
}: {
  sel: Sel;
  dedup: DedupView;
  chron: ChronologyView;
  goTo: (tab: "chronology" | "duplicates") => void;
}) {
  const [w, setW] = useState<WalkthroughData | null>(null);
  const [demo, setDemo] = useState<CheckerDemo | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setW(null);
    setDemo(null);
    Promise.all([getWalkthrough(sel.split, sel.case), getCheckerDemo(sel.split, sel.case)])
      .then(([a, b]) => {
        setW(a);
        setDemo(b);
      })
      .catch((e: Error) => setError(e.message));
  }, [sel]);

  if (error) return <div className="card error">{error}</div>;
  if (!w || !demo) return <div className="card muted">Preparing the walkthrough for this case file…</div>;

  const hard = w.hard_negative;
  const dateLike = (xs: string[]) => xs.find((t) => /\d{2}\/\d{2}\/\d{4}/.test(t)) ?? xs[0];
  const steps: Step[] = [
    {
      id: "arrived",
      short: "What arrived",
      title: "What arrived",
      lead: `${w.pages} pages, from every provider that answered the request plus the auto insurer's claim file. The answer key says only ${w.originals_in_key} of them are different pages; the rest are copies.`,
      rules: ["The method never sees the answer key. It is used only to label and score what the method did."],
      body: (
        <div className="wt-two">
          <div>
            <h4>Who sent the pages</h4>
            <Bars items={w.by_source} total={w.pages} />
          </div>
          <div>
            <h4>How each copy was made (answer key)</h4>
            <Bars items={w.by_how.map((x) => ({ label: mechanismLabel(x.label === "original" ? "original" : x.label.replace("cropped ", "crop+")), pages: x.pages }))} total={w.pages} />
          </div>
        </div>
      ),
    },
    {
      id: "clean",
      short: "Ignore what copying adds",
      title: "Ignore what copying adds",
      lead: `Copies of one page are never identical: each picks up a fax header, a "received" stamp, a Bates number and scan errors. Here is page ${w.clean_page}, a copy, with the lines that are ignored struck out.`,
      rules: [
        "Ignored lines: fax transmission headers, \"RECEIVED\" stamps, Bates numbers, \"Page x of y\". They are recognized even when the scan garbled them.",
        "Characters scanners confuse are treated as the same: 0/O, 1/l/i, 5/S, 8/B, rn/m.",
      ],
      body: (
        <>
          <div className="wt-lines">
            {w.clean_lines.map((l, k) => (
              <div key={k} className={l.removed ? "gone" : ""}>
                {l.text}
              </div>
            ))}
          </div>
          {w.ocr_pairs.length > 0 && (
            <>
              <h4>Scan errors that still count as the same word</h4>
              <table>
                <thead>
                  <tr>
                    <th>On this copy (p. {w.clean_page})</th>
                    <th>On the kept copy (p. {w.clean_kept_page})</th>
                  </tr>
                </thead>
                <tbody>
                  {w.ocr_pairs.map(([a, b]) => (
                    <tr key={a}>
                      <td>
                        <code>{a}</code>
                      </td>
                      <td>
                        <code>{b}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      ),
    },
    {
      id: "same",
      short: "Compare two copies",
      title: "Compare two copies of one page",
      lead: `Each page becomes a set of five-word phrases. Page ${w.duplicate_pair.b} and page ${w.duplicate_pair.a} are the same record: almost every phrase matches, and so does every date and number.`,
      rules: [
        `Duplicates need at least ${Math.round(w.min_containment * 100)}% of the shorter page's phrases on the other page (so a cropped copy still counts)…`,
        "…and every date, amount and code on one page must appear on the other.",
      ],
      status: "ok",
      body: <Pair sel={sel} dedup={dedup} p={w.duplicate_pair} />,
    },
    {
      id: "hard",
      short: "The hard case",
      title: "The hard case: alike, but not a copy",
      lead: hard
        ? `Physical therapy notes are written from a template, so two visits look almost the same. Pages ${hard.a} and ${hard.b} share most of their wording, but they are different visits, and throwing one away would lose a visit from the timeline.`
        : "This case file has no near-identical pair of therapy notes.",
      rules: [
        "Wording alone is never enough: a different date or number means a different record.",
        "A number that is really a misread word (\"0f\" for \"of\") does not count as different.",
      ],
      status: "stop",
      body: hard ? (
        <Pair sel={sel} dedup={dedup} p={hard} highlightA={dateLike(hard.numbers_only_a)} highlightB={dateLike(hard.numbers_only_b)} />
      ) : (
        <p className="muted">Pick another case file to see one.</p>
      ),
    },
    {
      id: "group",
      short: "Keep one of each",
      title: "Keep the most complete copy of each page",
      lead: `Copies are grouped, and the most complete copy in each group is kept: ${w.removed} pages removed, ${w.kept} kept.`,
      rules: [
        "A page joins a group only by matching that group's most complete page directly, never through another copy.",
        "Why: a copy cropped so badly that its dates are gone could otherwise link two different documents, and one of them would be thrown away. The first version did exactly that; this rule is the fix.",
      ],
      body: (
        <>
          <div className="wt-kv">
            <span>Groups of copies</span>
            <strong>{w.groups}</strong>
            <span>Pages removed</span>
            <strong>{w.removed}</strong>
            <span>Pages kept</span>
            <strong>{w.kept}</strong>
            <span>Most copied page</span>
            <span>
              {w.largest.label} (kept p. {w.largest.kept}, {w.largest.copies} copies removed)
            </span>
            <span>Unique pages lost (answer key)</span>
            <strong className={dedup.lost.length ? "wrong" : "right"}>{dedup.lost.length}</strong>
          </div>
          <button className="linkish" onClick={() => goTo("duplicates")}>
            See every group, kept page beside each removed copy →
          </button>
        </>
      ),
    },
    {
      id: "timeline",
      short: "Build the timeline",
      title: "Build the timeline",
      lead: `The ${w.kept} kept pages go to the model in ${w.batches} batches of up to ${w.batch_size}. It returns one entry per visit, test or procedure, each with the page numbers and exact quotes it relied on.`,
      rules: [
        "The answer is structured JSON in a fixed schema: date, provider, kind, one-sentence summary, codes, 1 to 3 citations.",
        "Every citation is a page number plus 5 to 25 words copied exactly from that page.",
        "Bills, claim forms, fax covers and authorizations are not timeline entries.",
      ],
      body: (
        <>
          <div className={`source ${chron.source}`}>
            <strong>{chron.source === "claude" ? "Claude" : "Oracle"}</strong> {chron.note}
          </div>
          <div className="wt-kv">
            <span>Timeline entries</span>
            <strong>{chron.entries.length}</strong>
            <span>Encounters in the answer key found</span>
            <strong>
              {chron.events_found} of {chron.events_in_key}
            </strong>
          </div>
          <button className="linkish" onClick={() => goTo("chronology")}>
            Open the timeline and click any citation to see its page →
          </button>
        </>
      ),
    },
    {
      id: "check",
      short: "Check every entry",
      title: "Check every entry against its page",
      lead:
        `Code, not the model, checks each entry. To show it working, it was just handed this case's timeline with 30% of the entries falsified (a made-up quote or a wrong date): of ${demo.offered} entries it kept ${demo.kept}, ` +
        (demo.kept_wrong === 0
          ? "and every falsified one was dropped."
          : `and ${demo.kept_wrong} falsified ${demo.kept_wrong === 1 ? "entry" : "entries"} got through: a wrong date that the cited page could not rule out, because that date is also printed on it and the page has no date-of-service label the checker could read.`),
      rules: [
        "Each quote must be on the page it cites (spacing, capitals and scan look-alikes aside).",
        "The entry's date, and every code it lists, must be written on a cited page.",
        "A failing answer gets one repair attempt; entries that still fail are dropped, never kept.",
      ],
      status: "ok",
      body: (
        <>
          {demo.passing && (
            <>
              <h4>An entry that passes</h4>
              <CheckList e={demo.passing} />
            </>
          )}
          <h4>Falsified entries it caught</h4>
          <div className="checked-grid">
            {demo.falsified.slice(0, 4).map((e, k) => (
              <CheckList key={k} e={e} />
            ))}
          </div>
        </>
      ),
    },
  ];

  return (
    <Walkthrough
      title="How it works, on this case file"
      subtitle={<>Every number and page below comes from running the pipeline on {sel.case}. Pick another case file above to see it again.</>}
      steps={steps}
    />
  );
}

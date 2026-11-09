import { useEffect, useState } from "react";

type Saved = { command: string; text: string | null };
type OverviewData = Record<string, Saved>;

function upTo(text: string | null, stop: string): string {
  if (!text) return "";
  const i = text.indexOf(stop);
  return (i >= 0 ? text.slice(0, i) : text).trimEnd();
}

// One raw evaluation printout, shown only inside "Exact evaluation output".
function Raw({ title, saved, cut }: { title: string; saved?: Saved; cut?: string }) {
  if (!saved?.text) return null;
  return (
    <div className="ov-raw">
      <h4>{title}</h4>
      <div className="cmd">$ {saved.command}</div>
      <pre>{cut ? upTo(saved.text, cut) : saved.text.trimEnd()}</pre>
    </div>
  );
}

function Metric({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div className="ov-metric">
      <div className="v">{value}</div>
      <div className="l">{label}</div>
      {sub && <div className="s">{sub}</div>}
    </div>
  );
}

// Duplicate removal (the default method) on files from generators it was never built on.
const NEVER_SEEN = [
  { set: "Independent set 2", removed: "57.1%", lost: "0 of 1,227" },
  { set: "Independent set 3", removed: "22.9%", lost: "2 of 1,032" },
  { set: "Independent set 4", removed: "81.7%", lost: "1 of 1,361" },
  { set: "Independent set 5", removed: "80.6%", lost: "12 of 1,223" },
];

export default function Overview() {
  const [data, setData] = useState<OverviewData | null>(null);
  useEffect(() => {
    fetch("/api/overview")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setData({}));
  }, []);

  return (
    <div className="ov">
      <h1>Getting a patient's medical records, in two steps</h1>
      <p className="lede">
        A personal-injury firm needs a client's complete medical records. Two things make that slow: knowing exactly which office
        to ask, and making sense of the hundreds of pages that come back. This is a small, measured version of each.
      </p>

      <div className="ov-flow">
        <div className="ov-box">
          <div className="ov-step">Step 1</div>
          <h3>Find the provider</h3>
          <p>"NYU Langone ortho, 333 E 38th": which of 444 registered NYU Langone entities is that? It picks one, with its NPI, or says it can't tell.</p>
          <a className="ov-go" href="#match">
            Try it
          </a>
          <a className="ov-go ghost" href="#match/tour">
            How it works
          </a>
        </div>
        <div className="ov-arrow">→</div>
        <div className="ov-box dim">
          <div className="ov-step">Not built here</div>
          <h3>Send and chase the request</h3>
          <p>Fax, portal, mail and follow-up calls until the records arrive.</p>
        </div>
        <div className="ov-arrow">→</div>
        <div className="ov-box">
          <div className="ov-step">Step 2</div>
          <h3>Process the records</h3>
          <p>About 400 pages arrive, most of them copies. Remove the duplicates, then build a dated timeline where every entry is checked against its page.</p>
          <a className="ov-go" href="#records">
            Explore a case file
          </a>
          <a className="ov-go ghost" href="#records/tour">
            How it works
          </a>
        </div>
      </div>

      <h2>Results</h2>
      <p className="ov-note">Each number says what it was measured on.</p>

      <div className="ov-card">
        <h3>Step 1 · Find the provider</h3>
        <div className="ov-metrics">
          <Metric value="97.9%" label="right when it answers" sub="1,000 test queries" />
          <Metric value="60.3%" label="for picking the closest name" sub="the simple baseline" />
          <Metric value="81%" label="of queries answered" sub="the rest: “can't tell”, not a guess" />
        </div>
        <p className="ov-read">
          Queries are real registry records made messy: typos, abbreviations, dropped suites and ZIP codes, and names that aren't NYU
          Langone at all. A wrong office means a records request that comes back weeks later with nothing, so the matcher would rather
          say it can't tell.
        </p>
      </div>

      <div className="ov-card">
        <h3>Step 2 · Remove duplicate pages</h3>
        <div className="ov-metrics">
          <Metric value="99.3%" label="of duplicates removed" sub="16 case files from this repo's own generator" />
          <Metric value="16 of 2,269" label="unique pages lost" sub="merged into a look-alike page" />
        </div>
        <p className="ov-read">
          The harder test: case files from four record generators written separately, with their own layouts, stamps, fax headers and
          scan damage, none of which the method was built on. (Set 1 was used while building it, so it isn't listed.)
        </p>
        <table className="ov-table">
          <thead>
            <tr>
              <th>Never-seen files</th>
              <th>Duplicates removed</th>
              <th>Unique pages lost</th>
            </tr>
          </thead>
          <tbody>
            {NEVER_SEEN.map((r) => (
              <tr key={r.set}>
                <td>{r.set}</td>
                <td>{r.removed}</td>
                <td>{r.lost}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="ov-read muted">
          Where it falls short: copies carrying stamps in wordings it has never seen stay in (set 3), and a corrected billing statement
          can be merged into the original (most of set 5's losses).
        </p>
      </div>

      <div className="ov-card">
        <h3>Step 2 · Build the timeline</h3>
        <div className="ov-metrics">
          <Metric value="351 of 352" label="visits, tests and procedures found" sub="11 held-out case files" />
          <Metric value="0" label="entries invented" sub="351 of 351 correct" />
          <Metric value="99.8%" label="citations on the right record" sub="829 of 830" />
        </div>
        <p className="ov-read">
          Claude reads the kept pages and returns each entry with the page and the exact words it relied on. Then code, not the model,
          checks every entry: the quote must be on the cited page, and the date must be the visit's date, not a signature or fax date.
          Entries that fail are dropped.
        </p>
        <p className="ov-read muted">
          The check, tested on its own on a never-seen generator with 30% of answers deliberately falsified: 470 of the 472 entries it
          kept were correct. It also dropped 13 of 626 correct entries, mostly where a title like "PROGRESS REPORT 04/21/23" makes the
          visit date look like a report date.
        </p>
      </div>

      <details className="ov-details">
        <summary>Exact evaluation output</summary>
        <p className="ov-read muted">Printed by the evaluation scripts and saved in the repo; the numbers above come from these.</p>
        {!data && <p className="muted">Loading…</p>}
        <Raw title="Find the provider: 1,000 generated test queries" saved={data?.matching_generated} cut="matcher v2: of the" />
        <Raw title="Duplicate removal: 16 case files from this repo's generator" saved={data?.dedup_test2} cut="content lost by this method v2" />
        <Raw title="Duplicate removal: independent set 2" saved={data?.dedup_alt2} cut="content lost by this method v2" />
        <Raw title="Duplicate removal: independent set 3" saved={data?.dedup_alt3} cut="  of those, with words" />
        <Raw title="Duplicate removal: independent set 4" saved={data?.dedup_alt4} cut="  of those, with words" />
        <Raw title="Duplicate removal: independent set 5" saved={data?.dedup_alt5} cut="  of those, with words" />
        <Raw title="Timeline built by Claude: 11 held-out case files" saved={data?.chronology_claude_test2} cut="events found by kind" />
        <Raw title="The check, with 30% of answers falsified: independent set 5" saved={data?.checker_alt5} cut="events found by kind" />
        <p className="ov-read muted">
          The tables also list earlier versions of each method ("v1", "v3"). The default is v2. How each version was built and tested,
          and why, is in the repo README.
        </p>
      </details>

      <p className="ov-foot">
        No real patient data: step 1 uses public NPI Registry records; step 2 uses invented patients and providers.{" "}
        <a href="https://github.com/LuisERom/records-retrieval">Code and full write-up on GitHub</a>.
      </p>
    </div>
  );
}

import { useEffect, useState } from "react";
import Walkthrough, { Tokens, Verdict, type Step } from "../Walkthrough";
import { postExplain, type Explain, type MatchInput } from "./api";

const REASON: Record<string, string> = {
  low_score: "the best record scored below the bar",
  too_close: "the next different record scored too close to call",
  no_candidates: "there was nothing to compare against",
};

export default function MatchWalkthrough({ input, onClose }: { input: MatchInput; onClose: () => void }) {
  const [x, setX] = useState<Explain | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    setX(null);
    postExplain({ name: input.name, address: input.address, zip: input.zip })
      .then(setX)
      .catch((e: Error) => setError(e.message));
  }, [input.name, input.address, input.zip]);

  if (error) return <div className="card error">{error}</div>;
  if (!x) return <div className="card muted">Loading the walkthrough…</div>;

  const top = x.candidates[0];
  const pct = (v: number) => `${Math.round(v * 100)}%`;
  const steps: Step[] = [
    {
      id: "typed",
      short: "What was typed",
      title: "What was typed",
      lead: "The lookup starts from exactly what a person typed on the intake form, mistakes and all.",
      rules: ["Nothing is added or looked up first: the name, street address and ZIP are all it has."],
      body: (
        <div className="wt-kv">
          <span>Provider name</span>
          <strong>{x.typed_name || "—"}</strong>
          <span>Street address</span>
          <strong>{x.typed_address || "— (none)"}</strong>
          <span>ZIP</span>
          <strong>{x.typed_zip || "— (none)"}</strong>
        </div>
      ),
    },
    {
      id: "clean",
      short: "Clean it up",
      title: "Clean it up",
      lead: "People and the registry write the same thing differently, so both sides are put into one standard form before comparing.",
      rules: [
        "Abbreviations made uniform: Street → ST, East → E, First → 1, Orthopaedic / Orthopedic / ortho → ORTHO, New York University → NYU.",
        "Suite, floor and room numbers are dropped from the address: a suite is part of the same location.",
        "ZIP cut to 5 digits; filler words (the, of, inc, LLC) ignored.",
      ],
      body: (
        <div className="wt-kv">
          <span>Name words</span>
          <Tokens items={x.name_tokens} />
          <span>House number</span>
          <Tokens items={x.house ? [x.house] : []} />
          <span>Street</span>
          <Tokens items={x.street} />
          <span>ZIP</span>
          <Tokens items={x.zip ? [x.zip] : []} />
        </div>
      ),
    },
    {
      id: "narrow",
      short: "Narrow the candidates",
      title: "Narrow the candidates",
      lead: "Instead of comparing against every NYU Langone record, keep only the ones that could plausibly be the place: same ZIP, or same house number and street.",
      rules: [
        "A record is a candidate if it shares the ZIP, or the house number and first street word.",
        "If the lookup gives no usable address, every record is a candidate and the name decides alone.",
        "Pharmacies and medical-equipment or prosthetics suppliers are left out: a records request never goes there, unless the name typed asks for one (\"pharmacy\", \"supply\").",
      ],
      body: (
        <>
          <div className="wt-bar">
            <span className="lbl">Records compared</span>
            <span className="bar">
              <div style={{ width: `${(100 * x.candidates_considered) / x.locations_total}%` }} />
            </span>
            <span className="v">{x.candidates_considered}</span>
          </div>
          <p>
            <strong>{x.candidates_considered}</strong> of {x.locations_total} registered NPIs compared, chosen by{" "}
            <strong>{x.blocked_by}</strong>.
            {x.pharmacies_skipped > 0 && (
              <>
                {" "}
                <strong>{x.pharmacies_skipped}</strong> pharmacy or supplier record{x.pharmacies_skipped === 1 ? " was" : "s were"} left out.
              </>
            )}
          </p>
        </>
      ),
    },
    {
      id: "score",
      short: "Score each one",
      title: "Score each candidate",
      lead: "Each candidate gets a score from 0 to 1 for how well the name matches and how well the address matches. The top rows are shown.",
      rules: [
        `Total = ${x.weights.name} × name + ${x.weights.address} × address (name alone when no address was typed).`,
        `Name = ${Math.round((1 - x.weights.reverse_share_of_name) * 100) / 100} × (share of typed words found in the record's names or specialty) + ${x.weights.reverse_share_of_name} × (share of the record's own name that was typed).`,
        "Address = house number 0.4 + street 0.4 + ZIP 0.2 (rescaled when the house number is missing). A word at least 75% similar still counts, so small typos are tolerated.",
      ],
      body: (
        <div className="wt-scroll">
          <table>
            <thead>
              <tr>
                <th>Record</th>
                <th className="num">Typed words found</th>
                <th className="num">Its name typed</th>
                <th className="num">Address</th>
                <th className="num">Total</th>
              </tr>
            </thead>
            <tbody>
              {x.candidates.map((c, k) => (
                <tr key={c.npi} className={k === 0 ? "top" : c.same_as_top ? "twin" : ""}>
                  <td>
                    <strong>{c.name}</strong>
                    <div className="muted small">
                      {c.address} · {c.taxonomy || "no specialty listed"}
                      {c.same_as_top && " · same name and address as the top record"}
                    </div>
                  </td>
                  <td className="num">{pct(c.name_forward)}</td>
                  <td className="num">{pct(c.name_reverse)}</td>
                  <td className="num">{c.address_score === null ? "—" : pct(c.address_score)}</td>
                  <td className="num">
                    <strong>{c.total.toFixed(3)}</strong>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ),
    },
    {
      id: "decide",
      short: "Answer or abstain",
      title: "Answer, or say it can't tell",
      lead: "A wrong answer sends the request to the wrong office and costs days, so the matcher only answers when the winner is both good enough and clearly ahead.",
      rules: [
        `Answer only if the top score is at least ${x.min_score}…`,
        `…and at least ${x.min_margin} ahead of the next different record.`,
        "Records the registry itself cannot tell apart (same name, same street address) are returned together instead of picking one at random.",
      ],
      status: x.answered ? "ok" : "stop",
      body: (
        <>
          <div className="wt-kv">
            <span>Top score</span>
            <span>
              <strong>{x.top_score}</strong> {x.top_score >= x.min_score ? "≥" : "<"} {x.min_score}
            </span>
            <span>Next different record</span>
            <span>{x.next_different_score}</span>
            <span>Lead</span>
            <span>
              <strong>{x.margin}</strong> {x.margin >= x.min_margin ? "≥" : "<"} {x.min_margin}
            </span>
          </div>
          <Verdict ok={x.answered}>
            {x.answered ? (
              <>
                Answer: <strong>{top?.name}</strong>, {top?.address}.
              </>
            ) : (
              <>No confident match: {REASON[x.reason ?? ""] ?? x.reason}.</>
            )}
          </Verdict>
        </>
      ),
    },
    {
      id: "baseline",
      short: "Compare: name only",
      title: "Compare with matching on the name alone",
      lead: "The baseline is roughly what a search box over the registry gives you: the record whose name is closest to what was typed.",
      rules: ["It ignores the address.", "It never says it can't tell."],
      body: (
        <div className="wt-kv">
          <span>Name only picks</span>
          <strong>{x.baseline_name ?? "—"}</strong>
          <span>The matcher</span>
          <strong>{x.answered ? top?.name : "no confident match"}</strong>
        </div>
      ),
    },
  ];

  return (
    <div className="mw">
      <Walkthrough
        title="How did it decide?"
        subtitle={
          <>
            Step by step, with this lookup's real numbers ·{" "}
            <button className="linkish" onClick={onClose}>
              close
            </button>
          </>
        }
        steps={steps}
      />
    </div>
  );
}

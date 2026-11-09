import { useEffect, useState } from "react";
import MatchApp from "./match/MatchApp";
import Overview from "./Overview";
import RecordsApp from "./records/RecordsApp";

type Section = "overview" | "match" | "records";

const SECTIONS: { id: Section; step: string; label: string; note: string }[] = [
  { id: "overview", step: "", label: "Overview", note: "What this is, how the two steps fit together, and the measured results." },
  {
    id: "match",
    step: "1",
    label: "Find the provider",
    note: "Where should the records request go? A messy provider name and address, matched to the right NYU Langone location in the public NPI Registry.",
  },
  {
    id: "records",
    step: "2",
    label: "Process the records",
    note: "What came back? Duplicate pages removed, then a dated timeline where every entry is checked against the page it cites.",
  },
];

// "#records/tour" -> section "records", tour open
function fromHash(): { section: Section; tour: boolean } {
  const [s, extra] = window.location.hash.replace(/^#/, "").split("/");
  const section = (["overview", "match", "records"] as const).find((x) => x === s) ?? "overview";
  return { section, tour: extra === "tour" };
}

export default function App() {
  const [route, setRoute] = useState(fromHash);
  useEffect(() => {
    const on = () => {
      setRoute(fromHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const current = SECTIONS.find((s) => s.id === route.section)!;

  return (
    <>
      <div className="shell-bar">
        <div className="shell-inner">
          <a className="shell-name" href="#overview">
            records-retrieval
          </a>
          <nav className="shell-tabs">
            {SECTIONS.map((s) => (
              <a key={s.id} href={`#${s.id}`} className={s.id === route.section ? "on" : ""}>
                {s.step && <span className="step">{s.step}</span>}
                {s.label}
              </a>
            ))}
          </nav>
          <span className="shell-note">{current.note}</span>
        </div>
      </div>
      {route.section === "overview" && <Overview />}
      {route.section === "match" && (
        <div className="match-app">
          <MatchApp tour={route.tour} />
        </div>
      )}
      {route.section === "records" && (
        <div className="records-app">
          <RecordsApp tour={route.tour} />
        </div>
      )}
    </>
  );
}

import { useEffect, useState, type ReactNode } from "react";

// A step-by-step view of one run, modelled on GnoRA's admin reasoning walkthrough:
// numbered steps on the left; for the open step, what it does, the rules it
// follows, and the real intermediate data from this run.

export interface Step {
  id: string;
  short: string;        // label in the step list
  title: string;        // heading of the open step
  lead: string;         // one sentence: what this step does
  rules: string[];      // the rules this step follows
  body: ReactNode;      // the data from this run
  status?: "ok" | "stop" | "info";
}

export default function Walkthrough({ title, subtitle, steps, start = 0 }: { title: string; subtitle?: ReactNode; steps: Step[]; start?: number }) {
  const [i, setI] = useState(start);
  const [rules, setRules] = useState(true);
  useEffect(() => setI(Math.min(start, steps.length - 1)), [steps.length, start]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
      if (e.key === "ArrowRight") setI((x) => Math.min(steps.length - 1, x + 1));
      if (e.key === "ArrowLeft") setI((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [steps.length]);
  const step = steps[i];
  if (!step) return null;

  return (
    <section className="wt" aria-label={title}>
      <div className="wt-top">
        <div>
          <div className="wt-title">{title}</div>
          {subtitle && <div className="wt-sub">{subtitle}</div>}
        </div>
        <div className="wt-nav">
          <button onClick={() => setI(Math.max(0, i - 1))} disabled={i === 0} aria-label="Previous step">
            ‹ Back
          </button>
          <span className="wt-count">
            {i + 1} / {steps.length}
          </span>
          <button className="primary" onClick={() => setI(Math.min(steps.length - 1, i + 1))} disabled={i === steps.length - 1} aria-label="Next step">
            Next ›
          </button>
        </div>
      </div>
      <div className="wt-body">
        <nav className="wt-steps" aria-label="Steps">
          {steps.map((s, k) => (
            <button key={s.id} className={k === i ? "on" : ""} aria-current={k === i ? "step" : undefined} onClick={() => setI(k)}>
              <span className={`wt-dot ${s.status ?? "info"} ${k < i ? "done" : ""}`} aria-hidden />
              <span className="wt-n">{k + 1}</span>
              <span>{s.short}</span>
            </button>
          ))}
          <div className="wt-hint">← → keys move between steps</div>
        </nav>
        <div className="wt-main">
          <h2>
            Step {i + 1}. {step.title}
          </h2>
          <p className="wt-lead">{step.lead}</p>
          {step.rules.length > 0 && (
            <div className="wt-rules">
              <button className="wt-rules-head" onClick={() => setRules(!rules)} aria-expanded={rules}>
                Rules this step follows {rules ? "▾" : "▸"}
              </button>
              {rules && (
                <ol>
                  {step.rules.map((r) => (
                    <li key={r}>{r}</li>
                  ))}
                </ol>
              )}
            </div>
          )}
          <div className="wt-data">{step.body}</div>
        </div>
      </div>
    </section>
  );
}

export function Tokens({ items, tone }: { items: string[]; tone?: "add" | "del" | "plain" }) {
  if (!items.length) return <span className="muted">none</span>;
  return (
    <span className="tokens">
      {items.map((t, k) => (
        <span key={`${t}-${k}`} className={`tok ${tone ?? "plain"}`}>
          {t}
        </span>
      ))}
    </span>
  );
}

export function Verdict({ ok, children }: { ok: boolean; children: ReactNode }) {
  return <div className={`wt-verdict ${ok ? "ok" : "stop"}`}>{children}</div>;
}

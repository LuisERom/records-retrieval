import { useEffect, useState } from "react";
import { getHighlight, pageUrl, type Box, type DedupView, type PageInfo } from "./api";

// Shared by the records views: labels, types and the page viewer.

export const KIND_LABEL: Record<string, string> = {
  er_visit: "ER visit",
  office_visit: "Office visit",
  imaging: "Imaging",
  lab: "Lab",
  therapy_evaluation: "Therapy evaluation",
  therapy_visit: "Therapy visit",
  procedure: "Procedure",
  surgery: "Surgery",
};

export function mechanismLabel(m: string): string {
  const base: Record<string, string> = {
    original: "as sent",
    fax: "fax copy",
    rescan: "rescan",
    received: "copy kept by another office (received stamp)",
  };
  if (m.startsWith("crop+")) return `cropped ${base[m.slice(5)] ?? m.slice(5)}`;
  return base[m] ?? m;
}

export type Sel = { split: string; case: string };
export type Cite = { page: number; quote: string | null };

export function PageViewer({
  sel,
  dedup,
  page,
  quote,
  onGoto,
  compact,
  zoom: sharedZoom,
  onZoom,
}: {
  sel: Sel;
  dedup: DedupView;
  page: number;
  quote: string | null;
  onGoto: (p: number) => void;
  compact?: boolean;
  zoom?: number; // when given, the zoom is shared with another viewer (Duplicates compares two pages)
  onZoom?: (z: number) => void;
}) {
  const [boxes, setBoxes] = useState<Box[]>([]);
  const [ownZoom, setOwnZoom] = useState(1);
  const zoom = sharedZoom ?? ownZoom;
  const setZoom = (f: (z: number) => number) => (onZoom ? onZoom(f(zoom)) : setOwnZoom(f));
  const info: PageInfo | undefined = dedup.pages[page - 1];
  useEffect(() => {
    setBoxes([]);
    if (!quote) return;
    let live = true;
    getHighlight(sel.split, sel.case, page, quote)
      .then((b) => live && setBoxes(b))
      .catch(() => live && setBoxes([]));
    return () => {
      live = false;
    };
  }, [sel, page, quote]);

  return (
    <div className="viewer card">
      <div className="viewer-head">
        <div>
          <strong>Page {page}</strong> <span className="muted">of {dedup.total}</span>{" "}
          {info && (
            <span className={`badge ${info.kept ? "kept" : "removed"}`}>
              {info.kept ? "kept" : `removed: copy of p. ${info.copy_of}`}
            </span>
          )}
        </div>
        {!compact && (
          <div className="nav">
            <button onClick={() => onGoto(Math.max(1, page - 1))} disabled={page <= 1}>
              ‹
            </button>
            <button onClick={() => onGoto(Math.min(dedup.total, page + 1))} disabled={page >= dedup.total}>
              ›
            </button>
          </div>
        )}
      </div>
      {info && (
        <div className="muted small">
          How this copy was made (answer key): {mechanismLabel(info.mechanism)} · {info.doc_kind}
          {!info.correct && <span className="wrong"> · this decision disagrees with the answer key</span>}
        </div>
      )}
      {quote && (
        <div className={`quote ${boxes.length ? "" : "missing"}`}>
          “{quote}” {boxes.length ? "" : "(not located on this page image)"}
        </div>
      )}
      <div className="zoombar">
        <button onClick={() => setZoom((z) => Math.max(1, z - 0.5))} disabled={zoom <= 1} aria-label="Zoom out">
          −
        </button>
        <span>{Math.round(zoom * 100)}%</span>
        <button onClick={() => setZoom((z) => Math.min(3, z + 0.5))} disabled={zoom >= 3} aria-label="Zoom in">
          +
        </button>
        <a href={pageUrl(sel.split, sel.case, page)} target="_blank" rel="noreferrer">
          Open full size
        </a>
        <span className="muted small">or click the page</span>
      </div>
      <div className={`sheet-scroll ${zoom > 1 ? "zoomed" : ""}`}>
        <div className="sheet" style={{ width: `${zoom * 100}%` }} onClick={() => setZoom((z) => (z > 1 ? 1 : 2))}>
          <img src={pageUrl(sel.split, sel.case, page)} alt={`Page ${page}`} />
          {boxes.map((b, i) => (
            <div
              key={i}
              className="hl"
              style={{ left: `${b.x * 100}%`, top: `${b.y * 100}%`, width: `${b.w * 100}%`, height: `${b.h * 100}%` }}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

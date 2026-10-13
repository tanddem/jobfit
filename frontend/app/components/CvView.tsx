import type { Gap, Highlight, Tone } from "../lib/api";

const MARK: Record<Tone, string> = {
  strong: "bg-strong/20 decoration-strong",
  partial: "bg-partial/25 decoration-partial",
  weak: "bg-weak/20 decoration-weak",
};

type Piece = { text: string; highlight?: Highlight };

/** Split text into plain and highlighted pieces; highlights never overlap and are sorted. */
function pieces(text: string, highlights: Highlight[]): Piece[] {
  const out: Piece[] = [];
  let cursor = 0;
  for (const h of highlights) {
    if (h.start > cursor) out.push({ text: text.slice(cursor, h.start) });
    out.push({ text: text.slice(h.start, h.end), highlight: h });
    cursor = h.end;
  }
  if (cursor < text.length) out.push({ text: text.slice(cursor) });
  return out;
}

function GapNote({ gap }: { gap: Gap }) {
  const missing = gap.evidence === null;
  const colour = gap.severity === "high" ? "text-weak" : "text-partial";
  return (
    <li>
      <span className={`font-semibold ${colour}`}>{missing ? "Missing" : "Weak"}:</span> {gap.requirement}
      {!missing && <span className="text-muted"> ({JSON.stringify(gap.evidence)})</span>}
    </li>
  );
}

/**
 * The user's own CV with gaps marked on it: matched keywords in green, weak
 * passages in amber or red. Gaps that cannot be marked inline sit in a strip
 * across the top: requirements the CV never mentions, and weak passages whose
 * text could not be located on the CV.
 */
export default function CvView({ text, highlights, gaps }: { text: string; highlights: Highlight[]; gaps: Gap[] }) {
  const unmarked = gaps.filter((g) => g.span === null);
  return (
    <div className="rounded border border-muted">
      {unmarked.length > 0 && (
        <ul className="space-y-1 border-b border-muted p-3 text-sm">
          {unmarked.map((g, i) => (
            <GapNote key={i} gap={g} />
          ))}
        </ul>
      )}
      <pre className="max-h-[36rem] overflow-auto whitespace-pre-wrap p-4 font-sans text-sm leading-relaxed">
        {pieces(text, highlights).map((p, i) =>
          p.highlight ? (
            <mark
              key={i}
              title={p.highlight.note}
              className={`rounded px-0.5 text-ink underline decoration-2 underline-offset-2 ${MARK[p.highlight.tone]}`}
            >
              {p.text}
            </mark>
          ) : (
            <span key={i}>{p.text}</span>
          ),
        )}
      </pre>
    </div>
  );
}

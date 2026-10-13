import type { Upload } from "../lib/api";
import CategoryBar from "./CategoryBar";
import CvView from "./CvView";
import ScoreRing from "./ScoreRing";

function Pills({ terms, className }: { terms: string[]; className: string }) {
  return (
    <div className="flex flex-wrap gap-1">
      {terms.map((term) => (
        <span key={term} className={`rounded-full px-2 py-0.5 text-xs ${className}`}>
          {term}
        </span>
      ))}
    </div>
  );
}

/** The scoring result: overall ring, category bars, keyword sets, and the marked-up CV. */
export default function ScorePanel({ upload }: { upload: Upload }) {
  const { score } = upload;
  return (
    <section className="grid gap-8 md:grid-cols-[18rem_1fr]">
      <div className="space-y-6">
        <div className="flex flex-col items-center gap-1">
          <ScoreRing score={score.overall} />
          <span className="text-sm capitalize text-muted">{score.band} match</span>
        </div>
        <div className="space-y-4">
          {score.categories.map((c) => (
            <CategoryBar key={c.id} category={c} />
          ))}
        </div>
        {score.matched_keywords.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-sm font-medium">Matched keywords</h3>
            <Pills terms={score.matched_keywords} className="bg-strong/15 text-strong" />
          </div>
        )}
        {score.missing_keywords.length > 0 && (
          <div className="space-y-1">
            <h3 className="text-sm font-medium">Missing keywords</h3>
            <Pills terms={score.missing_keywords} className="bg-weak/10 text-weak" />
          </div>
        )}
      </div>
      <div className="space-y-2">
        <h2 className="text-lg font-semibold">{upload.filename}</h2>
        <CvView text={upload.cv_text} highlights={score.highlights} gaps={score.gaps} />
      </div>
    </section>
  );
}

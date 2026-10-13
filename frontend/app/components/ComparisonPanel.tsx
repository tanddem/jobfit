import { formatDate } from "../lib/applications";
import type { UploadDetail } from "../lib/api";
import CategoryBar from "./CategoryBar";
import ScoreRing from "./ScoreRing";

function Delta({ before, after }: { before: number; after: number }) {
  const change = after - before;
  if (change === 0) return <span className="text-muted">no change</span>;
  return <span className={change > 0 ? "text-strong" : "text-weak"}>{change > 0 ? `+${change}` : change}</span>;
}

/** Two versions of a CV for the same role, side by side, with the change in each score. */
export default function ComparisonPanel({ older, newer }: { older: UploadDetail; newer: UploadDetail }) {
  return (
    <div className="grid gap-6 md:grid-cols-2">
      {[older, newer].map((version) => (
        <div key={version.upload_id} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <div>
            <h3 className="font-semibold">{version.filename}</h3>
            <p className="text-xs text-muted">{formatDate(version.created_at)}</p>
          </div>
          <div className="flex items-center gap-4">
            <ScoreRing score={version.score.overall} />
            {version === newer && (
              <p className="text-sm">
                Overall <Delta before={older.score.overall} after={newer.score.overall} />
              </p>
            )}
          </div>
          <div className="space-y-4">
            {version.score.categories.map((category, i) => (
              <div key={category.id}>
                <CategoryBar category={category} />
                {version === newer && (
                  <p className="text-xs">
                    <Delta before={older.score.categories[i].score} after={category.score} />
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

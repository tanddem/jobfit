import { toneFor, type CategoryScore } from "../lib/api";

/** One rubric category: name, weight, a horizontal bar for the score, and why. */
export default function CategoryBar({ category }: { category: CategoryScore }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-sm">
        <span className="font-medium">
          {category.name} <span className="text-muted">({category.weight}%)</span>
        </span>
        <span className="font-semibold">{category.score}</span>
      </div>
      <div className="h-2 rounded bg-track">
        <div
          className="h-2 rounded"
          style={{ width: `${category.score}%`, background: `var(--${toneFor(category.score)})` }}
        />
      </div>
      <p className="text-xs text-muted">{category.rationale}</p>
    </div>
  );
}

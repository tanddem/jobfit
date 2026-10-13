import { toneFor } from "../lib/api";

const RADIUS = 52;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

/** The overall score as a ring filled to the score, coloured by its tone. */
export default function ScoreRing({ score }: { score: number }) {
  const colour = `var(--${toneFor(score)})`;
  return (
    <svg viewBox="0 0 120 120" className="h-36 w-36" role="img" aria-label={`Overall score ${score} out of 100`}>
      <circle cx="60" cy="60" r={RADIUS} fill="none" stroke="var(--track)" strokeWidth="10" />
      <circle
        cx="60"
        cy="60"
        r={RADIUS}
        fill="none"
        stroke={colour}
        strokeWidth="10"
        strokeLinecap="round"
        strokeDasharray={CIRCUMFERENCE}
        strokeDashoffset={CIRCUMFERENCE * (1 - score / 100)}
        transform="rotate(-90 60 60)"
      />
      <text x="60" y="68" textAnchor="middle" fontSize="28" fontWeight="600" fill={colour}>
        {score}
      </text>
    </svg>
  );
}

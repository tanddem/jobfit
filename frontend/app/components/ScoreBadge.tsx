import { toneFor, type Tone } from "../lib/api";

const BADGE: Record<Tone, string> = {
  strong: "bg-strong/15 text-strong",
  partial: "bg-partial/20 text-ink",
  weak: "bg-weak/15 text-weak",
};

/** A compact score pill coloured by its tone. */
export default function ScoreBadge({ score }: { score: number }) {
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-sm font-semibold ${BADGE[toneFor(score)]}`}>{score}</span>;
}

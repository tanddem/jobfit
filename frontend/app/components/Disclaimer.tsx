export const DISCLAIMER =
  "JobFit only helps you rephrase experience you really have. It never invents experience, and it does not guarantee interviews, offers or any hiring outcome.";

/** The product disclaimer, as a footer line or as a callout. */
export default function Disclaimer({ variant = "footer" }: { variant?: "footer" | "callout" }) {
  if (variant === "callout") {
    return <p className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-3 text-sm text-ink">{DISCLAIMER}</p>;
  }
  return <p className="text-xs text-muted">{DISCLAIMER}</p>;
}

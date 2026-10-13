import Link from "next/link";

/** The JobFit wordmark, linking home. */
export default function Logo({ href = "/" }: { href?: string }) {
  return (
    <Link href={href} className="text-xl font-bold tracking-tight text-ink">
      Job<span className="text-primary">Fit</span>
    </Link>
  );
}

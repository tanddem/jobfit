import Link from "next/link";
import Disclaimer from "./components/Disclaimer";
import Logo from "./components/Logo";

const STEPS = [
  {
    title: "Score in seconds",
    body: "Upload your CV and paste the job description. You get a weighted score and a breakdown by category straight away, with no questions first.",
  },
  {
    title: "See the gaps on your own CV",
    body: "Matched keywords, weak bullets and missing requirements are marked directly on the document you uploaded.",
  },
  {
    title: "Track every application",
    body: "Each score is saved under the company and role, so you can compare CV versions and see what moved the number.",
  },
];

export default function LandingPage() {
  return (
    <div className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-4">
        <Logo />
        <nav className="flex items-center gap-4 text-sm">
          <Link href="/login/" className="text-ink hover:text-primary">
            Sign in
          </Link>
          <Link href="/register/" className="rounded-md bg-primary px-4 py-2 font-medium text-white">
            Get started
          </Link>
        </nav>
      </header>

      <main className="flex-1">
        <section className="mx-auto max-w-3xl px-6 py-20 text-center">
          <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">Close the gap between your CV and the job you want</h1>
          <p className="mt-6 text-lg text-muted">
            JobFit reads your CV against a job description, scores the match, and shows exactly where it falls short.
          </p>
          <div className="mt-8 flex justify-center gap-3">
            <Link href="/register/" className="rounded-md bg-primary px-6 py-3 font-medium text-white">
              Create a free account
            </Link>
            <Link href="/login/" className="rounded-md border border-slate-300 px-6 py-3 font-medium text-ink hover:bg-slate-50">
              Sign in
            </Link>
          </div>
        </section>

        <section className="border-y border-slate-200 bg-slate-50">
          <div className="mx-auto grid max-w-6xl gap-6 px-6 py-16 md:grid-cols-3">
            {STEPS.map((step) => (
              <div key={step.title} className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
                <h2 className="font-semibold">{step.title}</h2>
                <p className="mt-2 text-sm text-muted">{step.body}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="mx-auto max-w-3xl px-6 py-12">
          <Disclaimer variant="callout" />
        </section>
      </main>

      <footer className="border-t border-slate-200">
        <div className="mx-auto max-w-6xl px-6 py-4">
          <Disclaimer />
        </div>
      </footer>
    </div>
  );
}

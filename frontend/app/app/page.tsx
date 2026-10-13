"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { uploadCv, type Upload } from "../lib/api";
import { clearSession, useSession } from "../lib/session";

export default function AppPage() {
  const router = useRouter();
  const session = useSession();
  const [cv, setCv] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [upload, setUpload] = useState<Upload | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (session === null) router.replace("/");
  }, [session, router]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session || !cv) return;
    setBusy(true);
    setError("");
    try {
      setUpload(await uploadCv(session.userId, cv, jdText));
    } catch (err) {
      const message = (err as Error).message;
      // The database resets on every boot, so a stored session can outlive its user.
      if (message === "Unknown user.") clearSession();
      else setError(message);
    } finally {
      setBusy(false);
    }
  }

  if (!session) return null;

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 space-y-6 p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">JobFit</h1>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-muted">Signed in as {session.name}</span>
          <button onClick={clearSession} className="text-primary hover:underline">
            Sign out
          </button>
        </div>
      </header>

      <form onSubmit={handleSubmit} className="grid gap-6 md:grid-cols-2">
        <label className="block">
          <span className="text-sm font-medium">Your CV (PDF, up to 5 MB)</span>
          <input
            type="file"
            accept="application/pdf,.pdf"
            required
            onChange={(e) => setCv(e.target.files?.[0] ?? null)}
            className="mt-1 block w-full text-sm"
          />
        </label>
        <label className="block md:row-span-2">
          <span className="text-sm font-medium">Job description</span>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            required
            rows={12}
            placeholder="Paste the job description here"
            className="mt-1 w-full rounded border border-muted px-3 py-2"
          />
        </label>
        <div className="space-y-2">
          {error && <p className="text-sm text-weak">{error}</p>}
          <button
            type="submit"
            disabled={busy || !cv || !jdText.trim()}
            className="rounded bg-primary px-4 py-2 font-medium text-white disabled:opacity-50"
          >
            {busy ? "Reading your CV..." : "Upload"}
          </button>
        </div>
      </form>

      {upload && (
        <section className="space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Text we read from {upload.filename}</h2>
            <button
              disabled
              title="Scoring arrives in the next release"
              className="rounded bg-primary px-4 py-2 font-medium text-white opacity-50"
            >
              Score (coming next)
            </button>
          </div>
          <p className="text-sm text-muted">Check that nothing important is missing before scoring.</p>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded border border-muted p-4 text-sm">
            {upload.cv_text}
          </pre>
        </section>
      )}
    </main>
  );
}

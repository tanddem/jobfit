"use client";

import Link from "next/link";
import { useState } from "react";
import { useSignedOutRedirect } from "../../components/AppShell";
import Disclaimer from "../../components/Disclaimer";
import ScorePanel from "../../components/ScorePanel";
import { SignedOutError, uploadCv, type UploadDetail } from "../../lib/api";
import { applicationHref } from "../../lib/applications";
import { INPUT } from "../../lib/styles";

export default function NewScorePage() {
  const onSignedOut = useSignedOutRedirect();
  const [company, setCompany] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [cv, setCv] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [upload, setUpload] = useState<UploadDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ready = company.trim() && roleTitle.trim() && cv && jdText.trim();

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cv) return;
    setBusy(true);
    setError("");
    try {
      setUpload(await uploadCv(company, roleTitle, cv, jdText));
    } catch (err) {
      if (err instanceof SignedOutError) onSignedOut(err);
      else setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold">Score a CV</h1>
        <p className="text-sm text-muted">We score immediately. Nothing to answer first.</p>
      </div>

      <form onSubmit={handleSubmit} className="grid gap-6 rounded-xl border border-slate-200 bg-white p-6 shadow-sm md:grid-cols-2">
        <div className="space-y-4">
          <label className="block text-sm font-medium">
            Company
            <input value={company} onChange={(e) => setCompany(e.target.value)} required maxLength={200} className={INPUT} />
          </label>
          <label className="block text-sm font-medium">
            Role title
            <input value={roleTitle} onChange={(e) => setRoleTitle(e.target.value)} required maxLength={200} className={INPUT} />
          </label>
          <label className="block text-sm font-medium">
            Your CV (PDF, up to 5 MB)
            <input
              type="file"
              accept="application/pdf,.pdf"
              required
              onChange={(e) => setCv(e.target.files?.[0] ?? null)}
              className="mt-1 block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-primary/10 file:px-3 file:py-2 file:text-primary"
            />
          </label>
          <Disclaimer variant="callout" />
        </div>
        <label className="block text-sm font-medium">
          Job description
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            required
            rows={14}
            placeholder="Paste the job description here"
            className={INPUT}
          />
        </label>
        <div className="flex items-center gap-4 md:col-span-2">
          <button type="submit" disabled={busy || !ready} className="rounded-md bg-primary px-5 py-2 font-medium text-white disabled:opacity-50">
            {busy ? "Scoring your CV..." : "Score"}
          </button>
          {error && <p className="text-sm text-weak">{error}</p>}
        </div>
      </form>

      {upload && (
        <div className="space-y-4">
          <Link href={applicationHref(upload.company, upload.role_title)} className="text-sm text-primary hover:underline">
            See all versions for {upload.company}, {upload.role_title}
          </Link>
          <ScorePanel upload={upload} />
        </div>
      )}
    </div>
  );
}

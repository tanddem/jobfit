"use client";

import Link from "next/link";
import { useState } from "react";
import { useSignedOutRedirect } from "../../components/AppShell";
import Disclaimer from "../../components/Disclaimer";
import ScorePanel from "../../components/ScorePanel";
import { fetchJd, SignedOutError, uploadCv, type UploadDetail } from "../../lib/api";
import { applicationHref } from "../../lib/applications";
import { INPUT } from "../../lib/styles";

export default function NewScorePage() {
  const onSignedOut = useSignedOutRedirect();
  const [company, setCompany] = useState("");
  const [roleTitle, setRoleTitle] = useState("");
  const [cv, setCv] = useState<File | null>(null);
  const [jdText, setJdText] = useState("");
  const [jdUrl, setJdUrl] = useState("");
  const [fetchedFrom, setFetchedFrom] = useState<string | null>(null);
  const [fetching, setFetching] = useState(false);
  const [fetchError, setFetchError] = useState("");
  const [upload, setUpload] = useState<UploadDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const ready = company.trim() && roleTitle.trim() && cv && jdText.trim();

  async function handleFetch() {
    setFetching(true);
    setFetchError("");
    setFetchedFrom(null);
    try {
      const fetched = await fetchJd(jdUrl.trim());
      setJdText(fetched.jd_text);
      setFetchedFrom(fetched.final_url);
    } catch (err) {
      if (err instanceof SignedOutError) onSignedOut(err);
      else setFetchError((err as Error).message);
    } finally {
      setFetching(false);
    }
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!cv) return;
    setBusy(true);
    setError("");
    try {
      setUpload(await uploadCv(company, roleTitle, cv, jdText, fetchedFrom));
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
        <div className="space-y-3">
          <div className="text-sm font-medium">
            Job posting link <span className="font-normal text-muted">(optional)</span>
            <div className="mt-1 flex gap-2">
              <input
                type="url"
                value={jdUrl}
                onChange={(e) => {
                  setJdUrl(e.target.value);
                  setFetchedFrom(null);
                }}
                placeholder="https://..."
                className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 focus:border-primary focus:outline-none"
              />
              <button
                type="button"
                onClick={handleFetch}
                disabled={fetching || !jdUrl.trim()}
                className="shrink-0 rounded-md border border-primary px-4 py-2 font-medium text-primary disabled:opacity-50"
              >
                {fetching ? "Fetching..." : "Fetch"}
              </button>
            </div>
            {fetchError && <p className="mt-1 font-normal text-weak">{fetchError}</p>}
            {fetchedFrom && (
              <p className="mt-1 font-normal text-muted">Fetched from {fetchedFrom}. Check the text below before scoring.</p>
            )}
          </div>
          <label className="block text-sm font-medium">
            Job description
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              required
              rows={14}
              placeholder="Paste the job description here, or fetch it from a link above"
              className={INPUT}
            />
          </label>
        </div>
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

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useAccount, useSignedOutRedirect } from "../components/AppShell";
import ScoreBadge from "../components/ScoreBadge";
import { listUploads } from "../lib/api";
import { applicationHref, formatDate, groupByApplication, type Application } from "../lib/applications";

export default function DashboardPage() {
  const account = useAccount();
  const onError = useSignedOutRedirect();
  const [applications, setApplications] = useState<Application[] | null>(null);

  useEffect(() => {
    listUploads()
      .then((uploads) => setApplications(groupByApplication(uploads)))
      .catch(onError);
  }, [onError]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Applications</h1>
          <p className="text-sm text-muted">Welcome back, {account.name}. Every score is saved under its company and role.</p>
        </div>
        <Link href="/app/new/" className="rounded-md bg-primary px-4 py-2 font-medium text-white">
          New score
        </Link>
      </div>

      {applications?.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-300 bg-white p-12 text-center">
          <h2 className="font-semibold">No applications yet</h2>
          <p className="mt-1 text-sm text-muted">Score your CV against a job description to start your history.</p>
          <Link href="/app/new/" className="mt-4 inline-block rounded-md bg-primary px-4 py-2 font-medium text-white">
            Score your first CV
          </Link>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        {applications?.map((app) => {
          const [latest, previous] = app.versions;
          return (
            <Link
              key={`${app.company}\n${app.roleTitle}`}
              href={applicationHref(app.company, app.roleTitle)}
              className="block rounded-xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-primary"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="font-semibold">{app.company}</h2>
                  <p className="text-sm text-muted">{app.roleTitle}</p>
                </div>
                <ScoreBadge score={latest.overall} />
              </div>
              <p className="mt-4 text-xs text-muted">
                {app.versions.length} {app.versions.length === 1 ? "version" : "versions"} - last scored {formatDate(latest.created_at)}
                {previous && ` - ${latest.overall - previous.overall >= 0 ? "+" : ""}${latest.overall - previous.overall} since previous`}
              </p>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

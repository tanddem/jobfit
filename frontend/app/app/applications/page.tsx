"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSignedOutRedirect } from "../../components/AppShell";
import ComparisonPanel from "../../components/ComparisonPanel";
import ScoreBadge from "../../components/ScoreBadge";
import ScorePanel from "../../components/ScorePanel";
import { deleteUpload, getUpload, listUploads, type UploadDetail, type UploadSummary } from "../../lib/api";
import { formatDate } from "../../lib/applications";

/** Versions of one application (company and role): list, compare two, view one, delete. */
function ApplicationInner() {
  const router = useRouter();
  const params = useSearchParams();
  const company = params.get("company") ?? "";
  const role = params.get("role") ?? "";
  const onError = useSignedOutRedirect();
  const [versions, setVersions] = useState<UploadSummary[] | null>(null);
  const [selected, setSelected] = useState<number[]>([]);
  const [details, setDetails] = useState<Record<number, UploadDetail>>({});
  const [viewing, setViewing] = useState<number | null>(null);
  const requested = useRef(new Set<number>());

  useEffect(() => {
    if (!company || !role) {
      router.replace("/app/");
      return;
    }
    let stale = false;
    listUploads({ company, role })
      .then((list) => {
        if (stale) return;
        setVersions(list);
        setSelected(list.slice(0, 2).map((v) => v.upload_id));
        setViewing(list[0]?.upload_id ?? null);
      })
      .catch(onError);
    return () => {
      stale = true;
    };
  }, [company, role, router, onError]);

  useEffect(() => {
    for (const id of [...selected, viewing]) {
      if (id === null || requested.current.has(id)) continue;
      requested.current.add(id);
      getUpload(id)
        .then((detail) => setDetails((current) => ({ ...current, [id]: detail })))
        .catch(onError);
    }
  }, [selected, viewing, onError]);

  function toggle(id: number) {
    setSelected((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : [...current, id].slice(-2),
    );
  }

  async function remove(id: number) {
    if (!confirm("Delete this version? This cannot be undone.")) return;
    await deleteUpload(id).catch(onError);
    const rest = (versions ?? []).filter((v) => v.upload_id !== id);
    setVersions(rest);
    setSelected((current) => current.filter((x) => x !== id));
    if (viewing === id) setViewing(rest[0]?.upload_id ?? null);
  }

  const compared = [...selected].sort((a, b) => a - b).map((id) => details[id]);
  const viewed = viewing !== null ? details[viewing] : undefined;

  return (
    <div className="space-y-8">
      <div>
        <Link href="/app/" className="text-sm text-primary hover:underline">
          All applications
        </Link>
        <h1 className="mt-1 text-2xl font-semibold">{company}</h1>
        <p className="text-sm text-muted">{role}</p>
      </div>

      {versions?.length === 0 && <p className="text-muted">No versions for this application yet.</p>}

      {versions && versions.length > 0 && (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-left text-xs uppercase text-muted">
              <tr>
                <th className="px-4 py-2">Compare</th>
                <th className="px-4 py-2">CV</th>
                <th className="px-4 py-2">Scored</th>
                <th className="px-4 py-2">Score</th>
                <th className="px-4 py-2" />
              </tr>
            </thead>
            <tbody>
              {versions.map((v) => (
                <tr key={v.upload_id} className={`border-t border-slate-100 ${viewing === v.upload_id ? "bg-primary/5" : ""}`}>
                  <td className="px-4 py-2">
                    <input type="checkbox" checked={selected.includes(v.upload_id)} onChange={() => toggle(v.upload_id)} aria-label="Compare this version" />
                  </td>
                  <td className="px-4 py-2">
                    <button onClick={() => setViewing(v.upload_id)} className="text-left text-primary hover:underline">
                      {v.filename}
                    </button>
                  </td>
                  <td className="px-4 py-2 text-muted">{formatDate(v.created_at)}</td>
                  <td className="px-4 py-2">
                    <ScoreBadge score={v.overall} />
                  </td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => remove(v.upload_id)} className="text-weak hover:underline">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selected.length === 2 && compared.every(Boolean) && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Comparison</h2>
          <ComparisonPanel older={compared[0]} newer={compared[1]} />
        </section>
      )}
      {versions && versions.length > 1 && selected.length < 2 && (
        <p className="text-sm text-muted">Tick two versions to compare them side by side.</p>
      )}

      {viewed && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Version detail</h2>
          <ScorePanel upload={viewed} />
        </section>
      )}
    </div>
  );
}

export default function ApplicationPage() {
  return (
    <Suspense>
      <ApplicationInner />
    </Suspense>
  );
}

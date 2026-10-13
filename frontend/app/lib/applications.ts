import type { UploadSummary } from "./api";

export type Application = {
  company: string;
  roleTitle: string;
  versions: UploadSummary[];
};

/** Group uploads (newest first) by company and role; each group's versions stay newest first. */
export function groupByApplication(uploads: UploadSummary[]): Application[] {
  const groups = new Map<string, Application>();
  for (const upload of uploads) {
    const key = JSON.stringify([upload.company, upload.role_title]);
    const group = groups.get(key) ?? { company: upload.company, roleTitle: upload.role_title, versions: [] };
    group.versions.push(upload);
    groups.set(key, group);
  }
  return [...groups.values()];
}

export function applicationHref(company: string, roleTitle: string) {
  return `/app/applications/?${new URLSearchParams({ company, role: roleTitle })}`;
}

export function formatDate(iso: string) {
  return new Date(iso.replace(" ", "T") + "Z").toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

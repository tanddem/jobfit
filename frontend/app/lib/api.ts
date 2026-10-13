/** Calls to the FastAPI backend. The session lives in an HTTP-only cookie the browser sends. */

export type Tone = "strong" | "partial" | "weak";

export type CategoryScore = {
  id: string;
  name: string;
  weight: number;
  score: number;
  rationale: string;
};

export type Gap = {
  category: string;
  severity: "high" | "medium" | "low";
  requirement: string;
  evidence: string | null;
  span: [number, number] | null;
};

export type Highlight = { start: number; end: number; tone: Tone; note: string };

export type ScoreResult = {
  overall: number;
  band: string;
  categories: CategoryScore[];
  matched_keywords: string[];
  missing_keywords: string[];
  gaps: Gap[];
  highlights: Highlight[];
  model: string;
};

export type Account = { id: number; email: string; name: string };

export type UploadSummary = {
  upload_id: number;
  company: string;
  role_title: string;
  filename: string;
  created_at: string;
  overall: number;
  band: string;
};

export type UploadDetail = UploadSummary & {
  cv_text: string;
  jd_text: string;
  jd_url: string | null;
  score: ScoreResult;
};

export type FetchedJd = { jd_text: string; final_url: string };

/** The colour token for a 0-100 score: strong >= 75, partial 50-74, weak < 50. */
export function toneFor(score: number): Tone {
  if (score >= 75) return "strong";
  if (score >= 50) return "partial";
  return "weak";
}

/** Thrown when the session is missing or expired. */
export class SignedOutError extends Error {}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (response.status === 401 && !path.startsWith("/api/auth/login")) throw new SignedOutError();
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    const detail = body?.detail;
    if (typeof detail === "string") throw new Error(detail);
    if (Array.isArray(detail) && typeof detail[0]?.msg === "string") throw new Error(detail[0].msg);
    throw new Error(`Request failed (${response.status}).`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

function json(body: unknown): RequestInit {
  return { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
}

export const register = (email: string, name: string, password: string) =>
  request<Account>("/api/auth/register", json({ email, name, password }));

export const login = (email: string, password: string) => request<Account>("/api/auth/login", json({ email, password }));

export const logout = () => request<void>("/api/auth/logout", { method: "POST" });

export const me = () => request<Account>("/api/auth/me");

export const fetchJd = (url: string) => request<FetchedJd>("/api/jd/fetch", json({ url }));

export function uploadCv(company: string, roleTitle: string, cv: File, jdText: string, jdUrl: string | null) {
  const form = new FormData();
  form.append("company", company);
  form.append("role_title", roleTitle);
  form.append("jd_text", jdText);
  if (jdUrl) form.append("jd_url", jdUrl);
  form.append("cv", cv);
  return request<UploadDetail>("/api/uploads", { method: "POST", body: form });
}

export function listUploads(filter?: { company: string; role: string }) {
  const query = filter ? `?${new URLSearchParams(filter)}` : "";
  return request<UploadSummary[]>(`/api/uploads${query}`);
}

export const getUpload = (id: number) => request<UploadDetail>(`/api/uploads/${id}`);

export const deleteUpload = (id: number) => request<void>(`/api/uploads/${id}`, { method: "DELETE" });

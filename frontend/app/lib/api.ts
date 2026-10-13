/** Calls to the FastAPI backend. */

import type { Session } from "./session";

export type Upload = {
  upload_id: number;
  filename: string;
  cv_text: string;
  jd_text: string;
};

async function errorMessage(response: Response): Promise<string> {
  const body = await response.json().catch(() => null);
  if (typeof body?.detail === "string") return body.detail;
  return `Request failed (${response.status}).`;
}

export async function createSession(name: string): Promise<Session> {
  const response = await fetch("/api/session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!response.ok) throw new Error(await errorMessage(response));
  const body = await response.json();
  return { userId: body.user_id, name: body.name };
}

export async function uploadCv(userId: number, cv: File, jdText: string): Promise<Upload> {
  const form = new FormData();
  form.append("user_id", String(userId));
  form.append("jd_text", jdText);
  form.append("cv", cv);
  const response = await fetch("/api/uploads", { method: "POST", body: form });
  if (!response.ok) throw new Error(await errorMessage(response));
  return response.json();
}

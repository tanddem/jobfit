"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createSession } from "./lib/api";
import { saveSession } from "./lib/session";

export default function LoginPage() {
  const router = useRouter();
  const [name, setName] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      saveSession(await createSession(name));
      router.push("/app/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center p-6">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4">
        <h1 className="text-3xl font-semibold">JobFit</h1>
        <p className="text-muted">Score your CV against the job you want.</p>
        <label className="block">
          <span className="text-sm font-medium">Your name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            maxLength={100}
            className="mt-1 w-full rounded border border-muted px-3 py-2"
          />
        </label>
        {error && <p className="text-sm text-weak">{error}</p>}
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="w-full rounded bg-primary px-4 py-2 font-medium text-white disabled:opacity-50"
        >
          {busy ? "Signing in..." : "Continue"}
        </button>
      </form>
    </main>
  );
}

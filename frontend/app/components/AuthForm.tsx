"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { login, register } from "../lib/api";
import { INPUT } from "../lib/styles";
import Disclaimer from "./Disclaimer";
import Logo from "./Logo";

/** The sign-in and create-account forms, which share one layout. */
export default function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const isRegister = mode === "register";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await (isRegister ? register(email, name, password) : login(email, password));
      router.replace("/app/");
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <main className="flex flex-1 items-center justify-center bg-slate-50 p-6">
      <div className="w-full max-w-sm space-y-6">
        <div className="text-center">
          <Logo />
        </div>
        <form onSubmit={handleSubmit} className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="text-xl font-semibold">{isRegister ? "Create your account" : "Sign in"}</h1>
          <label className="block text-sm font-medium">
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" className={INPUT} />
          </label>
          {isRegister && (
            <label className="block text-sm font-medium">
              Your name
              <input value={name} onChange={(e) => setName(e.target.value)} required maxLength={100} autoComplete="name" className={INPUT} />
            </label>
          )}
          <label className="block text-sm font-medium">
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={isRegister ? 8 : undefined}
              autoComplete={isRegister ? "new-password" : "current-password"}
              className={INPUT}
            />
            {isRegister && <span className="mt-1 block text-xs font-normal text-muted">At least 8 characters.</span>}
          </label>
          {error && <p className="text-sm text-weak">{error}</p>}
          <button type="submit" disabled={busy} className="w-full rounded-md bg-primary px-4 py-2 font-medium text-white disabled:opacity-50">
            {busy ? "Please wait..." : isRegister ? "Create account" : "Sign in"}
          </button>
          <p className="text-center text-sm text-muted">
            {isRegister ? "Already have an account? " : "New to JobFit? "}
            <Link href={isRegister ? "/login/" : "/register/"} className="text-primary hover:underline">
              {isRegister ? "Sign in" : "Create an account"}
            </Link>
          </p>
        </form>
        <Disclaimer />
      </div>
    </main>
  );
}

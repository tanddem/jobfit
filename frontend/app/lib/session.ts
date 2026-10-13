/** The fake-login session, kept in localStorage and readable as a React hook. */

import { useMemo, useSyncExternalStore } from "react";

export type Session = { userId: number; name: string };

const SESSION_KEY = "jobfit.session";
const listeners = new Set<() => void>();

function subscribe(listener: () => void) {
  listeners.add(listener);
  window.addEventListener("storage", listener);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", listener);
  };
}

function notify() {
  listeners.forEach((listener) => listener());
}

export function saveSession(session: Session) {
  localStorage.setItem(SESSION_KEY, JSON.stringify(session));
  notify();
}

export function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  notify();
}

/**
 * The stored session, null when signed out, or undefined while the page is
 * still hydrating and localStorage has not been read yet.
 */
export function useSession(): Session | null | undefined {
  const raw = useSyncExternalStore(
    subscribe,
    () => localStorage.getItem(SESSION_KEY),
    () => undefined,
  );
  return useMemo(() => (typeof raw === "string" ? (JSON.parse(raw) as Session) : raw), [raw]);
}

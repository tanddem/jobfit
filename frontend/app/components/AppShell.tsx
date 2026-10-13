"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { logout, me, SignedOutError, type Account } from "../lib/api";
import Disclaimer from "./Disclaimer";
import Logo from "./Logo";

const AccountContext = createContext<Account | null>(null);

/** The signed-in account; only valid inside AppShell. */
export function useAccount() {
  return useContext(AccountContext) as Account;
}

/** Send the browser to sign in; used whenever an API call reports the session is gone. */
export function useSignedOutRedirect() {
  const router = useRouter();
  return useCallback(
    (err: unknown) => {
      if (err instanceof SignedOutError) router.replace("/login/");
      else throw err;
    },
    [router],
  );
}

const NAV = [
  { href: "/app/", label: "Applications" },
  { href: "/app/new/", label: "New score" },
];

/** Topbar, auth guard and footer disclaimer for every signed-in page. */
export default function AppShell({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [account, setAccount] = useState<Account | null>(null);
  const [unreachable, setUnreachable] = useState(false);

  useEffect(() => {
    me()
      .then(setAccount)
      .catch((err) => (err instanceof SignedOutError ? router.replace("/login/") : setUnreachable(true)));
  }, [router]);

  async function signOut() {
    await logout();
    router.replace("/login/");
  }

  if (unreachable) {
    return <p className="m-auto p-6 text-muted">JobFit could not be reached. Refresh the page to try again.</p>;
  }
  if (!account) return null;

  return (
    <AccountContext.Provider value={account}>
      <div className="flex min-h-full flex-1 flex-col bg-slate-50">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-6 py-3">
            <div className="flex items-center gap-8">
              <Logo href="/app/" />
              <nav className="flex gap-1 text-sm">
                {NAV.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`rounded-md px-3 py-1.5 ${pathname === item.href || pathname + "/" === item.href ? "bg-primary/10 font-medium text-primary" : "text-ink hover:bg-slate-100"}`}
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <span className="text-muted">{account.name}</span>
              <button onClick={signOut} className="text-primary hover:underline">
                Sign out
              </button>
            </div>
          </div>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">{children}</main>
        <footer className="border-t border-slate-200 bg-white">
          <div className="mx-auto max-w-6xl px-6 py-4">
            <Disclaimer />
          </div>
        </footer>
      </div>
    </AccountContext.Provider>
  );
}

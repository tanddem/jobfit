import AppShell from "../components/AppShell";

export default function SignedInLayout({ children }: LayoutProps<"/app">) {
  return <AppShell>{children}</AppShell>;
}

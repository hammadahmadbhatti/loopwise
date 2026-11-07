"use client";

import {
  BarChart3,
  Gavel,
  Inbox,
  Layers,
  LogOut,
  Megaphone,
  MessageSquareText,
  Settings,
  Sparkles,
  Target,
  Users,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { cn, Spinner } from "./ui";

const NAV = [
  { section: "Understand", items: [
    { href: "/app", label: "Overview", icon: BarChart3 },
    { href: "/app/feedback", label: "Feedback", icon: Inbox },
    { href: "/app/themes", label: "Themes", icon: Layers },
    { href: "/app/ask", label: "Ask AI", icon: Sparkles },
    { href: "/app/customers", label: "Customers", icon: Users },
  ] },
  { section: "Decide", items: [
    { href: "/app/opportunities", label: "Opportunities", icon: Target },
    { href: "/app/decisions", label: "Decision log", icon: Gavel },
  ] },
  { section: "Close the loop", items: [
    { href: "/app/loop", label: "Changelog & outbox", icon: Megaphone },
  ] },
];

export function Logo({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-brand-500 to-violet-600 text-white shadow-sm">
        <MessageSquareText className="h-4 w-4" />
      </div>
      <span className="text-[15px] font-semibold tracking-tight">Loopwise</span>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const { user, loading, workspace, logout, selectWorkspace } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user || !workspace) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-6 w-6" />
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="px-4 pb-3 pt-4">
          <Logo />
        </div>
        <div className="px-3 pb-2">
          {user.workspaces.length > 1 ? (
            <select
              value={workspace.id}
              onChange={(e) => selectWorkspace(Number(e.target.value))}
              className="w-full rounded-lg border border-slate-200 bg-slate-50 px-2 py-1.5 text-xs font-medium text-slate-700"
              aria-label="Workspace"
            >
              {user.workspaces.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}
            </select>
          ) : (
            <div className="truncate rounded-lg bg-slate-50 px-2.5 py-1.5 text-xs font-medium text-slate-700">{workspace.name}</div>
          )}
        </div>
        <nav className="scroll-thin flex-1 space-y-4 overflow-y-auto px-3 py-2">
          {NAV.map((group) => (
            <div key={group.section}>
              <div className="px-2 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">{group.section}</div>
              {group.items.map(({ href, label, icon: Icon }) => {
                const active = href === "/app" ? pathname === "/app" : pathname.startsWith(href);
                return (
                  <Link
                    key={href}
                    href={href}
                    className={cn(
                      "flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm transition",
                      active ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                    )}
                  >
                    <Icon className="h-4 w-4" />
                    {label}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="border-t border-slate-100 p-3">
          <Link href="/app/settings" className={cn("flex items-center gap-2.5 rounded-lg px-2 py-1.5 text-sm", pathname.startsWith("/app/settings") ? "bg-brand-50 font-medium text-brand-700" : "text-slate-600 hover:bg-slate-50")}>
            <Settings className="h-4 w-4" /> Settings
          </Link>
          <div className="mt-2 flex items-center justify-between gap-2 px-2">
            <div className="min-w-0">
              <div className="truncate text-xs font-medium text-slate-700">{user.name || user.email}</div>
              <div className="truncate text-[11px] text-slate-400">{user.email}</div>
            </div>
            <button onClick={logout} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="Sign out" aria-label="Sign out">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* mobile top bar */}
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 md:hidden">
          <Logo />
          <select
            value={pathname}
            onChange={(e) => router.push(e.target.value)}
            className="rounded-lg border border-slate-200 px-2 py-1 text-sm"
            aria-label="Navigate"
          >
            {NAV.flatMap((g) => g.items).concat([{ href: "/app/settings", label: "Settings", icon: Settings }]).map((i) => (
              <option key={i.href} value={i.href}>{i.label}</option>
            ))}
          </select>
        </div>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}

import Link from "next/link";
import { Logo } from "@/components/AppShell";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-gradient-to-b from-white to-slate-100 px-4 py-12">
      <Link href="/" className="mb-8"><Logo /></Link>
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">{children}</div>
    </div>
  );
}

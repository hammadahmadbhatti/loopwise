"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button, ErrorNote, Input, Label } from "@/components/ui";
import { useAuth } from "@/lib/auth";

export default function RegisterPage() {
  const { register } = useAuth();
  const router = useRouter();
  const [form, setForm] = useState({ name: "", email: "", password: "", workspace_name: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await register(form);
      router.push("/app/settings?welcome=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign up failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <h1 className="text-lg font-semibold">Create your workspace</h1>
        <p className="text-sm text-slate-500">One workspace per product or company.</p>
      </div>
      <ErrorNote error={error} />
      <label className="block"><Label>Your name</Label><Input required value={form.name} onChange={set("name")} autoComplete="name" /></label>
      <label className="block"><Label>Work email</Label><Input type="email" required value={form.email} onChange={set("email")} autoComplete="email" /></label>
      <label className="block"><Label hint="(min. 8 characters)">Password</Label><Input type="password" required minLength={8} value={form.password} onChange={set("password")} autoComplete="new-password" /></label>
      <label className="block"><Label>Company or product name</Label><Input required minLength={2} value={form.workspace_name} onChange={set("workspace_name")} /></label>
      <Button variant="primary" className="w-full" loading={busy} type="submit">Create workspace</Button>
      <p className="text-center text-sm text-slate-500">
        Already have an account? <Link href="/login" className="font-medium text-brand-600 hover:underline">Sign in</Link>
      </p>
    </form>
  );
}

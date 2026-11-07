"use client";

import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, session } from "./api";
import type { User, WorkspaceRef } from "./types";

interface AuthState {
  user: User | null;
  loading: boolean;
  workspace: WorkspaceRef | null;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; password: string; name: string; workspace_name: string }) => Promise<void>;
  logout: () => void;
  selectWorkspace: (id: number) => void;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [wsId, setWsId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();

  const adopt = useCallback((u: User) => {
    setUser(u);
    const stored = session.workspaceId();
    const chosen = u.workspaces.find((w) => w.id === stored) ?? u.workspaces[0] ?? null;
    session.setWorkspaceId(chosen?.id ?? null);
    setWsId(chosen?.id ?? null);
  }, []);

  const refresh = useCallback(async () => {
    if (!session.token()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      adopt(await api<User>("/api/auth/me"));
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, [adopt]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial session restore from storage
    void refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api<{ access_token: string; user: User }>("/api/auth/login", { body: { email, password }, auth: false });
    session.setToken(r.access_token);
    adopt(r.user);
  }, [adopt]);

  const register = useCallback(async (data: { email: string; password: string; name: string; workspace_name: string }) => {
    const r = await api<{ access_token: string; user: User }>("/api/auth/register", { body: data, auth: false });
    session.setToken(r.access_token);
    session.setWorkspaceId(r.user.workspaces[0]?.id ?? null);
    adopt(r.user);
  }, [adopt]);

  const logout = useCallback(() => {
    session.setToken(null);
    session.setWorkspaceId(null);
    setUser(null);
    router.replace("/login");
  }, [router]);

  const selectWorkspace = useCallback((id: number) => {
    session.setWorkspaceId(id);
    setWsId(id);
    router.push("/app");
  }, [router]);

  const workspace = useMemo(() => user?.workspaces.find((w) => w.id === wsId) ?? null, [user, wsId]);

  return (
    <AuthContext.Provider value={{ user, loading, workspace, login, register, logout, selectWorkspace, refresh }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

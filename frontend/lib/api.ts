"use client";

const TOKEN_KEY = "loopwise.token";
const WS_KEY = "loopwise.workspace";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

function read(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function write(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage unavailable (private mode): session only */
  }
}

export const session = {
  token: () => read(TOKEN_KEY),
  setToken: (t: string | null) => write(TOKEN_KEY, t),
  workspaceId: () => Number(read(WS_KEY)) || null,
  setWorkspaceId: (id: number | null) => write(WS_KEY, id === null ? null : String(id)),
};

function detailMessage(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const loc = Array.isArray(d?.loc) ? d.loc.filter((x: unknown) => x !== "body").join(".") : "";
        return loc ? `${loc}: ${d?.msg}` : d?.msg;
      })
      .join("; ");
  }
  return "Something went wrong";
}

export async function api<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown; form?: FormData; auth?: boolean; raw?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = session.token();
  if (opts.auth !== false && token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  if (res.status === 401 && opts.auth !== false) {
    session.setToken(null);
    // Full reload on purpose: drops every cached page state that belonged to the expired session
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    if (!window.location.pathname.startsWith("/login")) window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      message = detailMessage((await res.json()).detail);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, message);
  }
  if (opts.raw) return res as unknown as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

/** Workspace-scoped path helper: ws("/feedback") -> /api/workspaces/{id}/feedback */
export function ws(path = ""): string {
  const id = session.workspaceId();
  if (!id) throw new ApiError(400, "No workspace selected");
  return `/api/workspaces/${id}${path}`;
}

export function qs(params: Record<string, string | number | boolean | null | undefined>): string {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "" && v !== false) s.set(k, String(v));
  }
  const out = s.toString();
  return out ? `?${out}` : "";
}

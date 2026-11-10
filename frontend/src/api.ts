// EngCheck xizmati bilan ishlash. Barcha xatolar ApiError sifatida chiqadi.
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

const TOKEN_KEY = "engcheck.token";
let token: string | null = null;
let locale = "uz";
let onUnauthorized: () => void = () => {};

try {
  token = sessionStorage.getItem(TOKEN_KEY);
} catch {
  token = null;
}

export function setToken(value: string | null): void {
  token = value;
  try {
    if (value) sessionStorage.setItem(TOKEN_KEY, value);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* sessiya xotirasi yo'q bo'lsa token faqat xotirada turadi */
  }
}
export const hasToken = () => token !== null;
export const setApiLocale = (value: string) => void (locale = value);
export const setUnauthorizedHandler = (fn: () => void) => void (onUnauthorized = fn);

async function request(method: string, path: string, body?: unknown): Promise<Response> {
  const headers: Record<string, string> = { "Accept-Language": locale };
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) payload = body;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "network", "");
  }
  if (!res.ok) {
    let code = "internal_error";
    let message = res.statusText;
    try {
      const data = await res.json();
      code = data.code ?? code;
      message = data.message ?? message;
    } catch {
      /* JSON bo'lmagan javob */
    }
    if (res.status === 401 && code === "unauthorized") onUnauthorized();
    throw new ApiError(res.status, code, message);
  }
  return res;
}

async function json<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await request(method, path, body);
  return res.status === 204 ? (undefined as T) : ((await res.json()) as T);
}

export interface User { id: number; login: string; role: string; locale: string; is_active: boolean; permissions: string[] }
export interface Project { id: number; name: string; industry: string; stage: string; created_at: string }
export interface Doc {
  id: number; project_id: number; filename: string; doc_type: string; discipline: string;
  doc_number: string | null; revision: string | null; parse_status: string; parse_message: string | null; superseded: boolean;
}
export interface Param {
  tag: string; param: string; param_name: string; raw_value: string; si_value: number | null;
  si_unit: string | null; page_no: number; location: string; confidence: string;
}
export interface DocDetail extends Doc { pages: { page_no: number; text: string }[]; params: Param[]; unmapped_headers: string[]; skipped_tags: string[] }
export interface Finding {
  id: number; rule: string; rule_title: string; tag: string | null; param: string | null;
  severity: string; confidence: string; status: string; source_type: string; description: string; documents: string[];
}
export interface Evidence { document_id: number; doc_number: string | null; filename: string; doc_type: string; revision: string | null; page_no: number; location: string; value: string }
export interface Action { action: string; comment: string; user: string | null; created_at: string }
export interface FindingDetail extends Finding { project_id: number; rationale: string; recommendation: string; source: string; evidence: Evidence[]; actions: Action[] }
export interface Dashboard {
  documents: { total: number; by_type: Record<string, number>; by_status: Record<string, number> };
  findings: { total: number; by_severity: Record<string, number>; by_status: Record<string, number>; open: number; open_critical: number; confirmed_unfixed: number };
  last_run: { id: number; started_at: string; ai_mode: string; errors: { rule: string; error: string }[] } | null;
  rules: { enabled: number; total: number };
}
export interface Rule { code: string; title: string; severity: string; enabled: boolean; source: string }
export interface AuditRow { id: number; user: string | null; action: string; object_type: string; object_id: number | null; created_at: string }

export const api = {
  needsSetup: () => json<{ needs_setup: boolean }>("GET", "/setup"),
  setup: (login: string, password: string) => json<User>("POST", "/setup", { login, password }),
  login: (login: string, password: string) => json<{ token: string; user: User }>("POST", "/auth/login", { login, password }),
  logout: () => json<void>("POST", "/auth/logout"),
  me: () => json<User>("GET", "/auth/me"),
  setMyLocale: (value: string) => json<User>("PATCH", "/auth/me", { locale: value }),
  projects: () => json<Project[]>("GET", "/projects"),
  project: (id: number) => json<Project>("GET", `/projects/${id}`),
  createProject: (body: { name: string; industry: string; stage: string }) => json<Project>("POST", "/projects", body),
  deleteProject: (id: number) => json<void>("DELETE", `/projects/${id}`),
  dashboard: (id: number) => json<Dashboard>("GET", `/projects/${id}/dashboard`),
  documents: (id: number) => json<Doc[]>("GET", `/projects/${id}/documents`),
  document: (id: number) => json<DocDetail>("GET", `/documents/${id}`),
  deleteDocument: (id: number) => json<void>("DELETE", `/documents/${id}`),
  suggest: (filename: string) =>
    json<{ doc_type: string | null; doc_number: string | null; revision: string | null }>(
      "GET", `/doc-type-suggestion?filename=${encodeURIComponent(filename)}`),
  upload: (projectId: number, file: File, meta: { doc_type: string; discipline: string; doc_number: string; revision: string }) => {
    const form = new FormData();
    form.append("file", file);
    for (const [key, value] of Object.entries(meta)) if (value) form.append(key, value);
    return json<Doc>("POST", `/projects/${projectId}/documents`, form);
  },
  fileBlob: async (id: number) => (await request("GET", `/documents/${id}/file`)).blob(),
  runReview: (id: number) => json<{ id: number }>("POST", `/projects/${id}/reviews`),
  findings: (id: number, query: string) => json<Finding[]>("GET", `/projects/${id}/findings${query ? `?${query}` : ""}`),
  finding: (id: number) => json<FindingDetail>("GET", `/findings/${id}`),
  act: (id: number, action: string, comment: string) => json<FindingDetail>("POST", `/findings/${id}/actions`, { action, comment }),
  users: () => json<User[]>("GET", "/users"),
  createUser: (body: { login: string; password: string; role: string }) => json<User>("POST", "/users", body),
  updateUser: (id: number, body: { role?: string; is_active?: boolean }) => json<User>("PATCH", `/users/${id}`, body),
  rules: () => json<Rule[]>("GET", "/rules"),
  updateRule: (code: string, enabled: boolean) => json<Rule>("PATCH", `/rules/${code}`, { enabled }),
  audit: () => json<AuditRow[]>("GET", "/audit?limit=100"),
  auditVerify: () => json<{ ok: boolean; broken_at: number | null }>("GET", "/audit/verify"),
};

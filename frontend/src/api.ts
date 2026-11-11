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
export interface Project { id: number; name: string; industry: string; stage: string; created_at: string; allow_cloud_ai: boolean }
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
export interface Citation { key: string; source_id: number; title: string; standard_code: string | null; edition: string | null; status: string; license_type: string; page_no: number; excerpt: string }
export interface AiNote { id: number; provider: string; model: string; ai_mode: string; text: string; assumptions: string[]; citations: Citation[]; status: string; decided_by: string | null; created_at: string }
export interface RunInfo { id: number; started_at: string; ai_mode: string; ai_provider: string | null; ai_note: string | null; ai_message: string | null; ai_stats: { pages_reviewed: number; pages_skipped: number; pages_failed: number; pages_truncated: number } | null; ai_error_message: string | null; errors: { rule: string; error: string }[] }
export interface DgNode { id: string; label: string; kind: string; source: string; x: number; y: number; params: Record<string, string>; moved?: boolean; renamed?: boolean; original_label?: string; line_list_only?: boolean }
export interface DgEdge { id: string; from: string; to: string; label: string; source: string; directed?: boolean }
export interface DiagramData { exists: boolean; nodes: DgNode[]; edges: DgEdge[]; unconnected: string[]; differences: { kind: string; label: string }[]; orphan_edits: { id: number }[]; can_undo: boolean; can_redo: boolean; stale: boolean }
export interface L3Item { id: string; label: string; kind: string; shape: string; source: string; x: number; y: number; z: number; rot: number; w: number; d: number; h: number; position_source: string; size_source: string; renamed?: boolean; original_label?: string }
export interface Layout3dData { exists: boolean; items: L3Item[]; unit_assumed: string | null; plot_plan: string | null; differences: { kind: string; label: string }[]; orphan_edits: { id: number }[]; can_undo: boolean; can_redo: boolean; stale: boolean }
export interface AiProvider { id: number; name: string; kind: string; base_url: string | null; model: string; embed_model: string | null; enabled: boolean; is_default: boolean; is_local: boolean; has_key: boolean }
export interface AiStatus { mode: string; provider: string | null; reason: string | null; message: string | null; allow_cloud_ai: boolean }
export interface KbSource { id: number; title: string; kind: string; standard_code: string | null; edition: string | null; status: string; license_type: string; filename: string | null; approved: boolean; added_by: string | null; chunks: number }
export interface KbHit { chunk_id: number; source_id: number; title: string; kind: string; standard_code: string | null; edition: string | null; status: string; license_type: string; page_no: number; excerpt: string }
export interface FindingDetail extends Finding { project_id: number; ai_notes: AiNote[]; rationale: string; recommendation: string; source: string; evidence: Evidence[]; actions: Action[] }
export interface Dashboard {
  documents: { total: number; by_type: Record<string, number>; by_status: Record<string, number> };
  findings: { total: number; by_severity: Record<string, number>; by_status: Record<string, number>; open: number; open_critical: number; confirmed_unfixed: number; ai: number };
  last_run: RunInfo | null;
  kb: { sources: number; pending: number };
  diagram: { exists: boolean; stale: boolean; nodes: number; differences: number };
  layout3d: { exists: boolean; stale: boolean; items: number; differences: number };
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
  runReview: (id: number, useAi = false) => json<RunInfo>("POST", `/projects/${id}/reviews`, { use_ai: useAi }),
  setAllowCloud: (id: number, value: boolean) => json<Project>("PATCH", `/projects/${id}`, { allow_cloud_ai: value }),
  exportProject: async (id: number, passphrase: string) => (await request("POST", `/projects/${id}/export`, { passphrase: passphrase || null })).blob(),
  importProject: (file: File, passphrase: string) => {
    const form = new FormData();
    form.append("file", file);
    if (passphrase) form.append("passphrase", passphrase);
    return json<{ project: Project; documents: number; decisions_restored: number; decisions_unmatched: number }>("POST", "/projects/import", form);
  },
  system: () => json<{ version: string; db_encrypted: boolean; encryption_available: boolean; secret_backend: string; files_encrypted: boolean }>("GET", "/system"),
  diagram: (id: number) => json<DiagramData>("GET", `/projects/${id}/diagram`),
  diagramGenerate: (id: number) => json<DiagramData>("POST", `/projects/${id}/diagram/generate`),
  diagramEdit: (id: number, op: Record<string, unknown>) => json<DiagramData>("POST", `/projects/${id}/diagram/edits`, op),
  diagramUndo: (id: number) => json<DiagramData>("POST", `/projects/${id}/diagram/undo`),
  diagramRedo: (id: number) => json<DiagramData>("POST", `/projects/${id}/diagram/redo`),
  diagramSvg: async (id: number) => (await request("GET", `/projects/${id}/diagram.svg`)).blob(),
  layout3d: (id: number) => json<Layout3dData>("GET", `/projects/${id}/layout3d`),
  layout3dGenerate: (id: number) => json<Layout3dData>("POST", `/projects/${id}/layout3d/generate`),
  layout3dEdit: (id: number, op: Record<string, unknown>) => json<Layout3dData>("POST", `/projects/${id}/layout3d/edits`, op),
  layout3dUndo: (id: number) => json<Layout3dData>("POST", `/projects/${id}/layout3d/undo`),
  layout3dRedo: (id: number) => json<Layout3dData>("POST", `/projects/${id}/layout3d/redo`),
  aiStatus: (id: number) => json<AiStatus>("GET", `/projects/${id}/ai-status`),
  aiProviders: () => json<AiProvider[]>("GET", "/ai/providers"),
  createAiProvider: (body: Record<string, string | null>) => json<AiProvider>("POST", "/ai/providers", body),
  updateAiProvider: (id: number, body: Record<string, unknown>) => json<AiProvider>("PATCH", `/ai/providers/${id}`, body),
  deleteAiProvider: (id: number) => json<void>("DELETE", `/ai/providers/${id}`),
  defaultAiProvider: (id: number) => json<AiProvider>("POST", `/ai/providers/${id}/default`),
  testAiProvider: (id: number) => json<{ ok: boolean; error: string | null; message: string | null }>("POST", `/ai/providers/${id}/test`),
  requestAiNote: (findingId: number) => json<AiNote>("POST", `/findings/${findingId}/ai-notes`),
  decideAiNote: (noteId: number, decision: string) => json<AiNote>("POST", `/ai-notes/${noteId}/decision`, { decision }),
  proposeLesson: (findingId: number, text: string) => json<KbSource>("POST", `/findings/${findingId}/lesson`, { text: text || null }),
  kbSources: () => json<KbSource[]>("GET", "/kb/sources"),
  kbAdd: (form: FormData) => json<KbSource>("POST", "/kb/sources", form),
  kbUpdate: (id: number, body: Record<string, unknown>) => json<KbSource>("PATCH", `/kb/sources/${id}`, body),
  kbDelete: (id: number) => json<void>("DELETE", `/kb/sources/${id}`),
  kbSearch: (q: string) => json<KbHit[]>("GET", `/kb/search?q=${encodeURIComponent(q)}`),
  kbReindex: () => json<{ indexed: number; provider: string }>("POST", "/kb/reindex", {}),
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

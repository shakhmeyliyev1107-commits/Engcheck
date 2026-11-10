export const INDUSTRIES = ["gtl", "mto", "oil_refining", "gas_processing", "water_treatment", "wastewater_treatment"];
export const STAGES = ["FEED", "DD", "AS_BUILT"];
export const DOC_TYPES = ["PFD", "PID", "DATASHEET", "EQUIPMENT_LIST", "LINE_LIST", "MATERIAL_SPEC", "CALCULATION", "HAZOP", "HAZID", "OTHER"];
export const DISCIPLINES = ["process", "mechanical", "piping", "instrumentation", "electrical", "civil", "hse", "technical"];
export const SEVERITIES = ["critical", "major", "minor", "info"];
export const STATUSES = ["new", "reviewed", "confirmed", "rejected", "fixed"];
export const ROLES = ["admin", "lead", "engineer", "viewer"];
// Hujjat turi bo'yicha odatiy intizom (foydalanuvchi o'zgartira oladi).
export const DEFAULT_DISCIPLINE: Record<string, string> = {
  PFD: "process", PID: "process", DATASHEET: "mechanical", EQUIPMENT_LIST: "mechanical", LINE_LIST: "piping",
  MATERIAL_SPEC: "piping", CALCULATION: "process", HAZOP: "hse", HAZID: "hse", OTHER: "technical",
};
export const AI_KINDS = ["anthropic", "openai_compatible", "ollama"];
export const KB_KINDS = ["standard", "literature", "note"];
export const KB_STATUSES = ["active", "superseded", "withdrawn"];
export const KB_LICENSES = ["internal", "open", "licensed"];

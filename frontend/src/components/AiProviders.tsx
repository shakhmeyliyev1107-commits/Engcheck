import { type FormEvent, useState } from "react";
import { api } from "../api";
import { AI_KINDS } from "../constants";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { ErrorNote } from "./Layout";

const EMPTY = { name: "", kind: "ollama", base_url: "", model: "", embed_model: "", api_key: "" };

/** AI provayderlarini sozlash. Kalit faqat yoziladi — hech qachon qayta ko'rsatilmaydi. */
export function AiProviders() {
  const { t } = useI18n();
  const errorText = useErrorText();
  const list = useLoad(() => api.aiProviders(), []);
  const [form, setForm] = useState(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [results, setResults] = useState<Record<number, { ok: boolean; text: string }>>({});

  const guard = async (fn: () => Promise<unknown>) => {
    setError(null);
    try {
      await fn();
      list.reload();
    } catch (err) {
      setError(errorText(err));
    }
  };
  const add = (e: FormEvent) => {
    e.preventDefault();
    void guard(async () => {
      await api.createAiProvider({ ...form, base_url: form.base_url || null, model: form.model || null,
                                   embed_model: form.embed_model || null, api_key: form.api_key || null });
      setForm(EMPTY);
    });
  };
  const test = async (id: number) => {
    try {
      const r = await api.testAiProvider(id);
      setResults((x) => ({ ...x, [id]: { ok: r.ok, text: r.ok ? t("ai.testOk") : r.message ?? r.error ?? "" } }));
    } catch (err) {
      setResults((x) => ({ ...x, [id]: { ok: false, text: errorText(err) } }));
    }
  };
  const set = (key: keyof typeof EMPTY) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  return (
    <>
      <h2>{t("ai.providers")}</h2>
      <p className="muted">{t("ai.providersHint")}</p>
      <ErrorNote text={error ?? list.error} />
      <form className="panel formgrid" onSubmit={add} data-testid="ai-form" autoComplete="off">
        <label className="field">{t("ai.name")}<input name="ai-name" value={form.name} onChange={set("name")} required maxLength={80} /></label>
        <label className="field">{t("ai.kind")}
          <select name="ai-kind" value={form.kind} onChange={set("kind")}>
            {AI_KINDS.map((k) => <option key={k} value={k}>{t(`ai.kind.${k}` as Key)}</option>)}
          </select>
        </label>
        <label className="field">{t("ai.baseUrl")}<input name="ai-url" value={form.base_url} onChange={set("base_url")} placeholder={form.kind === "ollama" ? "http://127.0.0.1:11434" : form.kind === "anthropic" ? "" : "https://…/v1"} /></label>
        <label className="field">{t("ai.model")}<input name="ai-model" value={form.model} onChange={set("model")} placeholder={form.kind === "anthropic" ? "claude-opus-5-5" : ""} required={form.kind !== "anthropic"} /></label>
        <label className="field">{t("ai.embedModel")}<input name="ai-embed" value={form.embed_model} onChange={set("embed_model")} /></label>
        <label className="field">{t("ai.apiKey")}<input name="ai-key" type="password" value={form.api_key} onChange={set("api_key")} autoComplete="new-password" /></label>
        <div><button className="primary" data-testid="ai-add">{t("ai.add")}</button></div>
      </form>
      {list.data && list.data.length > 0 && (
        <div className="table-wrap" style={{ marginTop: 12 }}>
          <table>
            <thead><tr><th>{t("ai.name")}</th><th>{t("ai.kind")}</th><th>{t("ai.model")}</th><th>{t("ai.apiKey")}</th><th>{t("admin.enabled")}</th><th /></tr></thead>
            <tbody>
              {list.data.map((p) => (
                <tr key={p.id} data-testid="ai-row">
                  <td>
                    <strong>{p.name}</strong>{" "}
                    <span className="badge">{t(p.is_local ? "ai.local" : "ai.cloud")}</span>{" "}
                    {p.is_default && <span className="badge st-confirmed" data-testid="ai-default">{t("ai.default")}</span>}
                    {p.base_url && <div className="muted" style={{ fontSize: ".85rem" }}>{p.base_url}</div>}
                  </td>
                  <td>{t(`ai.kind.${p.kind}` as Key)}</td>
                  <td>{p.model}</td>
                  <td>{t(p.has_key ? "ai.keySet" : "ai.keyMissing")}</td>
                  <td><input type="checkbox" aria-label={`${p.name} ${t("admin.enabled")}`} checked={p.enabled} onChange={(e) => void guard(() => api.updateAiProvider(p.id, { enabled: e.target.checked }))} /></td>
                  <td>
                    <div className="row">
                      <button onClick={() => void test(p.id)} data-testid="ai-test">{t("ai.test")}</button>
                      {!p.is_default && <button onClick={() => void guard(() => api.defaultAiProvider(p.id))} data-testid="ai-make-default">{t("ai.makeDefault")}</button>}
                      <button className="link" onClick={() => void guard(() => api.deleteAiProvider(p.id))}>{t("common.delete")}</button>
                    </div>
                    {results[p.id] && <div className={results[p.id].ok ? "note" : "error"} style={{ marginTop: 6 }} data-testid="ai-test-result">{results[p.id].text}</div>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

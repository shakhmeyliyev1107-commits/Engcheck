import { type FormEvent, useState } from "react";
import { api, type KbHit } from "../api";
import { ErrorNote } from "../components/Layout";
import { KB_KINDS, KB_LICENSES, KB_STATUSES } from "../constants";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";

export function sourceRef(s: { title: string; standard_code: string | null; edition: string | null }) {
  return [s.title, s.standard_code, s.edition].filter(Boolean).join(" — ");
}

export function Kb() {
  const { t } = useI18n();
  const { user } = useSession();
  const errorText = useErrorText();
  const sources = useLoad(() => api.kbSources(), []);
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<KbHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [form, setForm] = useState({ title: "", kind: "literature", standard_code: "", edition: "", status: "active", license_type: "internal", text: "" });
  const [file, setFile] = useState<File | null>(null);
  const manage = can(user, "manage_kb");

  const guard = async (fn: () => Promise<unknown>) => {
    setError(null);
    setInfo(null);
    try {
      await fn();
    } catch (err) {
      setError(errorText(err));
    }
  };
  const search = (e: FormEvent) => {
    e.preventDefault();
    if (query.trim()) void guard(async () => setHits(await api.kbSearch(query.trim())));
  };
  const add = (e: FormEvent) => {
    e.preventDefault();
    void guard(async () => {
      const data = new FormData();
      for (const [key, value] of Object.entries(form)) if (value) data.append(key, value);
      if (file) data.append("file", file);
      await api.kbAdd(data);
      setForm({ ...form, title: "", standard_code: "", edition: "", text: "" });
      setFile(null);
      (e.target as HTMLFormElement).reset();
      sources.reload();
    });
  };
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  return (
    <>
      <h1>{t("kb.title")}</h1>
      <p className="sub">{t("kb.intro")}</p>
      <ErrorNote text={error ?? sources.error} />
      {info && <p className="note">{info}</p>}

      <form className="row" onSubmit={search}>
        <input style={{ flex: 1, minWidth: 220 }} value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder={t("kb.searchPlaceholder")} aria-label={t("kb.search")} data-testid="kb-query" />
        <button className="primary" data-testid="kb-search">{t("kb.search")}</button>
      </form>
      {hits && hits.length === 0 && <p className="muted" data-testid="kb-empty">{t("kb.noResults")}</p>}
      {hits && hits.map((h) => (
        <div className="hit" key={h.chunk_id} data-testid="kb-hit" style={{ marginTop: 10 }}>
          <strong>{sourceRef(h)}</strong>, {t("kb.page", { page: h.page_no })}{" "}
          <span className="badge">{t(`kb.kind.${h.kind}` as Key)}</span>{" "}
          {h.status !== "active" && <span className="badge parse-error">{t(`kb.status.${h.status}` as Key)}</span>}{" "}
          {h.license_type === "licensed" && <span className="badge">{t("kb.license.licensed")}</span>}
          <div style={{ marginTop: 6 }}>{h.excerpt}</div>
        </div>
      ))}

      {can(user, "upload") && (
        <>
          <h2>{t("kb.add")}</h2>
          <form className="panel formgrid" onSubmit={add} data-testid="kb-form">
            <label className="field">{t("kb.sourceTitle")}<input name="title" value={form.title} onChange={set("title")} required maxLength={255} /></label>
            <label className="field">{t("kb.kind")}
              <select name="kind" value={form.kind} onChange={set("kind")}>
                {KB_KINDS.map((k) => <option key={k} value={k}>{t(`kb.kind.${k}` as Key)}</option>)}
              </select>
            </label>
            <label className="field">{t("kb.code")}<input name="standard_code" value={form.standard_code} onChange={set("standard_code")} /></label>
            <label className="field">{t("kb.edition")}<input name="edition" value={form.edition} onChange={set("edition")} /></label>
            <label className="field">{t("kb.status")}
              <select name="status" value={form.status} onChange={set("status")}>
                {KB_STATUSES.map((k) => <option key={k} value={k}>{t(`kb.status.${k}` as Key)}</option>)}
              </select>
            </label>
            <label className="field">{t("kb.license")}
              <select name="license_type" value={form.license_type} onChange={set("license_type")}>
                {KB_LICENSES.map((k) => <option key={k} value={k}>{t(`kb.license.${k}` as Key)}</option>)}
              </select>
            </label>
            <label className="field wide">{t("kb.file")}<input type="file" accept=".pdf,.docx,.xlsx,.txt,.md" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label>
            <label className="field wide">{t("kb.text")}<textarea name="text" value={form.text} onChange={set("text")} /></label>
            <div><button className="primary" data-testid="kb-add">{t("kb.add")}</button></div>
          </form>
        </>
      )}

      <div className="row spread">
        <h2>{t("kb.sources")}</h2>
        {manage && (
          <button onClick={() => void guard(async () => {
            const r = await api.kbReindex();
            setInfo(t("kb.reindexed", { count: r.indexed, provider: r.provider }));
          })}>{t("kb.reindex")}</button>
        )}
      </div>
      {sources.data && sources.data.length === 0 && <p className="muted">{t("kb.noSources")}</p>}
      {sources.data && sources.data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>{t("kb.sourceTitle")}</th><th>{t("kb.kind")}</th><th>{t("kb.status")}</th><th>{t("kb.license")}</th><th>{t("kb.approved")}</th><th /></tr>
            </thead>
            <tbody>
              {sources.data.map((s) => (
                <tr key={s.id} data-testid="kb-row">
                  <td>{sourceRef(s)}{s.filename && <div className="muted" style={{ fontSize: ".85rem" }}>{s.filename}</div>}</td>
                  <td>{t(`kb.kind.${s.kind}` as Key)}</td>
                  <td>
                    {manage ? (
                      <select aria-label={t("kb.status")} value={s.status}
                              onChange={(e) => void guard(async () => { await api.kbUpdate(s.id, { status: e.target.value }); sources.reload(); })}>
                        {KB_STATUSES.map((k) => <option key={k} value={k}>{t(`kb.status.${k}` as Key)}</option>)}
                      </select>
                    ) : t(`kb.status.${s.status}` as Key)}
                  </td>
                  <td>{t(`kb.license.${s.license_type}` as Key)}</td>
                  <td>
                    {s.approved ? <span className="badge st-confirmed">{t("kb.approved")}</span> : (
                      <>
                        <span className="badge parse-error">{t("kb.pending")}</span>{" "}
                        {manage && <button data-testid="kb-approve" onClick={() => void guard(async () => { await api.kbUpdate(s.id, { approved: true }); sources.reload(); })}>{t("kb.approve")}</button>}
                      </>
                    )}
                  </td>
                  <td>{manage && <button className="link" onClick={() => { if (window.confirm(t("kb.deleteConfirm"))) void guard(async () => { await api.kbDelete(s.id); sources.reload(); }); }}>{t("common.delete")}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

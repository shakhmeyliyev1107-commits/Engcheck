import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { SeverityBadge, StatusBadge } from "../components/Badges";
import { ErrorNote } from "../components/Layout";
import { DOC_TYPES, SEVERITIES, STATUSES } from "../constants";
import { useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";

export function Findings() {
  const id = Number(useParams().id);
  const { t } = useI18n();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const query = search.toString();
  const project = useLoad(() => api.project(id), [id]);
  const dash = useLoad(() => api.dashboard(id), [id]);
  const rules = useLoad(() => api.rules(), []);
  const { data, error } = useLoad(() => api.findings(id, query), [id, query]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(search);
    if (value) next.set(key, value);
    else next.delete(key);
    setSearch(next, { replace: true });
  };
  const noRun = dash.data && dash.data.last_run === null;

  return (
    <>
      <div className="crumbs">
        <Link to="/projects">{t("nav.projects")}</Link> / <Link to={`/projects/${id}`}>{project.data?.name ?? "…"}</Link> /
      </div>
      <h1>{t("findings.title")}</h1>
      <ErrorNote text={error} />
      <div className="filters panel" style={{ marginTop: 12 }}>
        <label className="field">
          {t("findings.severity")}
          <select value={search.get("severity") ?? ""} onChange={(e) => setFilter("severity", e.target.value)} data-testid="filter-severity">
            <option value="">{t("common.all")}</option>
            {SEVERITIES.map((s) => <option key={s} value={s}>{t(`severity.${s}` as Key)}</option>)}
          </select>
        </label>
        <label className="field">
          {t("findings.status")}
          <select value={search.get("status") ?? ""} onChange={(e) => setFilter("status", e.target.value)} data-testid="filter-status">
            <option value="">{t("common.all")}</option>
            <option value="open">{t("findings.open")}</option>
            {STATUSES.map((s) => <option key={s} value={s}>{t(`status.${s}` as Key)}</option>)}
          </select>
        </label>
        <label className="field">
          {t("findings.rule")}
          <select value={search.get("rule") ?? ""} onChange={(e) => setFilter("rule", e.target.value)}>
            <option value="">{t("common.all")}</option>
            {(rules.data ?? []).map((r) => <option key={r.code} value={r.code}>{r.code} — {r.title}</option>)}
          </select>
        </label>
        <label className="field">
          {t("findings.docType")}
          <select value={search.get("doc_type") ?? ""} onChange={(e) => setFilter("doc_type", e.target.value)} data-testid="filter-doctype">
            <option value="">{t("common.all")}</option>
            {DOC_TYPES.map((d) => <option key={d} value={d}>{t(`doctype.${d}` as Key)}</option>)}
          </select>
        </label>
        {search.get("document_id") && <span className="note">{t("findings.forDocument")}</span>}
        {query && <button onClick={() => setSearch({}, { replace: true })}>{t("findings.clearFilters")}</button>}
      </div>
      {noRun && <p className="note">{t("findings.noRun")}</p>}
      {data && !noRun && <p className="muted" data-testid="finding-count">{t("findings.count", { count: data.length })}</p>}
      {data && data.length === 0 && !noRun && <p className="muted">{t("findings.empty")}</p>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t("findings.severity")}</th><th>{t("findings.description")}</th><th>{t("findings.rule")}</th>
                <th>{t("findings.documents")}</th><th>{t("findings.confidence")}</th><th>{t("findings.status")}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((f) => (
                <tr key={f.id} className="clickable" data-testid="finding-row" onClick={() => navigate(`/findings/${f.id}`)}>
                  <td><SeverityBadge value={f.severity} /></td>
                  <td><Link to={`/findings/${f.id}`} onClick={(e) => e.stopPropagation()}>{f.description}</Link></td>
                  <td title={f.rule_title}>{f.rule}</td>
                  <td>{f.documents.join(", ")}</td>
                  <td>{t(`confidence.${f.confidence}` as Key)}</td>
                  <td><StatusBadge value={f.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

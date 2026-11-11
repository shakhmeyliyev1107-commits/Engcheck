import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { ParseBadge, SeverityBadge } from "../components/Badges";
import { ErrorNote } from "../components/Layout";
import { FolderDialog } from "../components/FolderDialog";
import { UploadDialog } from "../components/UploadDialog";
import { SEVERITIES } from "../constants";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";

export function ProjectPage() {
  const id = Number(useParams().id);
  const { t, locale } = useI18n();
  const { user } = useSession();
  const navigate = useNavigate();
  const errorText = useErrorText();
  const project = useLoad(() => api.project(id), [id]);
  const dash = useLoad(() => api.dashboard(id), [id]);
  const docs = useLoad(() => api.documents(id), [id]);
  const ai = useLoad(() => api.aiStatus(id), [id]);
  const [useAi, setUseAi] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportPass, setExportPass] = useState("");
  const [importNote] = useState(() => {
    try {
      const note = window.sessionStorage.getItem("engcheck.importNote");
      window.sessionStorage.removeItem("engcheck.importNote");
      return note;
    } catch {
      return null;
    }
  });
  const [uploading, setUploading] = useState(false);
  const [folderOpen, setFolderOpen] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = () => {
    dash.reload();
    docs.reload();
  };
  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      await api.runReview(id, useAi);
      navigate(`/projects/${id}/findings`);
    } catch (err) {
      setError(errorText(err));
      setRunning(false);
    }
  };
  const removeDoc = async (docId: number) => {
    if (!window.confirm(t("doc.deleteConfirm"))) return;
    try {
      await api.deleteDocument(docId);
      reload();
    } catch (err) {
      setError(errorText(err));
    }
  };
  const removeProject = async () => {
    if (!window.confirm(t("project.deleteConfirm"))) return;
    try {
      await api.deleteProject(id);
      navigate("/projects");
    } catch (err) {
      setError(errorText(err));
    }
  };

  const d = dash.data;
  const findingsUrl = `/projects/${id}/findings`;
  const notParsed = d ? d.documents.total - (d.documents.by_status.parsed ?? 0) : 0;
  return (
    <>
      <div className="crumbs"><Link to="/projects">{t("nav.projects")}</Link> /</div>
      <div className="row spread">
        <div>
          <h1>{project.data?.name ?? "…"}</h1>
          {project.data && (
            <p className="sub">{t(`industry.${project.data.industry}` as Key)} · {t(`stage.${project.data.stage}` as Key)}</p>
          )}
        </div>
        <div className="row">
          {can(user, "upload") && <button onClick={() => setUploading(true)} data-testid="open-upload">{t("project.upload")}</button>}
          {can(user, "upload") && <button onClick={() => setFolderOpen(true)} data-testid="open-folder">{t("project.folder")}</button>}
          {can(user, "review") && ai.data && ai.data.mode !== "none" && (
            <label className="check"><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} data-testid="use-ai" /> {t("ai.useAi")}</label>
          )}
          {can(user, "review") && (
            <button className="primary" onClick={run} disabled={running || !docs.data?.length} data-testid="run-review">
              {running ? t("project.running") : t("project.runReview")}
            </button>
          )}
        </div>
      </div>
      <ErrorNote text={error ?? project.error ?? dash.error ?? docs.error} />
      {importNote && <p className="note" data-testid="import-note">{importNote}</p>}

      {d && (
        <>
          <div className="cards" data-testid="dashboard">
            <a className="card" href="#documents" data-testid="card-documents">
              <div className="num">{d.documents.total}</div>
              <div className="lbl">{t("dash.documents")}</div>
              {notParsed > 0 && <small>{t("dash.notParsed", { count: notParsed })}</small>}
            </a>
            <Link className={`card ${d.findings.open_critical ? "alert" : ""}`} to={`${findingsUrl}?severity=critical&status=open`} data-testid="card-critical">
              <div className="num">{d.findings.open_critical}</div>
              <div className="lbl">{t("dash.openCritical")}</div>
            </Link>
            <Link className="card" to={`${findingsUrl}?status=open`} data-testid="card-open">
              <div className="num">{d.findings.open}</div>
              <div className="lbl">{t("dash.open")}</div>
            </Link>
            <Link className="card" to={`${findingsUrl}?status=confirmed`} data-testid="card-unfixed">
              <div className="num">{d.findings.confirmed_unfixed}</div>
              <div className="lbl">{t("dash.unfixed")}</div>
              <small>{t("dash.unfixedHint")}</small>
            </Link>
            <div className="card">
              <div className="num">{d.rules.enabled}/{d.rules.total}</div>
              <div className="lbl">{t("dash.rules")}</div>
            </div>
            <Link className="card" to={`/projects/${id}/diagram`} data-testid="card-diagram">
              <div className="num">{d.diagram.exists ? d.diagram.nodes : "—"}</div>
              <div className="lbl">{t(d.diagram.exists ? "dash.diagram" : "dash.diagramNone")}</div>
              {d.diagram.differences > 0 && <small>{t("dash.diagramDiff", { count: d.diagram.differences })}</small>}
            </Link>
            <Link className="card" to={`/projects/${id}/layout3d`} data-testid="card-layout3d">
              <div className="num">{d.layout3d.exists ? d.layout3d.items : "—"}</div>
              <div className="lbl">{t(d.layout3d.exists ? "dash.layout3d" : "dash.layout3dNone")}</div>
              {d.layout3d.differences > 0 && <small>{t("dash.diagramDiff", { count: d.layout3d.differences })}</small>}
            </Link>
            <Link className="card" to="/kb" data-testid="card-kb">
              <div className="num">{d.kb.sources}</div>
              <div className="lbl">{t("dash.kb")}</div>
              {d.kb.pending > 0 && <small>{t("dash.kbPending", { count: d.kb.pending })}</small>}
            </Link>
            {d.findings.ai > 0 && (
              <Link className="card" to={`${findingsUrl}?rule=AI01`} data-testid="card-ai">
                <div className="num">{d.findings.ai}</div>
                <div className="lbl">{t("dash.aiFindings")}</div>
              </Link>
            )}
          </div>
          <h2>{t("dash.bySeverity")}</h2>
          <div className="sevbar">
            {SEVERITIES.map((s) => (
              <Link key={s} to={`${findingsUrl}?severity=${s}`} data-testid={`sev-${s}`}>
                <SeverityBadge value={s} /> <strong>{d.findings.by_severity[s] ?? 0}</strong>
              </Link>
            ))}
          </div>
          <p className="muted" style={{ marginTop: 12 }}>
            {d.last_run
              ? t("project.lastRun", { date: new Date(d.last_run.started_at + "Z").toLocaleString(locale === "uz" ? "uz-UZ" : locale) })
              : t("project.neverRun")}
          </p>
          {d.last_run && d.last_run.ai_mode === "none" && !d.last_run.ai_note && <p className="note" data-testid="last-run-ai">{t("ai.lastRun.none")}</p>}
          {d.last_run && d.last_run.ai_mode === "none" && d.last_run.ai_note && (
            <p className="warn" data-testid="last-run-ai">{t("ai.lastRun.failed", { reason: d.last_run.ai_message ?? d.last_run.ai_note })}</p>
          )}
          {d.last_run && d.last_run.ai_mode !== "none" && (
            <p className="note" data-testid="last-run-ai">
              {t("ai.lastRun.used", { provider: d.last_run.ai_provider ?? "", pages: d.last_run.ai_stats?.pages_reviewed ?? 0, skipped: d.last_run.ai_stats?.pages_skipped ?? 0,
                                       truncated: d.last_run.ai_stats?.pages_truncated ?? 0, failed: d.last_run.ai_stats?.pages_failed ?? 0 })}
            </p>
          )}
          {d.last_run?.ai_error_message && <p className="warn" data-testid="ai-interrupted">{t("ai.lastRun.interrupted", { reason: d.last_run.ai_error_message })}</p>}
          {d.last_run && d.last_run.errors.some((e) => e.rule !== "AI01") && (
            <p className="warn">{t("project.ruleErrors", { rules: d.last_run.errors.filter((e) => e.rule !== "AI01").map((e) => e.rule).join(", ") })}</p>
          )}
        </>
      )}

      {ai.data && (
        <div className="panel" style={{ marginTop: 14 }} data-testid="ai-status">
          {ai.data.mode === "none"
            ? t("ai.mode.none", { reason: ai.data.message ?? ai.data.reason ?? "" })
            : t(`ai.mode.${ai.data.mode}` as Key, { provider: ai.data.provider ?? "" })}
          {can(user, "manage_kb") && (
            <label className="check" style={{ marginTop: 8 }}>
              <input type="checkbox" checked={ai.data.allow_cloud_ai} data-testid="allow-cloud"
                     onChange={async (e) => {
                       try {
                         await api.setAllowCloud(id, e.target.checked);
                         ai.reload();
                       } catch (err) {
                         setError(errorText(err));
                       }
                     }} /> {t("ai.allowCloud")}
            </label>
          )}
        </div>
      )}

      <h2 id="documents">{t("project.documents")}</h2>
      {docs.data && docs.data.length === 0 && <p className="muted">{t("project.noDocuments")}</p>}
      {docs.data && docs.data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>{t("doc.number")}</th><th>{t("doc.file")}</th><th>{t("doc.type")}</th><th>{t("doc.revision")}</th><th>{t("doc.status")}</th><th /></tr>
            </thead>
            <tbody>
              {docs.data.map((doc) => (
                <tr key={doc.id} data-testid="doc-row">
                  <td><Link to={`/documents/${doc.id}`}>{doc.doc_number ?? "—"}</Link></td>
                  <td>{doc.filename}</td>
                  <td>{t(`doctype.${doc.doc_type}` as Key)}</td>
                  <td>{doc.revision ?? "—"}</td>
                  <td>
                    <ParseBadge value={doc.parse_status} />
                    {doc.superseded && <div className="warn" style={{ marginTop: 4 }} data-testid="superseded">{t("doc.superseded")}</div>}
                    {doc.parse_message && <div className="muted" style={{ fontSize: ".85rem", marginTop: 4 }}>{doc.parse_message}</div>}
                  </td>
                  <td>{can(user, "upload") && <button className="link" onClick={() => removeDoc(doc.id)}>{t("common.delete")}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {can(user, "manage_kb") && (
        <div className="panel" style={{ marginTop: 24 }}>
          <strong>{t("pkg.export")}</strong>
          <p className="muted">{t("pkg.exportHint")}</p>
          {exporting ? (
            <div className="filters">
              <label className="field">{t("pkg.passphrase")}<input type="password" value={exportPass} onChange={(e) => setExportPass(e.target.value)} autoComplete="new-password" data-testid="export-pass" /></label>
              <button className="primary" data-testid="export-download" onClick={async () => {
                try {
                  const url = URL.createObjectURL(await api.exportProject(id, exportPass));
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `${project.data?.name ?? "project"}.engpkg`;
                  a.click();
                  setTimeout(() => URL.revokeObjectURL(url), 10_000);
                  setExporting(false);
                  setExportPass("");
                } catch (err) {
                  setError(errorText(err));
                }
              }}>{t("pkg.download")}</button>
              <button onClick={() => setExporting(false)}>{t("common.cancel")}</button>
              <p className="muted" style={{ flexBasis: "100%", margin: 0 }}>{t("pkg.passphraseHint")}</p>
            </div>
          ) : <button onClick={() => setExporting(true)} data-testid="export-open">{t("pkg.export")}</button>}
        </div>
      )}
      {can(user, "delete_project") && (
        <p style={{ marginTop: 28 }}><button className="danger" onClick={removeProject}>{t("project.deleteProject")}</button></p>
      )}
      {folderOpen && <FolderDialog projectId={id} onClose={(changed) => { setFolderOpen(false); if (changed) reload(); }} />}
      {uploading && <UploadDialog projectId={id} onClose={(changed) => { setUploading(false); if (changed) reload(); }} />}
    </>
  );
}

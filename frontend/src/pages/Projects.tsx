import { type FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { ErrorNote } from "../components/Layout";
import { INDUSTRIES, STAGES } from "../constants";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";

export function Projects() {
  const { t } = useI18n();
  const { user } = useSession();
  const navigate = useNavigate();
  const errorText = useErrorText();
  const { data, error } = useLoad(() => api.projects(), []);
  const [name, setName] = useState("");
  const [industry, setIndustry] = useState("gas_processing");
  const [stage, setStage] = useState("DD");
  const [formError, setFormError] = useState<string | null>(null);
  const [pkgFile, setPkgFile] = useState<File | null>(null);
  const [pkgPass, setPkgPass] = useState("");
  const [importing, setImporting] = useState(false);

  const create = async (e: FormEvent) => {
    e.preventDefault();
    setFormError(null);
    try {
      const project = await api.createProject({ name, industry, stage });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setFormError(errorText(err));
    }
  };

  const importPackage = async (e: FormEvent) => {
    e.preventDefault();
    if (!pkgFile) return;
    setFormError(null);
    setImporting(true);
    try {
      const r = await api.importProject(pkgFile, pkgPass);
      window.sessionStorage.setItem("engcheck.importNote", t("pkg.imported", { documents: r.documents, restored: r.decisions_restored, unmatched: r.decisions_unmatched }));
      navigate(`/projects/${r.project.id}`);
    } catch (err) {
      setFormError(errorText(err));
      setImporting(false);
    }
  };

  return (
    <>
      <h1>{t("projects.title")}</h1>
      <ErrorNote text={error} />
      {can(user, "upload") && (
        <form className="panel filters" onSubmit={create} style={{ marginTop: 14 }}>
          <label className="field">
            {t("projects.name")}
            <input name="name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={200} />
          </label>
          <label className="field">
            {t("projects.industry")}
            <select name="industry" value={industry} onChange={(e) => setIndustry(e.target.value)}>
              {INDUSTRIES.map((i) => <option key={i} value={i}>{t(`industry.${i}` as Key)}</option>)}
            </select>
          </label>
          <label className="field">
            {t("projects.stage")}
            <select name="stage" value={stage} onChange={(e) => setStage(e.target.value)}>
              {STAGES.map((s) => <option key={s} value={s}>{t(`stage.${s}` as Key)}</option>)}
            </select>
          </label>
          <button className="primary">{t("projects.new")}</button>
          <ErrorNote text={formError} />
        </form>
      )}
      {can(user, "upload") && (
        <form className="panel filters" onSubmit={importPackage} style={{ marginTop: 12 }} data-testid="import-form">
          <label className="field">{t("pkg.file")}<input type="file" accept=".engpkg" onChange={(e) => setPkgFile(e.target.files?.[0] ?? null)} data-testid="import-file" required /></label>
          <label className="field">{t("pkg.passphrase")}<input type="password" value={pkgPass} onChange={(e) => setPkgPass(e.target.value)} autoComplete="off" data-testid="import-pass" /></label>
          <button disabled={importing || !pkgFile} data-testid="import-submit">{t("pkg.import")}</button>
        </form>
      )}
      {data && data.length === 0 && <p className="muted">{t("projects.empty")}</p>}
      {data && data.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>{t("projects.name")}</th><th>{t("projects.industry")}</th><th>{t("projects.stage")}</th></tr>
            </thead>
            <tbody>
              {data.map((p) => (
                <tr key={p.id}>
                  <td><Link to={`/projects/${p.id}`}>{p.name}</Link></td>
                  <td>{t(`industry.${p.industry}` as Key)}</td>
                  <td>{t(`stage.${p.stage}` as Key)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

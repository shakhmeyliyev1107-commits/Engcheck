import { type FormEvent, useState } from "react";
import { api } from "../api";
import { ErrorNote } from "../components/Layout";
import { ROLES } from "../constants";
import { useErrorText, useLoad } from "../hooks";
import { type Key, useI18n } from "../i18n";
import { can, useSession } from "../session";

export function Admin() {
  const { t, locale } = useI18n();
  const { user } = useSession();
  const errorText = useErrorText();
  const users = useLoad(() => api.users(), []);
  const rules = useLoad(() => api.rules(), []);
  const audit = useLoad(() => api.audit(), []);
  const verify = useLoad(() => api.auditVerify(), []);
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("engineer");
  const [error, setError] = useState<string | null>(null);

  if (!can(user, "manage_users")) return null;
  const guard = async (fn: () => Promise<unknown>, after: () => void) => {
    setError(null);
    try {
      await fn();
      after();
      audit.reload();
    } catch (err) {
      setError(errorText(err));
    }
  };
  const add = (e: FormEvent) => {
    e.preventDefault();
    void guard(() => api.createUser({ login, password, role }), () => { setLogin(""); setPassword(""); users.reload(); });
  };

  return (
    <>
      <h1>{t("nav.admin")}</h1>
      <ErrorNote text={error ?? users.error ?? rules.error ?? audit.error} />
      <h2>{t("admin.users")}</h2>
      <form className="panel filters" onSubmit={add}>
        <label className="field">{t("login.login")}<input value={login} onChange={(e) => setLogin(e.target.value)} required /></label>
        <label className="field">{t("login.password")}<input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8} autoComplete="new-password" /></label>
        <label className="field">{t("admin.role")}
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            {ROLES.map((r) => <option key={r} value={r}>{t(`role.${r}` as Key)}</option>)}
          </select>
        </label>
        <button className="primary">{t("admin.addUser")}</button>
      </form>
      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("login.login")}</th><th>{t("admin.role")}</th><th>{t("admin.active")}</th></tr></thead>
          <tbody>
            {(users.data ?? []).map((u) => (
              <tr key={u.id}>
                <td>{u.login}</td>
                <td>
                  <select aria-label={t("admin.role")} value={u.role} onChange={(e) => void guard(() => api.updateUser(u.id, { role: e.target.value }), users.reload)}>
                    {ROLES.map((r) => <option key={r} value={r}>{t(`role.${r}` as Key)}</option>)}
                  </select>
                </td>
                <td><input type="checkbox" aria-label={t("admin.active")} checked={u.is_active} onChange={(e) => void guard(() => api.updateUser(u.id, { is_active: e.target.checked }), users.reload)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>{t("admin.rules")}</h2>
      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("findings.rule")}</th><th>{t("findings.description")}</th><th>{t("finding.source")}</th><th>{t("admin.enabled")}</th></tr></thead>
          <tbody>
            {(rules.data ?? []).map((r) => (
              <tr key={r.code}>
                <td>{r.code}</td><td>{r.title}</td><td>{r.source}</td>
                <td><input type="checkbox" aria-label={`${r.code} ${t("admin.enabled")}`} checked={r.enabled} onChange={(e) => void guard(() => api.updateRule(r.code, e.target.checked), rules.reload)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>{t("admin.audit")}</h2>
      {verify.data && (verify.data.ok
        ? <p className="note">{t("admin.auditOk")}</p>
        : <p className="error">{t("admin.auditBroken", { id: verify.data.broken_at ?? 0 })}</p>)}
      <div className="table-wrap">
        <table>
          <thead><tr><th>{t("admin.when")}</th><th>{t("admin.user")}</th><th>{t("admin.action")}</th><th>{t("admin.object")}</th></tr></thead>
          <tbody>
            {(audit.data ?? []).map((a) => (
              <tr key={a.id}>
                <td>{new Date(a.created_at + "Z").toLocaleString(locale === "uz" ? "uz-UZ" : locale)}</td>
                <td>{a.user ?? "—"}</td><td>{a.action}</td><td>{a.object_type} {a.object_id ?? ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

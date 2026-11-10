import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";
import { api, setToken } from "../api";
import { LOCALE_NAMES, LOCALES, type Locale, useI18n } from "../i18n";
import { can, useSession } from "../session";

export function LanguageSwitch() {
  const { locale, setLocale, t } = useI18n();
  return (
    <label className="lang">
      <span className="sr-only">{t("nav.language")}</span>
      <select value={locale} onChange={(e) => setLocale(e.target.value as Locale)} data-testid="lang-switch">
        {LOCALES.map((l) => (
          <option key={l} value={l}>{LOCALE_NAMES[l]}</option>
        ))}
      </select>
    </label>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  const { user, setUser } = useSession();
  const navigate = useNavigate();
  const logout = async () => {
    try {
      await api.logout();
    } catch {
      /* sessiya allaqachon tugagan bo'lishi mumkin */
    }
    setToken(null);
    setUser(null);
    navigate("/login");
  };
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>EngCheck</strong>
          <small>{t("app.tagline")}</small>
        </div>
        <nav>
          <NavLink to="/projects">{t("nav.projects")}</NavLink>
          {can(user, "manage_users") && <NavLink to="/admin">{t("nav.admin")}</NavLink>}
        </nav>
        <div className="sidebar-foot">
          <LanguageSwitch />
          {user && (
            <div className="who">
              <span data-testid="current-user">{user.login}</span>
              <small>{t(`role.${user.role}` as never)}</small>
              <button className="link" onClick={logout}>{t("nav.logout")}</button>
            </div>
          )}
        </div>
      </aside>
      <main className="content">{children}</main>
    </div>
  );
}

export function ErrorNote({ text }: { text: string | null }) {
  return text ? <p className="error" role="alert">{text}</p> : null;
}

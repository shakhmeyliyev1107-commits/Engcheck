import { type FormEvent, useState } from "react";
import { api, setToken } from "../api";
import { ErrorNote, LanguageSwitch } from "../components/Layout";
import { useErrorText } from "../hooks";
import { useI18n } from "../i18n";
import { useSession } from "../session";

/** Kirish sahifasi; setup=true bo'lsa avval birinchi administrator yaratiladi. */
export function Login({ setup, onDone }: { setup: boolean; onDone: () => void }) {
  const { t } = useI18n();
  const { setUser } = useSession();
  const errorText = useErrorText();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (setup) await api.setup(login, password);
      const res = await api.login(login, password);
      setToken(res.token);
      setUser(res.user);
      onDone();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="auth">
      <div className="row spread">
        <div>
          <h1>EngCheck</h1>
          <p className="sub">{t("app.tagline")}</p>
        </div>
        <LanguageSwitch />
      </div>
      <div className="panel">
        <h2 style={{ marginTop: 0 }}>{t(setup ? "setup.title" : "login.title")}</h2>
        {setup && <p className="muted">{t("setup.intro")}</p>}
        <form onSubmit={submit}>
          <label className="field">
            {t("login.login")}
            <input name="login" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" required autoFocus />
          </label>
          <label className="field">
            {t("login.password")}
            <input name="password" type="password" value={password} onChange={(e) => setPassword(e.target.value)}
                   autoComplete={setup ? "new-password" : "current-password"} required minLength={setup ? 8 : undefined} />
            {setup && <small>{t("login.passwordHint")}</small>}
          </label>
          <ErrorNote text={error} />
          <button className="primary" disabled={busy}>{t(setup ? "setup.submit" : "login.submit")}</button>
        </form>
      </div>
    </div>
  );
}

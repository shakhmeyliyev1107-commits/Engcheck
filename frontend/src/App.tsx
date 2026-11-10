import { useCallback, useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, hasToken, setApiLocale, setToken, setUnauthorizedHandler, type User } from "./api";
import { Layout } from "./components/Layout";
import { I18nContext, type Locale, storedLocale, storeLocale, translate, type TFunc } from "./i18n";
import { Admin } from "./pages/Admin";
import { DocumentView } from "./pages/DocumentView";
import { FindingDetailPage } from "./pages/FindingDetail";
import { Findings } from "./pages/Findings";
import { Kb } from "./pages/Kb";
import { Login } from "./pages/Login";
import { ProjectPage } from "./pages/Project";
import { Projects } from "./pages/Projects";
import { SessionContext } from "./session";

export function App() {
  const [locale, setLocaleState] = useState<Locale>(storedLocale() ?? "uz");
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();

  setApiLocale(locale);
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const setLocale = useCallback(
    (next: Locale) => {
      storeLocale(next);
      setApiLocale(next);
      // Xizmat matnlarni profil tilida qaytaradi: avval profil yangilanadi, keyin sahifa qayta yuklanadi.
      if (hasToken()) api.setMyLocale(next).then(setUser).catch(() => {}).finally(() => setLocaleState(next));
      else setLocaleState(next);
    },
    [],
  );

  // Kirgandan so'ng: brauzerda til tanlangan bo'lsa profilga yoziladi, aks holda profil tili olinadi.
  const adoptUser = useCallback((u: User | null) => {
    setUser(u);
    if (!u) return;
    const chosen = storedLocale();
    if (chosen && chosen !== u.locale) api.setMyLocale(chosen).then(setUser).catch(() => {});
    else if (!chosen && ["uz", "en", "ru"].includes(u.locale)) {
      setApiLocale(u.locale);
      setLocaleState(u.locale as Locale);
    }
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setToken(null);
      setUser(null);
    });
    (async () => {
      try {
        const { needs_setup } = await api.needsSetup();
        setNeedsSetup(needs_setup);
        if (!needs_setup && hasToken()) adoptUser(await api.me());
      } catch {
        setToken(null);
      }
      setReady(true);
    })();
  }, [adoptUser]);

  const t: TFunc = useCallback((key, vars) => translate(locale, key, vars), [locale]);
  const i18n = useMemo(() => ({ locale, setLocale, t }), [locale, setLocale, t]);
  const session = useMemo(() => ({ user, setUser: adoptUser }), [user, adoptUser]);

  if (!ready) return <p style={{ padding: 24 }}>{t("common.loading")}</p>;

  const authPage = (
    <Login
      setup={needsSetup}
      onDone={() => {
        setNeedsSetup(false);
        navigate((location.state as { from?: string } | null)?.from ?? "/projects", { replace: true });
      }}
    />
  );
  return (
    <I18nContext.Provider value={i18n}>
      <SessionContext.Provider value={session}>
        {!user ? (
          <Routes>
            <Route path="/login" element={needsSetup ? <Navigate to="/setup" replace /> : authPage} />
            <Route path="/setup" element={needsSetup ? authPage : <Navigate to="/login" replace />} />
            <Route path="*" element={<Navigate to={needsSetup ? "/setup" : "/login"} replace
                                               state={{ from: location.pathname + location.search }} />} />
          </Routes>
        ) : (
          <Layout>
            <Routes>
              <Route path="/projects" element={<Projects />} />
              <Route path="/projects/:id" element={<ProjectPage />} />
              <Route path="/projects/:id/findings" element={<Findings />} />
              <Route path="/findings/:id" element={<FindingDetailPage />} />
              <Route path="/documents/:id" element={<DocumentView />} />
              <Route path="/kb" element={<Kb />} />
              <Route path="/admin" element={<Admin />} />
              <Route path="*" element={<Navigate to="/projects" replace />} />
            </Routes>
          </Layout>
        )}
      </SessionContext.Provider>
    </I18nContext.Provider>
  );
}

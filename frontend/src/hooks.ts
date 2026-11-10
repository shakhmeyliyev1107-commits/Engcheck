import { useCallback, useEffect, useState } from "react";
import { ApiError } from "./api";
import { useI18n } from "./i18n";

/** Xato matni: xizmat bergan mahalliylashtirilgan xabar yoki tarmoq xatosi. */
export function useErrorText(): (e: unknown) => string {
  const { t } = useI18n();
  return useCallback(
    (e: unknown) => (e instanceof ApiError && e.code !== "network" && e.message ? e.message : t("common.networkError")),
    [t],
  );
}

/** Ma'lumot yuklash: {data, error, reload}. Til o'zgarsa qayta yuklanadi. */
export function useLoad<T>(loader: () => Promise<T>, deps: unknown[]) {
  const { locale } = useI18n();
  const errorText = useErrorText();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    setError(null);
    loader()
      .then((value) => alive && setData(value))
      .catch((e) => alive && setError(errorText(e)));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, locale, tick]);
  return { data, error, reload: () => setTick((n) => n + 1) };
}

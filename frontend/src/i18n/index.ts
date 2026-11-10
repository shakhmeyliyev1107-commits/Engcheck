import { createContext, useContext } from "react";
import en from "./en.json";
import ru from "./ru.json";
import uz from "./uz.json";

export type Locale = "uz" | "en" | "ru";
export type Key = keyof typeof uz;
export const LOCALES: Locale[] = ["uz", "en", "ru"];
export const LOCALE_NAMES: Record<Locale, string> = { uz: "O‘zbekcha", en: "English", ru: "Русский" };

const DICTS: Record<Locale, Record<string, string>> = { uz, en, ru };
const STORAGE_KEY = "engcheck.locale";

export function translate(locale: Locale, key: Key, vars?: Record<string, string | number>): string {
  const template = DICTS[locale][key] ?? DICTS.uz[key] ?? key;
  return vars ? template.replace(/\{(\w+)\}/g, (m, name) => String(vars[name] ?? m)) : template;
}

export function storedLocale(): Locale | null {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return LOCALES.includes(value as Locale) ? (value as Locale) : null;
  } catch {
    return null;
  }
}

export function storeLocale(locale: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    /* saqlab bo'lmasa ham ilova ishlayveradi */
  }
}

export type TFunc = (key: Key, vars?: Record<string, string | number>) => string;

export const I18nContext = createContext<{ locale: Locale; setLocale: (l: Locale) => void; t: TFunc }>({
  locale: "uz",
  setLocale: () => {},
  t: (key, vars) => translate("uz", key, vars),
});

export const useI18n = () => useContext(I18nContext);

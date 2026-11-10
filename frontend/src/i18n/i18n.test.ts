import { expect, test } from "vitest";
import en from "./en.json";
import ru from "./ru.json";
import uz from "./uz.json";
import { translate } from "./index";

const keys = (o: Record<string, string>) => Object.keys(o).sort();

test("uch til kalitlari bir xil", () => {
  expect(keys(en)).toEqual(keys(uz));
  expect(keys(ru)).toEqual(keys(uz));
});

test("hech bir tarjima bo'sh emas", () => {
  for (const dict of [uz, en, ru]) {
    for (const [key, value] of Object.entries(dict)) expect(value.trim(), key).not.toBe("");
  }
});

test("o'zgaruvchilar uch tilda bir xil", () => {
  const vars = (s: string) => (s.match(/\{\w+\}/g) ?? []).sort();
  for (const key of Object.keys(uz) as (keyof typeof uz)[]) {
    expect(vars(en[key]), key).toEqual(vars(uz[key]));
    expect(vars(ru[key]), key).toEqual(vars(uz[key]));
  }
});

test("translate o'zgaruvchini qo'yadi va tilni tanlaydi", () => {
  expect(translate("uz", "nav.findings")).toBe("Topilmalar");
  expect(translate("en", "nav.findings")).toBe("Findings");
  expect(translate("ru", "nav.findings")).toBe("Замечания");
  expect(translate("en", "project.lastRun", { date: "X" })).toContain("X");
});

test("noma'lum kalit o'zini qaytaradi", () => {
  expect(translate("uz", "yo.q.kalit" as never)).toBe("yo.q.kalit");
});

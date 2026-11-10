import { expect, test } from "@playwright/test";
import { openProject, signIn } from "./helpers";

// review-flow.spec.ts dan keyin ishlaydi: loyiha va topilmalar tayyor bo'ladi.
test("interfeys va topilma matnlari uch tilda", async ({ page }) => {
  await signIn(page);
  await openProject(page, "Gaz tozalash bloki");
  await page.getByTestId("sev-critical").click();

  const expected = {
    uz: { title: "Topilmalar", finding: "V-102: loyiha bosimi ish bosimi qiymatidan past", sev: "Kritik", nav: "Loyihalar" },
    en: { title: "Findings", finding: "V-102: design pressure is below the operating pressure", sev: "Critical", nav: "Projects" },
    ru: { title: "Замечания", finding: "V-102: расчётное давление ниже, чем рабочее давление", sev: "Критическое", nav: "Проекты" },
  } as const;

  for (const locale of ["en", "ru", "uz"] as const) {
    await page.getByTestId("lang-switch").selectOption(locale);
    const e = expected[locale];
    await expect(page.getByRole("heading", { level: 1 })).toHaveText(e.title);
    await expect(page.getByRole("link", { name: e.finding })).toBeVisible();
    await expect(page.getByTestId("finding-row").first()).toContainText(e.sev);
    await expect(page.getByRole("link", { name: e.nav, exact: true }).first()).toBeVisible();
    await expect(page.locator("html")).toHaveAttribute("lang", locale);
  }

  // Tanlangan til qayta yuklangandan keyin ham saqlanadi
  await page.getByTestId("lang-switch").selectOption("ru");
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Замечания");
  await page.getByRole("link", { name: expected.ru.finding }).click();
  await expect(page.getByText("Техническое обоснование")).toBeVisible();
  await expect(page.getByText("Внутреннее несоответствие между документами проекта")).toBeVisible();
  await page.getByTestId("lang-switch").selectOption("uz");
});

test("kirish sahifasidagi xato xabari tanlangan tilda", async ({ page }) => {
  await page.goto("/login");
  await page.getByTestId("lang-switch").selectOption("en");
  await page.locator('input[name="login"]').fill("admin");
  await page.locator('input[name="password"]').fill("wrong-password");
  await page.locator("form button.primary").click();
  await expect(page.getByRole("alert")).toHaveText("Incorrect login or password");
});

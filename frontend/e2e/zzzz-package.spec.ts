import { expect, test } from "@playwright/test";
import { readFileSync } from "node:fs";
import { openProject, signIn } from "./helpers";

test("loyihani parol bilan eksport qilib, qayta import qilish; tizim himoyasi holati", async ({ page }) => {
  await signIn(page);
  await openProject(page, "Gaz tozalash bloki");
  await page.getByTestId("export-open").click();
  await expect(page.getByText("Parolsiz paket faqat shikastlanishdan himoyalangan")).toBeVisible();
  await page.getByTestId("export-pass").fill("parol-2026");
  const download = page.waitForEvent("download");
  await page.getByTestId("export-download").click();
  const file = await (await download).path();
  expect((await download).suggestedFilename()).toBe("Gaz tozalash bloki.engpkg");

  await page.locator("aside nav").getByRole("link", { name: "Loyihalar" }).click();
  await page.getByTestId("import-file").setInputFiles({ name: "paket.engpkg", mimeType: "application/octet-stream", buffer: readFileSync(file) });
  await page.getByTestId("import-pass").fill("xato-parol");
  await page.getByTestId("import-submit").click();
  await expect(page.getByRole("alert")).toHaveText("Parol noto‘g‘ri yoki paket o‘zgartirilgan");
  await page.getByTestId("import-pass").fill("parol-2026");
  await page.getByTestId("import-submit").click();
  await expect(page).toHaveURL(/\/projects\/\d+$/);
  await expect(page.getByTestId("import-note")).toContainText("Import qilindi:");
  await expect(page.getByTestId("import-note")).toContainText("0 ta qarorga mos topilma topilmadi");
  await expect(page.getByTestId("doc-row").first()).toBeVisible();
  await expect(page.getByTestId("ai-status")).toBeVisible();
  await expect(page.getByTestId("allow-cloud")).not.toBeChecked();          // bulut roziligi ko'chmaydi

  await page.getByRole("link", { name: "Boshqaruv" }).click();
  const status = page.getByTestId("system-status");
  await expect(status).toContainText("Yuklangan asl hujjatlar diskda shifrlanmaydi");
  await expect(status).toContainText(/Baza shifrlan/);
});

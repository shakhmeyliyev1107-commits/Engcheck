import { expect, test } from "@playwright/test";
import path from "node:path";
import { signIn } from "./helpers";

const FOLDER = path.resolve("e2e/.tmp/sample");

test("hujjatlar papkasini ulash, skanerlash va tanlangan fayllarni yuklash", async ({ page }) => {
  await signIn(page);
  await page.goto("/projects");
  await page.locator('input[name="name"]').fill("Papkadan loyiha");
  await page.getByRole("button", { name: "Yangi loyiha" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Papkadan loyiha");
  await page.getByTestId("open-folder").click();

  // Bulut havolasi qabul qilinmaydi — sababi aniq aytiladi
  await page.getByTestId("folder-path").fill("https://drive.google.com/drive/folders/abc");
  await page.getByTestId("folder-link").click();
  await expect(page.getByText("Bulut manzili (havola) qo‘llab-quvvatlanmaydi")).toBeVisible();

  await page.getByTestId("folder-path").fill(FOLDER);
  await page.getByTestId("folder-link").click();
  await expect(page.getByTestId("folder-row")).toHaveCount(6);
  await expect(page.getByTestId("folder-summary")).toContainText("Yangi: 6");
  const pid = page.getByTestId("folder-row").filter({ hasText: "GP-PID-001_RevC.dxf" });
  await expect(pid.locator("select").first()).toHaveValue("PID");

  // Bitta faylni tanlovdan chiqaramiz: faqat 5 tasi yuklanadi
  await page.getByTestId("folder-row").filter({ hasText: "GP-MS-001_RevA.docx" }).locator('input[type="checkbox"]').click();
  await expect(page.getByTestId("folder-import")).toContainText("(5)");
  await page.getByTestId("folder-import").click();
  await expect(page.getByTestId("folder-summary")).toContainText("Yangi: 1 · Yuklangan: 5");
  await page.getByTestId("folder-close").click();
  await expect(page.getByTestId("doc-row")).toHaveCount(5);

  // Qayta ochilganda papka eslab qolingan va yuklanganlar belgilangan
  await page.getByTestId("open-folder").click();
  await expect(page.getByTestId("folder-path")).toHaveValue(FOLDER);
  await expect(page.locator('[data-testid="folder-row"][data-status="imported"]')).toHaveCount(5);
  await expect(page.locator('[data-testid="folder-row"][data-status="new"]')).toHaveCount(1);
});

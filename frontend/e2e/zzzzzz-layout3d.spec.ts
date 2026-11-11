import { expect, test } from "@playwright/test";
import path from "node:path";
import { openProject, signIn } from "./helpers";

const PLOT_PLAN = path.resolve("e2e/.tmp/sample_extra/GP-PLT-001_RevA.dxf");

test("3D model: yaratish, bosh reja, jadval orqali tahrirlash, qo‘shish, orqaga qaytarish va saqlanishi", async ({ page }) => {
  await signIn(page);
  await openProject(page, "Gaz tozalash bloki");
  await expect(page.getByTestId("card-layout3d").first()).toContainText("3D model yaratilmagan");
  await page.getByTestId("card-layout3d").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("3D joylashuv modeli");
  await page.getByTestId("l3-generate").click();
  const row = (label: string) => page.getByTestId("l3-row").filter({ has: page.locator("strong", { hasText: new RegExp(`^${label}$`) }) });
  await expect(row("V-101")).toHaveCount(1);

  // Bosh reja yo'q: joylashuv taxminiy ekani ochiq aytiladi
  await expect(page.getByTestId("l3-source")).toContainText("taxminiy panjarada");
  await expect(row("V-101").getByTestId("l3-pos-src")).toHaveText("taxminiy");
  // Sahna chizilgan
  await expect(page.locator('[data-testid="l3-view"] canvas')).toHaveCount(1);
  await expect(page.getByTestId("l3-view")).toHaveAttribute("data-rendered", "7");

  // Bosh rejani yuklaymiz: model eskiradi, qayta yaratilgach joylashuv hujjatdan olinadi
  await openProject(page, "Gaz tozalash bloki");
  await page.getByTestId("open-upload").click();
  await page.getByTestId("file-input").setInputFiles(PLOT_PLAN);
  const up = page.getByTestId("upload-row");
  await up.locator("select").first().selectOption("OTHER");
  await up.locator("select").nth(1).selectOption("civil");
  await page.getByTestId("upload-submit").click();
  await expect(page.getByTestId("doc-row")).toContainText(["GP-PLT-001"]);
  await page.getByTestId("card-layout3d").first().click();
  await expect(page.getByTestId("l3-stale")).toBeVisible();
  await page.getByTestId("l3-generate").click();
  await expect(page.getByTestId("l3-stale")).toHaveCount(0);
  await expect(page.getByTestId("l3-source")).toContainText("GP-PLT-001");
  await expect(page.getByTestId("l3-source")).toContainText("taxmin");            // chizma birligi — taxmin
  await expect(row("V-102").getByTestId("l3-pos-src")).toHaveText("hujjatdan");
  await expect(row("V-102").getByTestId("l3-x")).toHaveValue("22");
  await expect(row("V-102").getByTestId("l3-y")).toHaveValue("20");
  await expect(page.getByText("Model hujjatlarga mos.")).toBeVisible();

  // Klaviatura orqali ko'chirish va burish
  await row("V-102").getByTestId("l3-x").fill("15.5");
  await row("V-102").getByTestId("l3-x").press("Enter");
  await expect(row("V-102").getByTestId("l3-pos-src")).toHaveText("qo‘lda");
  await expect(page.getByTestId("l3-differences")).toContainText("Joyi bosh rejadagidan o‘zgartirilgan: V-102");
  await row("E-101").getByTestId("l3-rot").fill("90");
  await row("E-101").getByTestId("l3-rot").press("Enter");
  await expect(page.getByTestId("l3-undo")).toBeEnabled();

  // Tanlanmagan uskunani sahnada sudrash: joyi o'zgaradi va "qo'lda" deb belgilanadi
  const at = async (id: string) => page.getByTestId("l3-view").evaluate((el, i) => (el as unknown as { project: (id: string) => { x: number; y: number } }).project(i), id);
  await page.getByTestId("l3-view").scrollIntoViewIfNeeded();   // jadvalni tahrirlash sahifani pastga surgan
  const from = await at("eq:V-101");
  await page.mouse.move(from.x, from.y);
  await page.mouse.down();
  await page.mouse.move(from.x + 40, from.y + 10, { steps: 5 });
  const during = await at("eq:V-101");
  expect(Math.abs(during.x - from.x)).toBeGreaterThan(15);                      // sudrash paytida jismning o'zi ham siljiydi
  await page.mouse.up();
  await expect(row("V-101").getByTestId("l3-pos-src")).toHaveText("qo‘lda");
  await expect(row("V-101").getByTestId("l3-x")).not.toHaveValue("10");
  await page.getByTestId("l3-undo").click();
  await expect(row("V-101").getByTestId("l3-x")).toHaveValue("10");
  await expect(row("V-101").getByTestId("l3-pos-src")).toHaveText("hujjatdan");

  // Rad etilgan qiymat maydonda qolib ketmaydi
  await row("E-101").getByTestId("l3-w").fill("0");
  await row("E-101").getByTestId("l3-w").press("Enter");
  await expect(row("E-101").getByTestId("l3-w")).toHaveValue("6");

  // Uskuna qo'shish
  await page.getByTestId("l3-new-label").fill("T-201");
  await page.getByTestId("l3-add").click();
  await expect(row("T-201")).toHaveCount(1);
  await expect(page.getByTestId("l3-differences")).toContainText("Qo‘shilgan uskuna (hujjatlarda yo‘q): T-201");

  // Orqaga / oldinga
  await page.getByTestId("l3-undo").click();
  await expect(row("T-201")).toHaveCount(0);
  await page.getByTestId("l3-redo").click();
  await expect(row("T-201")).toHaveCount(1);

  // Qayta yuklash va qayta yaratishdan keyin tahrirlar saqlanadi
  await page.reload();
  await expect(row("V-102").getByTestId("l3-x")).toHaveValue("15.5");
  await expect(row("E-101").getByTestId("l3-rot")).toHaveValue("90");
  await page.getByTestId("l3-generate").click();
  await expect(row("V-102").getByTestId("l3-x")).toHaveValue("15.5");
  await expect(row("T-201")).toHaveCount(1);

  if (process.env.L3_SHOT) await page.screenshot({ path: process.env.L3_SHOT, fullPage: true });

  // O'chirish
  await row("T-201").getByTestId("l3-delete").click();
  await expect(row("T-201")).toHaveCount(0);

  await openProject(page, "Gaz tozalash bloki");
  await expect(page.getByTestId("card-layout3d").first()).toContainText("3D modeldagi uskunalar");
});

test("kuzatuvchi 3D modelni ko‘radi, lekin tahrirlay olmaydi", async ({ page }) => {
  await signIn(page, { login: "kuzatuvchi", password: "S3cret-pass" });
  await openProject(page, "Gaz tozalash bloki");
  await page.getByTestId("card-layout3d").first().click();
  await expect(page.getByTestId("l3-row").first()).toBeVisible();
  for (const id of ["l3-generate", "l3-undo", "l3-add", "l3-delete"]) await expect(page.getByTestId(id)).toHaveCount(0);
  await expect(page.getByTestId("l3-x").first()).toBeDisabled();
});

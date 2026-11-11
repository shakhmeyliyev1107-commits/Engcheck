import { expect, test } from "@playwright/test";
import { openProject, signIn } from "./helpers";

test("sxema yaratish, tugunni sudrash, uskuna qo‘shish, ulash, orqaga qaytarish va saqlanishi", async ({ page }) => {
  await signIn(page);
  await openProject(page, "Gaz tozalash bloki");
  await page.getByTestId("card-diagram").first().click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("Prinsipial sxema");
  await page.getByTestId("dg-generate").click();
  const node = (id: string) => page.locator(`[data-testid="dg-node"][data-id="${id}"]`);
  await expect(node("eq:V-101")).toBeVisible();
  await expect(node("bd:B.L.")).toBeVisible();
  await expect(page.getByTestId("dg-edge").first()).toBeVisible();
  await expect(page.getByText("Sxema hujjatlarga mos.")).toBeVisible();

  // Sudrab ko'chirish: o'rin o'zgaradi va qayta yuklashda saqlanadi
  const before = await node("eq:V-102").getAttribute("transform");
  const box = (await node("eq:V-102").boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + box.height / 2);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 + 60, box.y + box.height / 2 + 90, { steps: 6 });
  await page.mouse.up();
  await expect(page.getByTestId("dg-undo")).toBeEnabled();
  const after = await node("eq:V-102").getAttribute("transform");
  expect(after).not.toBe(before);
  await expect(page.getByText("Sxema hujjatlarga mos.")).toBeVisible();        // ko'chirish hujjatlardan farq emas
  await page.reload();
  await expect(node("eq:V-102")).toHaveAttribute("transform", after!);

  // Uskuna qo'shish va ulash: qo'lda kiritilgani alohida belgilanadi va farqlar ro'yxatiga tushadi
  await page.getByTestId("dg-new-label").fill("V-103");
  await page.getByTestId("dg-add-node").click();
  const added = page.locator('[data-testid="dg-node"][data-source="manual"]');
  await expect(added).toHaveCount(1);
  await expect(added).toContainText("V-103");
  await page.getByTestId("dg-connect").click();
  await node("eq:V-101").click();
  await added.click();
  await expect(page.locator('[data-testid="dg-edge"][data-source="manual"]')).toHaveCount(1);
  await expect(page.getByTestId("dg-differences")).toContainText("Qo‘shilgan uskuna (hujjatlarda yo‘q): V-103");
  await expect(page.getByTestId("dg-differences")).toContainText("Qo‘shilgan ulanish");

  // Oddiy bosish (sudramasdan) tahrir yaratmaydi: "Oldinga" tarixi o'chib ketmasligi kerak
  await page.getByTestId("dg-undo").click();
  await expect(page.getByTestId("dg-redo")).toBeEnabled();
  await node("eq:E-101").click();
  await expect(page.getByTestId("dg-redo")).toBeEnabled();
  await page.getByTestId("dg-redo").click();

  // Hujjatdagi ulanishda o'q uchi bor; nomi o'zgartirilgan uskuna belgilanadi va asl nomi ko'rinadi
  await expect(page.locator('[data-testid="dg-edge"][data-source="document"]').first()).toHaveAttribute("data-directed", "true");
  page.once("dialog", (dialog) => dialog.accept("E-101X"));
  await node("eq:E-101").click();
  await page.getByTestId("dg-rename").click();
  await expect(node("eq:E-101")).toHaveAttribute("data-renamed", "true");
  await expect(node("eq:E-101")).toContainText("E-101X");
  await expect(node("eq:E-101")).toContainText("asli: E-101");
  await page.getByTestId("dg-undo").click();
  await expect(node("eq:E-101")).toHaveAttribute("data-renamed", "false");

  // Orqaga va oldinga
  await page.getByTestId("dg-undo").click();
  await expect(page.locator('[data-testid="dg-edge"][data-source="manual"]')).toHaveCount(0);
  await page.getByTestId("dg-redo").click();
  await expect(page.locator('[data-testid="dg-edge"][data-source="manual"]')).toHaveCount(1);

  // Qayta yaratish: tahrirlar saqlanadi
  await page.getByTestId("dg-generate").click();
  await expect(added).toHaveCount(1);
  await expect(node("eq:V-102")).toHaveAttribute("transform", after!);

  // O'chirish va eksport
  await added.click();
  await page.getByTestId("dg-delete").click();
  await expect(added).toHaveCount(0);
  const download = page.waitForEvent("download");
  await page.getByTestId("dg-export").click();
  expect((await download).suggestedFilename()).toBe("Gaz tozalash bloki.svg");

  await openProject(page, "Gaz tozalash bloki");
  await expect(page.getByTestId("card-diagram").first()).toContainText("Sxemadagi uskunalar");
});

test("kuzatuvchi sxemani ko‘radi, lekin tahrirlay olmaydi", async ({ page }) => {
  await signIn(page, { login: "kuzatuvchi", password: "S3cret-pass" });
  await openProject(page, "Gaz tozalash bloki");
  await page.getByTestId("card-diagram").first().click();
  await expect(page.locator('[data-testid="dg-node"]').first()).toBeVisible();
  for (const id of ["dg-generate", "dg-undo", "dg-connect", "dg-add-node"]) await expect(page.getByTestId(id)).toHaveCount(0);
  await expect(page.getByTestId("dg-export")).toBeVisible();
});

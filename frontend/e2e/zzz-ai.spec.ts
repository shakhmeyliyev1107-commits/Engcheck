import { expect, test } from "@playwright/test";
import { openProject, signIn } from "./helpers";

const PROJECT = "Gaz tozalash bloki";
const KEY = "sk-e2e-secret-key";
test.describe.configure({ mode: "serial" });

test("AI provayder ulash, bilimlar bazasi, AI tekshiruv va AI izoh", async ({ page }) => {
  await signIn(page);

  // Provayder yo'q: loyiha sahifasi buni ochiq aytadi
  await openProject(page, PROJECT);
  await expect(page.getByTestId("ai-status")).toContainText("AI mavjud emas: yoqilgan AI provayder yo‘q");
  await expect(page.getByTestId("use-ai")).toHaveCount(0);

  // Provayder qo'shish va sinash
  await page.getByRole("link", { name: "Boshqaruv" }).click();
  const form = page.getByTestId("ai-form");
  await form.locator('input[name="ai-name"]').fill("lokal-llm");
  await form.locator('select[name="ai-kind"]').selectOption("openai_compatible");
  await form.locator('input[name="ai-url"]').fill("http://127.0.0.1:8796/v1");
  await form.locator('input[name="ai-model"]').fill("test-model");
  await form.locator('input[name="ai-key"]').fill(KEY);
  await page.getByTestId("ai-add").click();
  const row = page.getByTestId("ai-row").filter({ hasText: "lokal-llm" });
  await expect(row).toContainText("Lokal");
  await expect(row).toContainText("Kalit saqlangan");
  await expect(row.getByTestId("ai-default")).toBeVisible();
  await row.getByTestId("ai-test").click();
  await expect(row.getByTestId("ai-test-result")).toHaveText("Ulanish muvaffaqiyatli");
  await expect(form.locator('input[name="ai-key"]')).toHaveValue("");
  expect(await page.content()).not.toContain(KEY);            // kalit sahifada hech qayerda yo'q
  await page.reload();
  expect(await page.content()).not.toContain(KEY);

  // Bilimlar bazasi: manba qo'shish va qidirish
  await page.getByRole("link", { name: "Bilimlar bazasi" }).click();
  const kb = page.getByTestId("kb-form");
  await kb.locator('input[name="title"]').fill("Bosimli idishlar qo‘llanmasi");
  await kb.locator('input[name="edition"]').fill("2024");
  await kb.locator('textarea[name="text"]').fill("Design pressure shall not be less than the maximum operating pressure of the vessel.");
  await page.getByTestId("kb-add").click();
  await expect(page.getByTestId("kb-row")).toContainText("Bosimli idishlar qo‘llanmasi — 2024");
  await expect(page.getByTestId("kb-row")).toContainText("Tasdiqlangan");
  await page.getByTestId("kb-query").fill("design pressure operating");
  await page.getByTestId("kb-search").click();
  await expect(page.getByTestId("kb-hit")).toContainText("maximum operating pressure");
  await page.getByTestId("kb-query").fill("zzzz qqqq");
  await page.getByTestId("kb-search").click();
  await expect(page.getByTestId("kb-empty")).toBeVisible();

  // AI bilan tekshiruv: AI topilmasi alohida belgilanadi, uydirma iqtibos qabul qilinmaydi
  await openProject(page, PROJECT);
  await expect(page.getByTestId("ai-status")).toContainText("lokal model «lokal-llm»");
  await page.getByTestId("use-ai").check();
  await page.getByTestId("run-review").click();
  await expect(page.getByTestId("ai-badge")).toHaveCount(1);
  const aiRow = page.getByTestId("finding-row").filter({ has: page.getByTestId("ai-badge") });
  await expect(aiRow).toContainText("Havola qilingan reviziya tekshirilsin");
  await expect(aiRow).toContainText("Past");                  // ishonchlilik
  await expect(page.getByText("Uydirma")).toHaveCount(0);
  await aiRow.getByRole("link").click();
  await expect(page.getByText("AI taxmini — muhandis tasdiqlamagan").first()).toBeVisible();
  await expect(page.getByText("AI xulosasi (hujjat matni asosida) — muhandis tasdiqlamagan")).toBeVisible();
  await expect(page.getByTestId("status-badge")).toHaveText("Yangi");

  await openProject(page, PROJECT);
  await expect(page.getByTestId("last-run-ai")).toContainText("AI ishlatilgan (lokal-llm)");
  await expect(page.getByTestId("card-ai")).toContainText("1");
  await expect(page.getByTestId("card-kb")).toContainText("1");

  // Qoida topilmasiga AI izoh: manbali, tasdiqlanmagan; topilma holati o'zgarmaydi
  await page.getByTestId("sev-critical").click();
  await page.getByRole("link", { name: /V-102/ }).click();
  await page.getByTestId("ask-ai").click();
  const note = page.getByTestId("ai-note");
  await expect(note).toContainText("AI taxmini — muhandis tasdiqlamagan");
  await expect(note).toContainText("Loyiha bosimi ish bosimidan past bo'lmasligi kerak [K1].");
  await expect(note.getByTestId("ai-citation")).toHaveCount(1);          // berilmagan K9 tashlab yuborilgan
  await expect(note.getByTestId("ai-citation")).toContainText("Bosimli idishlar qo‘llanmasi — 2024");
  await expect(note).toContainText("Qiymatlar almashib yozilgan bo'lishi mumkin");
  await expect(page.getByTestId("status-badge")).toHaveText("Yangi");
  await note.getByTestId("ai-accept").click();
  await expect(note.getByTestId("ai-note-status")).toHaveText("Muhandis qabul qilgan");

  // Dars taklif qilish: tasdiqlangan topilmadan
  await page.getByTestId("action-confirm").click();
  await page.getByTestId("lesson-text").fill("Loyiha va ish bosimi ustunlari almashib qolmaganini tekshiring.");
  await page.getByTestId("lesson-submit").click();
  await expect(page.getByTestId("lesson-sent")).toBeVisible();
  await page.getByRole("link", { name: "Bilimlar bazasi" }).click();
  const lesson = page.getByTestId("kb-row").filter({ hasText: "Dars:" });
  await expect(lesson).toContainText("Tasdiqlanmagan");
  await lesson.getByTestId("kb-approve").click();
  await expect(lesson).toContainText("Tasdiqlangan");
});

test("oflayn: standart provayder javob bermasa lokal modelga o‘tiladi, u ham bo‘lmasa sabab ko‘rsatiladi", async ({ page }) => {
  await signIn(page);
  await page.getByRole("link", { name: "Boshqaruv" }).click();
  const form = page.getByTestId("ai-form");
  await form.locator('input[name="ai-name"]').fill("uzilgan");
  await form.locator('select[name="ai-kind"]').selectOption("ollama");
  await form.locator('input[name="ai-url"]').fill("http://127.0.0.1:9");
  await form.locator('input[name="ai-model"]').fill("llama3");
  await page.getByTestId("ai-add").click();
  const dead = page.getByTestId("ai-row").filter({ hasText: "uzilgan" });
  await dead.getByTestId("ai-make-default").click();
  await expect(dead.getByTestId("ai-default")).toBeVisible();
  await dead.getByTestId("ai-test").click();
  await expect(dead.getByTestId("ai-test-result")).toContainText("provayderga ulanib bo‘lmadi");

  await openProject(page, PROJECT);
  await expect(page.getByTestId("ai-status")).toContainText("lokal model «lokal-llm»");   // zaxiraga o'tdi

  await page.getByRole("link", { name: "Boshqaruv" }).click();
  await page.getByLabel("lokal-llm Yoqilgan").click();          // holat xizmat javobidan keyin yangilanadi
  await expect(page.getByLabel("lokal-llm Yoqilgan")).not.toBeChecked();
  await openProject(page, PROJECT);
  await expect(page.getByTestId("ai-status")).toContainText("AI mavjud emas: provayderga ulanib bo‘lmadi");
  await expect(page.getByTestId("use-ai")).toHaveCount(0);
  await page.getByTestId("run-review").click();                                          // qoidalar AI'siz ham ishlaydi
  await expect(page.getByTestId("finding-row").first()).toBeVisible();
  await expect(page.getByTestId("ai-badge")).toHaveCount(0);
});

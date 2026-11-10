import { expect, test } from "@playwright/test";
import path from "node:path";
import { ADMIN, openProject, SAMPLE_DIR, SAMPLE_FILES, signIn } from "./helpers";

const PROJECT = "Gaz tozalash bloki";

test.describe.configure({ mode: "serial" });

test("yuklash → tekshiruv → topilma → hujjat → tasdiqlash", async ({ page }) => {
  await page.goto("/projects/1");                      // kirmagan foydalanuvchi sozlash sahifasiga tushadi
  await expect(page).toHaveURL(/\/setup$/);
  await expect(page.getByRole("heading", { name: "Dastlabki sozlash" })).toBeVisible();
  await signIn(page);

  await page.locator('input[name="name"]').fill(PROJECT);
  await page.locator('select[name="industry"]').selectOption("gas_processing");
  await page.getByRole("button", { name: "Yangi loyiha" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(PROJECT);
  await expect(page.getByTestId("run-review")).toBeDisabled();   // hujjatsiz tekshirib bo'lmaydi

  await page.getByTestId("open-upload").click();
  await page.getByTestId("file-input").setInputFiles(SAMPLE_FILES);
  await expect(page.getByTestId("upload-row")).toHaveCount(6);
  // Fayl nomidan hujjat turi, raqami va reviziyasi taklif qilinadi
  const pid = page.getByTestId("upload-row").filter({ hasText: "GP-PID-001_RevC.dxf" });
  await expect(pid.locator("select").first()).toHaveValue("PID");
  await expect(pid.locator("input").first()).toHaveValue("GP-PID-001");
  await expect(pid.locator("input").nth(1)).toHaveValue("C");
  await page.getByTestId("upload-submit").click();
  await expect(page.getByTestId("doc-row")).toHaveCount(6);
  await expect(page.getByTestId("card-documents")).toContainText("6");

  await page.getByTestId("run-review").click();
  await expect(page).toHaveURL(/\/projects\/\d+\/findings$/);
  await expect(page.getByTestId("finding-row")).toHaveCount(8);
  await expect(page.getByTestId("finding-count")).toHaveText("8 ta topilma");

  // Dashboard: kritik kartasi bosilganda filtrlangan ro'yxat ochiladi
  await page.getByRole("link", { name: PROJECT }).click();
  await expect(page.getByTestId("card-critical")).toContainText("2");
  await expect(page.getByTestId("card-open")).toContainText("8");
  await expect(page.getByText("AI ishlatilmagan")).toBeVisible();
  await page.getByTestId("card-critical").click();
  await expect(page).toHaveURL(/severity=critical&status=open/);
  await expect(page.getByTestId("finding-row")).toHaveCount(2);
  await expect(page.getByTestId("filter-severity")).toHaveValue("critical");

  // Topilma kartasi: barcha majburiy maydonlar
  await page.getByRole("link", { name: "V-101: loyiha bosimi hujjatlarda turlicha ko‘rsatilgan" }).click();
  await expect(page.getByTestId("finding-title")).toContainText("V-101");
  for (const label of ["Texnik izoh", "Manba", "Ishonchlilik", "Tavsiya etilgan tuzatish"]) {
    await expect(page.getByText(label, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("Loyiha hujjatlari o‘rtasidagi ichki nomuvofiqlik")).toBeVisible();
  await expect(page.getByText("Deterministik qoida (AI emas)")).toBeVisible();
  await expect(page.getByTestId("evidence-row")).toHaveCount(3);

  // Dalildan hujjatga: to'g'ri sahifa ochiladi va teg qatori ajratib ko'rsatiladi
  const dsRow = page.getByTestId("evidence-row").filter({ hasText: "GP-DS-V101" });
  await expect(dsRow).toContainText("14 barg");
  await dsRow.getByTestId("evidence-link").click();
  await expect(page).toHaveURL(/\/documents\/\d+\?page=1&tag=V-101/);
  await expect(page.getByTestId("doc-title")).toHaveText("GP-DS-V101");
  await expect(page.getByTestId("param-row-hl").first()).toContainText("V-101");
  await expect(page.getByTestId("doc-text")).toContainText("Ref. P&ID GP-PID-001 Rev A");

  // Asl fayl o'zgarmagan holda yuklab olinadi
  const download = page.waitForEvent("download");
  await page.getByTestId("open-original").click();
  expect((await download).suggestedFilename()).toBe("GP-DS-V101_RevA.pdf");

  // Tasdiqlash
  await page.goBack();
  await page.getByTestId("comment").fill("Datasheet yangilanishi kerak");
  await page.getByTestId("action-confirm").click();
  await expect(page.getByTestId("status-badge")).toHaveText("Tasdiqlangan");
  await expect(page.getByTestId("history-row")).toContainText("Datasheet yangilanishi kerak");
  await expect(page.getByTestId("history-row")).toContainText("admin");
  await expect(page.getByTestId("action-mark_fixed")).toBeVisible();

  // Dashboard yangilanadi: bajarilmagan tavsiyalar 1, ochiq kritik 1
  await page.getByRole("link", { name: "Umumiy ko‘rinish" }).click();
  await expect(page.getByTestId("card-unfixed")).toContainText("1");
  await expect(page.getByTestId("card-critical")).toContainText("1");
  await page.getByTestId("card-unfixed").click();
  await expect(page.getByTestId("finding-row")).toHaveCount(1);
});

test("rad etish izohsiz o‘tmaydi; qayta tekshiruvda qaror saqlanadi", async ({ page }) => {
  await signIn(page);
  await openProject(page, PROJECT);
  await page.getByTestId("card-open").click();
  await page.getByRole("link", { name: /P-101B/ }).click();
  await page.getByTestId("action-reject").click();
  await expect(page.getByRole("alert")).toHaveText("Rad etish uchun izoh yozing");
  await expect(page.getByTestId("status-badge")).toHaveText("Yangi");
  await page.getByTestId("comment").fill("Vendor ma'lumoti kutilmoqda");
  await page.getByTestId("action-reject").click();
  await expect(page.getByTestId("status-badge")).toHaveText("Rad etilgan");

  await openProject(page, PROJECT);
  await page.getByTestId("run-review").click();
  await expect(page.getByTestId("finding-row")).toHaveCount(8);
  await page.getByTestId("filter-status").selectOption("rejected");
  await expect(page.getByTestId("finding-row")).toHaveCount(1);
  await expect(page.getByTestId("finding-row")).toContainText("P-101B");
});

test("hujjat sahifalari: 2-sahifadagi dalil 2-sahifani ochadi", async ({ page }) => {
  await signIn(page);
  await openProject(page, PROJECT);
  await page.getByTestId("sev-minor").click();
  await page.getByRole("link", { name: /P-101B/ }).click();
  await page.getByTestId("evidence-link").click();
  await expect(page).toHaveURL(/page=2/);
  await expect(page.getByTestId("page-indicator")).toHaveText("2-sahifa / 2");
  await expect(page.getByTestId("doc-text")).toContainText("P-101B");
  await page.getByTestId("doc-findings").click();
  await expect(page).toHaveURL(/document_id=\d+/);
  await expect(page.getByTestId("finding-row").first()).toBeVisible();
});

test("DWG va buzilgan fayl: aniq xabar, qolgan hujjatlar joyida", async ({ page }) => {
  await signIn(page);
  await openProject(page, PROJECT);
  await page.getByTestId("open-upload").click();
  await page.getByTestId("file-input").setInputFiles([
    { name: "GP-PID-002_RevA.dwg", mimeType: "application/acad", buffer: Buffer.concat([Buffer.from("AC1032"), Buffer.alloc(64)]) },
    { name: "GP-LL-002_RevA.xlsx", mimeType: "application/octet-stream", buffer: Buffer.from("PK\u0003\u0004 broken") },
  ]);
  await page.getByTestId("upload-submit").click();
  await expect(page.getByTestId("doc-row")).toHaveCount(8);
  const dwg = page.getByTestId("doc-row").filter({ hasText: "GP-PID-002_RevA.dwg" });
  await expect(dwg).toContainText("Qo‘llab-quvvatlanmaydi");
  await expect(dwg).toContainText("DXF ga o‘girib yuklang");
  await expect(page.getByTestId("doc-row").filter({ hasText: "GP-LL-002_RevA.xlsx" })).toContainText("Xato");
  await expect(page.getByTestId("card-documents")).toContainText("2 ta hujjat tahlil qilinmadi");

  // Bir xil faylni qayta yuklash rad etiladi
  await page.getByTestId("open-upload").click();
  await page.getByTestId("file-input").setInputFiles(path.join(SAMPLE_DIR, "GP-MS-001_RevA.docx"));
  await page.getByTestId("upload-submit").click();
  await expect(page.getByTestId("upload-row")).toContainText("Bu fayl loyihaga allaqachon yuklangan");
});

test("kuzatuvchi faqat ko‘radi", async ({ page, request }) => {
  const login = await request.post("/api/auth/login", { data: ADMIN });
  const { token } = await login.json();
  const created = await request.post("/api/users", {
    headers: { Authorization: `Bearer ${token}` },
    data: { login: "kuzatuvchi", password: "S3cret-pass", role: "viewer" },
  });
  expect(created.status()).toBe(201);

  await signIn(page, { login: "kuzatuvchi", password: "S3cret-pass" });
  await expect(page.getByRole("link", { name: "Boshqaruv" })).toHaveCount(0);
  await expect(page.locator('input[name="name"]')).toHaveCount(0);       // loyiha yarata olmaydi
  await openProject(page, PROJECT);
  await expect(page.getByTestId("open-upload")).toHaveCount(0);
  await expect(page.getByTestId("run-review")).toHaveCount(0);
  await page.getByTestId("card-open").click();
  await page.getByTestId("finding-row").first().click();
  await expect(page.getByTestId("view-only")).toBeVisible();
  await expect(page.getByTestId("action-confirm")).toHaveCount(0);
  await expect(page.getByTestId("evidence-row").first()).toBeVisible();
});

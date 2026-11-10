import { expect, type Page } from "@playwright/test";
import path from "node:path";

export const ADMIN = { login: "admin", password: "S3cret-pass" };
export const SAMPLE_DIR = path.resolve("e2e/.tmp/sample");
export const SAMPLE_FILES = [
  "GP-PID-001_RevC.dxf", "GP-EQL-001_RevB.xlsx", "GP-LL-001_RevB.xlsx",
  "GP-DS-V101_RevA.pdf", "GP-DS-P101_RevA.pdf", "GP-MS-001_RevA.docx",
].map((f) => path.join(SAMPLE_DIR, f));

/** Tizimga kiradi; birinchi marta bo'lsa administrator yaratadi. */
export async function signIn(page: Page, user = ADMIN) {
  await page.goto("/");
  await page.locator('input[name="login"]').fill(user.login);
  await page.locator('input[name="password"]').fill(user.password);
  await page.locator("form button.primary").click();
  await expect(page.getByTestId("current-user")).toHaveText(user.login);
}

export async function openProject(page: Page, name: string) {
  await page.goto("/projects");
  await page.getByRole("link", { name, exact: true }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(name);
}

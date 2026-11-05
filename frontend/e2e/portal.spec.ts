import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("real API search, language persistence and keyboard document reading", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("button", { name: "Controlled NOM pump", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "English", exact: true }).click();
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  await page.getByRole("textbox", { name: "Search publications", exact: true }).fill("motor");
  const opener = page.getByRole("button", { name: "Controlled NOM motor", exact: true });
  await expect(opener).toBeVisible();
  await expect(page.getByRole("button", { name: "Controlled NOM pump", exact: true })).toHaveCount(0);
  await opener.click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Controlled sample text");
  await expect(page.getByRole("button", { name: "Close reader" })).toBeFocused();
  const downloading = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download saved copy" }).click();
  const download = await downloading;
  expect(await download.failure()).toBeNull();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();
});

test("partial source state and saved publications are accessible on desktop and mobile", async ({ page }) => {
  await page.goto("/?lang=en");
  await expect(page.getByRole("button", { name: "Controlled NOM pump", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "SIDOF status", exact: true }).click();
  await expect(page.getByText("Saved publications", { exact: true })).toBeVisible();
  await expect(page.getByText("Last complete period check", { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations).toEqual([]);
});

test("reader has no automatically detectable accessibility violations", async ({ page }) => {
  await page.goto("/?lang=es");
  await page.getByRole("button", { name: "Controlled NOM motor", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("Controlled sample text");
  await dialog.evaluate(async (element) => {
    await Promise.all(element.getAnimations().map((animation) => animation.finished));
  });
  const scan = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21aa"]).analyze();
  expect(scan.violations).toEqual([]);
});

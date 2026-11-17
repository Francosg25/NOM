import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test("visit summary, publication facts and saved-version comparison work with the real API", async ({ page }) => {
  await page.goto("/?lang=en");
  await expect(page.getByRole("heading", { name: "Your first summary", exact: true })).toBeVisible();
  await expect(page.getByText("Added to the portal does not mean published today.", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Controlled NOM motor", exact: true }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("region", { name: "Publication facts" })).toBeVisible();
  await dialog.getByRole("button", { name: "Compare versions", exact: true }).click();
  await expect(dialog.getByText("There are differences in the saved text.", { exact: true })).toBeVisible();
  await expect(dialog.locator(".comparison-row ins").filter({ hasText: "50 kg" })).toBeVisible();
  await dialog.getByRole("button", { name: "Close comparison", exact: true }).click();
  await expect(dialog.locator(".comparison-row")).toHaveCount(0);
});

test("returning to saved news does not wait for a new API response", async ({ page }) => {
  let release!: () => void;
  const pending = new Promise<void>((resolve) => { release = resolve; });
  let newsRequests = 0;
  await page.route("**/api/publications?**", async (route) => {
    const url = new URL(route.request().url());
    if (url.searchParams.get("source_kind") === "sidof" && ++newsRequests > 1) await pending;
    await route.continue();
  });
  try {
    await page.goto("/?lang=en");
    const news = page.getByRole("button", { name: "Controlled NOM pump", exact: true });
    await expect(news).toBeVisible();
    await page.getByRole("button", { name: "NOM catalogue", exact: true }).click();
    await expect(news).toHaveCount(0);
    await page.getByRole("button", { name: "Latest publications", exact: true }).click();
    // The second SIDOF request cannot complete until release() below.
    await expect(news).toBeVisible();
    await expect.poll(() => newsRequests).toBe(2);
  } finally {
    release();
  }
});

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

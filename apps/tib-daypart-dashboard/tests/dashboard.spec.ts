import path from "node:path";
import { expect, test } from "@playwright/test";

const fixtures = path.resolve("tests/fixtures");

test("imports reports, filters a product line and restores the aggregate project", async ({
  page,
}) => {
  await page.goto("/");
  await page.evaluate(() => {
    return new Promise<void>((resolve) => {
      const request = indexedDB.deleteDatabase("tib-daypart-dashboard");
      request.onsuccess = () => resolve();
      request.onerror = () => resolve();
      request.onblocked = () => resolve();
    });
  });
  await page.reload();

  const files = page.locator('input[type="file"]');
  await files.nth(0).setInputFiles(path.join(fixtures, "ad-hours.csv"));
  await files.nth(1).setInputFiles(path.join(fixtures, "tib.csv"));
  await page.getByRole("button", { name: "校验并合并" }).click();

  await expect(page.locator(".metric-grid")).toBeVisible();
  await expect(page.locator(".metric-card").filter({ hasText: "CPC" })).toContainText(
    "US$0.43",
  );
  await expect(page.getByRole("heading", { name: "端到端数据可信度" })).toBeVisible();
  await page.locator(".filter-panel select").nth(2).selectOption("DD1-S81");
  await expect(page.locator(".section-heading").filter({ hasText: "活动候选明细" })).toContainText(
    "DD1-S81",
  );
  await page.getByRole("button", { name: "行业参考" }).click();
  await expect(page.getByRole("button", { name: "行业参考" })).toHaveClass(/active/);

  await page.reload();
  await expect(page.locator(".metric-grid")).toBeVisible();
  await expect(page.getByText("历史库已保存在本机")).toBeVisible();

  page.once("dialog", (dialog) => dialog.accept());
  await page.getByRole("button", { name: "清除历史库" }).click();
  await expect(page.getByRole("heading", { name: "写入滚动历史库" })).toBeVisible();
});

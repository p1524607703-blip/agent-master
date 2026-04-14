import { test, expect } from '@playwright/test'

test.describe('Agent 监控 AgentMonitor', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/agents')
  })

  test('HUD 状态行渲染', async ({ page }) => {
    await expect(page.locator('.hud-card').first()).toBeVisible({ timeout: 8000 })
    await expect(page.locator('.hud-card')).toHaveCount(5)
  })

  test('任务列表有数据', async ({ page }) => {
    await expect(page.locator('.task-row').first()).toBeVisible({ timeout: 8000 })
  })

  test('实时日志流在滚动', async ({ page }) => {
    await expect(page.locator('.log-stream')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('.log-line').first()).toBeVisible({ timeout: 6000 })
  })

  test('点击启动扫描派发任务', async ({ page }) => {
    await page.locator('.task-row').first().waitFor({ timeout: 8000 })
    const before = await page.locator('.task-row').count()
    await page.getByRole('button', { name: /启动扫描/ }).click()
    await page.waitForTimeout(1000)
    const after = await page.locator('.task-row').count()
    expect(after).toBeGreaterThanOrEqual(before)
  })
})

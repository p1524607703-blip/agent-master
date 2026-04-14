import { test, expect } from '@playwright/test'

test.describe('仪表盘 Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/')
  })

  test('页面标题正确', async ({ page }) => {
    await expect(page).toHaveTitle(/仪表盘|RADAR/)
  })

  test('侧边栏导航渲染', async ({ page }) => {
    await expect(page.locator('.sidebar')).toBeVisible()
    await expect(page.locator('.nav-item')).toHaveCount(5)
  })

  test('统计卡片显示数据', async ({ page }) => {
    // 等待 API 数据加载（stat-card 有数字出现）
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 })
    const cards = page.locator('.stat-card')
    await expect(cards).toHaveCount(4)
  })

  test('趋势图表渲染', async ({ page }) => {
    await expect(page.locator('.chart')).toBeVisible({ timeout: 8000 })
  })
})

import { test, expect } from '@playwright/test'

test.describe('趋势发现 TrendDiscovery', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/trends')
  })

  test('平台卡片加载', async ({ page }) => {
    await expect(page.locator('.platform-card').first()).toBeVisible({ timeout: 8000 })
    const cards = page.locator('.platform-card')
    await expect(cards).toHaveCount(4)
  })

  test('趋势列表有数据', async ({ page }) => {
    await expect(page.locator('.trend-item').first()).toBeVisible({ timeout: 8000 })
  })

  test('点击平台 tab 过滤', async ({ page }) => {
    await page.locator('.platform-tab', { hasText: 'TikTok' }).click()
    await expect(page.locator('.trend-item').first()).toBeVisible({ timeout: 5000 })
  })

  test('点击趋势项显示详情', async ({ page }) => {
    await page.locator('.trend-item').first().waitFor({ timeout: 8000 })
    await page.locator('.trend-item').first().click()
    await expect(page.locator('.trend-detail-card')).toBeVisible()
  })
})

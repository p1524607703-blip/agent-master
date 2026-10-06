import { test, expect } from '@playwright/test'

test.describe('选品看板 ProductBoard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/products')
  })

  test('商品卡片网格加载', async ({ page }) => {
    await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 8000 })
  })

  test('统计行显示数字', async ({ page }) => {
    await expect(page.locator('.stat-card').first()).toBeVisible({ timeout: 8000 })
    await expect(page.locator('.stat-card')).toHaveCount(4)
  })

  test('状态筛选 Tab 切换', async ({ page }) => {
    await page.locator('.product-card').first().waitFor({ timeout: 8000 })
    // 点击「已推荐」radio
    await page.locator('.el-radio-button__inner', { hasText: '已推荐' }).click()
    await page.waitForTimeout(500)
    // 所有卡片状态应为 recommended
    const statusBars = page.locator('.status--recommended')
    await expect(statusBars.first()).toBeVisible()
  })

  test('新增商品弹窗打开', async ({ page }) => {
    await page.getByRole('button', { name: /添加商品/ }).click()
    await expect(page.locator('.el-dialog')).toBeVisible()
    await page.keyboard.press('Escape')
  })
})

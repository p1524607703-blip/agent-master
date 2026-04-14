import { test, expect } from '@playwright/test'

const routes = [
  { path: '/',         title: '仪表盘' },
  { path: '/trends',   title: '趋势发现' },
  { path: '/analysis', title: 'AI' },
  { path: '/products', title: '选品' },
  { path: '/agents',   title: 'Agent' },
]

test.describe('路由导航', () => {
  test('所有页面可正常访问（无白屏/报错）', async ({ page }) => {
    for (const route of routes) {
      await page.goto(route.path)
      // 等待 sidebar 渲染（说明 Vue 应用已挂载）
      await expect(page.locator('.sidebar')).toBeVisible({ timeout: 8000 })
      // 确认页面无 JS 运行时错误
      const errors: string[] = []
      page.on('pageerror', err => errors.push(err.message))
      await page.waitForTimeout(500)
      expect(errors.filter(e => !e.includes('favicon'))).toHaveLength(0)
    }
  })

  test('侧边栏点击导航正确跳转', async ({ page }) => {
    await page.goto('/')
    await expect(page.locator('.sidebar')).toBeVisible({ timeout: 8000 })
    // 点击「趋势发现」
    await page.locator('.nav-item').nth(1).click()
    await expect(page).toHaveURL(/trends/)
    // 点击「选品看板」
    await page.locator('.nav-item').nth(3).click()
    await expect(page).toHaveURL(/products/)
  })
})

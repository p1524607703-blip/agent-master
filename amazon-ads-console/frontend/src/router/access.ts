export type NavGroup = { title: string; items: [string, string][] }

export const ROLE_HOME: Record<string, string> = {
  super_admin: '/operator-cpo', management: '/operator-cpo', operator: '/my-cpo',
}
export const homeFor = (role?: string | null) => ROLE_HOME[role || ''] || '/login'
const business: NavGroup = { title: '经营数据', items: [
  ['/operator-cpo', 'CPO 单双数据情况'], ['/ad-allocation', '广告费用分摊'], ['/product-mappings', '产品映射'],
] }
const system: NavGroup = { title: '系统管理', items: [
  ['/data-maintenance', '数据维护'], ['/codex-devices', '人员与设备'], ['/diagnostics', '系统诊断'],
] }
export function navigationFor(role?: string | null): NavGroup[] {
  if (role === 'operator') return [{title: '我的数据', items: [
    ['/my-cpo', '我的 CPO 明细'], ['/ad-allocation', '广告费用分摊'],
    ['/data-changes', '新品 / ASIN 提交'],
  ]}]
  if (role === 'management') return [business]
  if (role === 'super_admin') return [business, system]
  return []
}
export function canAccessRoute(role: string | null | undefined, path: string): boolean {
  if (navigationFor(role).some(group => group.items.some(([target]) => target === path))) return true
  if (path === '/data-changes') return ['operator', 'management', 'super_admin'].includes(role || '')
  return /^\/operators\/[^/]+$/.test(path) && ['management', 'super_admin'].includes(role || '')
}

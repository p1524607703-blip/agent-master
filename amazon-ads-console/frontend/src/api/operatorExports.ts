import { API_BASE, AUTH_TOKEN_KEY } from './client'

type Period = 'daily' | 'weekly' | 'monthly'
type Kind = 'summary' | 'all' | 'detail'

/** Download binary from the server, never from a cached/filtered UI table. */
export async function downloadOperatorReport(
  kind: Kind, period: Period, date: string, operator?: string
): Promise<void> {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  if (!token) throw new Error('登录已失效，请重新登录')
  const params = new URLSearchParams({ period })
  if (date) params.set('date', date)
  let path = '/operator-reports/summary.xlsx'
  if (kind === 'all') path = '/operator-reports/all.zip'
  if (kind === 'detail') {
    if (!operator) throw new Error('缺少运营姓名')
    path = '/operator-reports/operators/' + encodeURIComponent(operator) + '.xlsx'
  }
  const res = await fetch(API_BASE + path + '?' + params.toString(), {
    headers: { Authorization: 'Bearer ' + token },
    cache: 'no-store',
    credentials: 'omit',
  })
  if (!res.ok) {
    if (res.status === 401) throw new Error('登录已失效（401）')
    if (res.status === 403) throw new Error('当前账号没有该报表的导出权限（403）')
    if (res.status === 413) throw new Error('导出范围过大，请缩小报表范围')
    throw new Error('导出失败（HTTP ' + res.status + '）')
  }
  const expected = kind === 'all' ? 'application/zip' : 'spreadsheetml.sheet'
  if (!(res.headers.get('Content-Type') || '').includes(expected)) {
    throw new Error('服务器返回的文件类型不正确')
  }
  const blob = await res.blob()
  if (!blob.size) throw new Error('导出的文件为空')
  const ref = URL.createObjectURL(blob)
  try {
    const name = kind === 'all' ? '全部运营报表' : kind === 'detail' ? (operator + '_运营明细') : '所有成员概览'
    const link = document.createElement('a')
    link.href = ref
    link.download = name + '_' + (date || '最新') + (kind === 'all' ? '.zip' : '.xlsx')
    document.body.appendChild(link)
    link.click()
    link.remove()
  } finally {
    window.setTimeout(() => URL.revokeObjectURL(ref), 1000)
  }
}

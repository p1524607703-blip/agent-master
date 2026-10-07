export type CpoProduct = {
  code?: string
  parentAsin?: string | null
  group?: string
  brand?: string
  mappingStatus?: string
  dataStatus?: string
  businessAccounts?: string[]
  adAccounts?: string[]
  spend?: number | null
}

export type CpoQualitySummary = {
  missingBusinessProducts?: number | null
  unpairedAdSpend?: number | null
  totalOrders?: number | null
}

export type SourceCompleteness = {
  businessDays?: number
  advertisedProductDays?: number
  purchasedProductDays?: number
  completeDays?: number
  completeDates?: string[]
  sourceDates?: { business?: string[]; advertisedProduct?: string[]; purchasedProduct?: string[] }
  sourceMissingDates?: { business?: string[]; advertisedProduct?: string[]; purchasedProduct?: string[] }
  missingAccountsByDate?: { business?: Record<string, string[]>; advertisedProduct?: Record<string, string[]>; purchasedProduct?: Record<string, string[]> }
}

export type CpoQualityData = {
  final_cpo?: boolean
  sourceCompleteness?: SourceCompleteness
  summary?: CpoQualitySummary
  detailSummary?: CpoQualitySummary
  products?: CpoProduct[]
  missingBusinessProductList?: CpoProduct[]
  coverageDays?: number
  expectedDays?: number
  businessMappingConflictOrders?: number
  unmappedAdSpend?: number
  qualityReasons?: string[]
  warning?: string
}

export function qualitySummary(data: CpoQualityData): CpoQualitySummary {
  return data.detailSummary || data.summary || {}
}

export function missingBusinessList(data: CpoQualityData): CpoProduct[] {
  const products = data.missingBusinessProductList || (data.products || []).filter(
    p => p.mappingStatus === 'confirmed_no_business' || p.dataStatus === '缺业务报告',
  )
  const unique = new Map<string, CpoProduct>()
  for (const product of products) unique.set(`${product.code || ''}|${product.parentAsin || ''}`, product)
  return [...unique.values()]
}

export function qualityLabel(data: CpoQualityData): string {
  return data.final_cpo === true ? '完整口径' : data.final_cpo === false ? '非完整口径' : '口径待确认'
}

export function qualityReasons(data: CpoQualityData): string[] {
  if (data.qualityReasons?.length) return data.qualityReasons
  const summary = qualitySummary(data)
  const reasons: string[] = []
  const complete = data.sourceCompleteness?.completeDays ?? data.coverageDays
  if (complete === 0) reasons.push('当前区间没有三项来源同时完整的可计算日期。')
  else if (complete != null && data.expectedDays != null && complete < data.expectedDays) {
    reasons.push(`三项来源同时完整日期覆盖 ${complete}/${data.expectedDays} 天；未覆盖日期不进入计算。`)
  }
  if ((summary.missingBusinessProducts ?? 0) > 0) {
    reasons.push(`有 ${summary.missingBusinessProducts} 个已确认产品缺业务侧记录；请核对下方产品清单。`)
  }
  if ((summary.unpairedAdSpend ?? 0) > 0.005) {
    reasons.push('部分广告花费尚未配对到业务侧订单，相关 CPO 暂不能认定为完整。')
  }
  if ((data.businessMappingConflictOrders ?? 0) > 0.005) reasons.push('存在业务产品映射冲突，相关订单需确认归属。')
  if ((data.unmappedAdSpend ?? 0) > 0.005) reasons.push('存在尚未归属产品的广告花费。')
  if (data.final_cpo === true) reasons.push('服务端已确认当前口径完整。')
  else if (!reasons.length) reasons.push(data.final_cpo === false
    ? '服务端标记为非完整口径；当前响应未提供具体阻断原因，请核对产品状态与来源覆盖。'
    : '尚未取得完整性判定，请刷新数据后确认。')
  return reasons
}

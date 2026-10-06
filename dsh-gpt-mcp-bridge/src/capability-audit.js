export function capabilityAudit(records, catalog, limit = 50) {
  const recent = [...records].sort((a, b) => b.createdAt - a.createdAt).slice(0, limit)
  const observed = new Map()
  for (const task of recent) {
    for (const name of new Set(task.summary?.toolNames ?? [])) {
      observed.set(name, (observed.get(name) ?? 0) + 1)
    }
  }
  const advertised = [...new Set(catalog?.toolNames ?? [])].sort()
  return {
    catalog: catalog ? { source: 'DSH external model request', observedAt: catalog.observedAt,
      nativeToolCount: advertised.length, nativeTools: advertised } : null,
    recentTasks: { sampled: recent.length, limit,
      withDurableSummary: recent.filter(task => task.summary).length },
    usedInRecentTasks: [...observed].sort(([a], [b]) => a.localeCompare(b))
      .map(([name, taskCount]) => ({ name, taskCount })),
    advertisedButNotUsedInSample: advertised.filter(name => !observed.has(name)),
    interpretation: 'Advertised means DSH offered the tool to the model; recent usage is not a functional test. An unused tool may simply not have been needed. UI-only features are outside this native-tool catalog.',
  }
}

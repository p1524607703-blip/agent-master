import { test } from 'node:test'
import assert from 'node:assert/strict'
import { capabilityAudit } from '../src/capability-audit.js'

test('capability audit distinguishes advertised tools from recent usage', () => {
  const records = [
    { createdAt: 3, summary: { toolNames: ['bash', 'read', 'bash'] } },
    { createdAt: 2, summary: { toolNames: ['read'] } },
    { createdAt: 1, summary: { toolNames: ['subagent'] } },
  ]
  const report = capabilityAudit(records, { observedAt: 123, toolNames: ['read', 'bash', 'subagent', 'workflow'] }, 2)
  assert.deepEqual(report.catalog.nativeTools, ['bash', 'read', 'subagent', 'workflow'])
  assert.deepEqual(report.recentTasks, { sampled: 2, limit: 2, withDurableSummary: 2 })
  assert.deepEqual(report.usedInRecentTasks, [{ name: 'bash', taskCount: 1 }, { name: 'read', taskCount: 2 }])
  assert.deepEqual(report.advertisedButNotUsedInSample, ['subagent', 'workflow'])
  assert.match(report.interpretation, /not a functional test/)
})

test('missing live catalog is reported as unobserved, not unsupported', () => {
  const report = capabilityAudit([], null)
  assert.equal(report.catalog, null)
  assert.deepEqual(report.advertisedButNotUsedInSample, [])
})

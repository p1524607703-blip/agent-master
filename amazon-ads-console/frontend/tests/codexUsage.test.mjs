import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'

const source = readFileSync(new URL('../src/utils/codexUsage.ts', import.meta.url), 'utf8')
const output = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
const { sumTokens, usageShare, percentLabel } = await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`)

test('aggregate multiple devices and numeric database values without string concatenation', () => {
  assert.equal(sumTokens([{ todayTokens: '38', totalTokens: '38' }, { todayTokens: 38, totalTokens: 38 }], 'todayTokens'), 76)
})

test('member share uses the full population denominator for the same period', () => {
  const a = [{ todayTokens: 30, totalTokens: 300 }, { todayTokens: 10, totalTokens: 100 }]
  const b = [{ todayTokens: 60, totalTokens: 100 }]
  assert.equal(percentLabel(usageShare(sumTokens(a, 'todayTokens'), sumTokens([...a, ...b], 'todayTokens'))), '40.0%')
  assert.equal(percentLabel(usageShare(sumTokens(a, 'totalTokens'), sumTokens([...a, ...b], 'totalTokens'))), '80.0%')
})

test('missing measurement and a zero denominator do not claim a percentage', () => {
  assert.equal(sumTokens([{ todayTokens: null, totalTokens: null }], 'totalTokens'), null)
  assert.equal(usageShare(null, 100), null)
  assert.equal(usageShare(0, 0), null)
  assert.equal(percentLabel(usageShare(0, 100)), '0.0%')
  assert.equal(percentLabel(usageShare(null, 100)), '—')
})

test('unknown records stay excluded and invalid or unsafe counters are rejected', () => {
  assert.equal(sumTokens([{ todayTokens: null, totalTokens: null }, { todayTokens: 42, totalTokens: '42' }], 'totalTokens'), 42)
  for (const invalid of ['', '-1', 'NaN', '1.5', '9007199254740992']) {
    assert.equal(sumTokens([{ todayTokens: invalid, totalTokens: invalid }], 'todayTokens'), null)
  }
  assert.equal(usageShare(200, 100), null)
})

test('a small but nonzero usage is not displayed as zero', () => {
  assert.equal(percentLabel(usageShare(1, 100000)), '<0.1%')
  assert.equal(percentLabel(usageShare(42, 118)), '35.6%')
})

// Exercise real request code with the crypto API available on an HTTP origin.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const { webcrypto } = require('node:crypto')
const ts = require('typescript')

const source = fs.readFileSync(path.join(__dirname, '../src/api/allocation.ts'), 'utf8')
const js = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS },
}).outputText
const requests = []
const context = {
  exports: {},
  require: () => ({ API_BASE: '/api', AUTH_TOKEN_KEY: 'token' }),
  crypto: { getRandomValues: bytes => webcrypto.getRandomValues(bytes) },
  localStorage: { getItem: () => 'test-session' },
  fetch: async (url, init) => {
    requests.push({ url, ...init })
    return { ok: true, json: async () => ({ run_id: 'test-run' }) }
  },
}
vm.runInNewContext(js, context)

async function main() {
  assert.equal(context.crypto.randomUUID, undefined)
  await context.exports.modulePost('/ad-allocation/v1/runs', { period: '2026-09' })
  await context.exports.modulePost('/data-changes/batch/submit', {}, '"7"')
  assert.equal(requests.length, 2)
  const key = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/
  for (const request of requests) {
    assert.equal(request.method, 'POST')
    assert.equal(request.headers.Authorization, 'Bearer test-session')
    assert.match(request.headers['Idempotency-Key'], key)
  }
  assert.notEqual(requests[0].headers['Idempotency-Key'], requests[1].headers['Idempotency-Key'])
  assert.equal(requests[1].headers['If-Match'], '"7"')
  assert.equal(JSON.parse(requests[0].body).period, '2026-09')
  console.log('PASS: allocation and approval POST reach fetch without crypto.randomUUID')
}
main().catch(error => { console.error(error); process.exitCode = 1 })

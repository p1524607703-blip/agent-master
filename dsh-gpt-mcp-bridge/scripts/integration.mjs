import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'

const endpoint = process.argv[2] ?? 'http://127.0.0.1:3080/mcp'
const testPath = `.gpt-mcp-integration-${process.pid}.txt`
const client = new Client({ name: 'dsh-gpt-mcp-integration', version: '0.1.0' })
const transport = new StreamableHTTPClientTransport(new URL(endpoint))

function parsed(result) {
  const block = result.content?.find(item => item.type === 'text')
  if (block === undefined) throw new Error('tool returned no text result')
  const value = JSON.parse(block.text)
  if (result.isError) throw new Error(JSON.stringify(value))
  return value
}

async function call(name, args = {}) {
  return parsed(await client.callTool({ name, arguments: args }))
}

try {
  await client.connect(transport)
  const listed = await client.listTools()
  const info = await call('bridge_info')
  if (info.mode !== 'legacy') throw new Error('This direct-tool integration is legacy-only. Use npm test, smoke and relay-smoke for agent-loop mode; perform model execution separately with a bounded managed task.')
  if (listed.tools.length < 30) throw new Error(`expected at least 30 tools, got ${listed.tools.length}`)

  await call('fs_write', { path: testPath, content: 'full-access-ok' })
  const read = await call('fs_read', { path: testPath })
  if (read.content !== 'full-access-ok') throw new Error('filesystem round trip failed')

  const shell = await call('shell_exec', { command: 'printf shell-ok' })
  if (shell.exitCode !== 0 || shell.stdout !== 'shell-ok') throw new Error('shell execution failed')

  const started = await call('process_start', { command: 'printf process-ok' })
  await new Promise(resolve => setTimeout(resolve, 100))
  const processOutput = await call('process_read', { process_id: started.processId })
  if (!processOutput.chunks.some(chunk => chunk.text.includes('process-ok'))) throw new Error('managed process output failed')

  const git = await call('git_status')
  if (git.exitCode !== 0) throw new Error('git status failed')

  const sessions = await call('harness_list_sessions')
  if (!Array.isArray(sessions.items)) throw new Error('Harness session listing failed')

  const models = await call('harness_models')
  if (!Array.isArray(models.groups)) throw new Error('Harness model catalog failed')

  await call('fs_delete', { path: testPath })
  process.stdout.write(JSON.stringify({
    ok: true,
    endpoint,
    toolCount: listed.tools.length,
    checks: {
      filesystemWriteReadDelete: true,
      shell: true,
      managedProcess: true,
      git: true,
      harnessSessions: true,
      harnessModels: true,
    },
    visibleHarnessSessions: sessions.items.length,
    modelProviderGroups: models.groups.length,
  }, null, 2) + '\n')
} finally {
  try { await client.callTool({ name: 'fs_delete', arguments: { path: testPath, force: true } }) } catch {}
  await client.close()
}

import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js'

const endpoint = process.argv[2] ?? 'http://127.0.0.1:3080/mcp'
const client = new Client({ name: 'dsh-gpt-mcp-relay-smoke', version: '0.1.0' })
const transport = new StdioClientTransport({
  command: process.execPath,
  args: [new URL('./stdio-relay.mjs', import.meta.url).pathname, endpoint],
  stderr: 'pipe',
})

try {
  await client.connect(transport)
  const listed = await client.listTools()
  const info = await client.callTool({ name: 'bridge_info', arguments: {} })
  const names = listed.tools.map(tool => tool.name)
  if (!names.includes('agent_task_start') || !names.includes('harness_run') || info.isError) throw new Error('stdio relay verification failed')
  process.stdout.write(JSON.stringify({ ok: true, endpoint, toolCount: listed.tools.length }, null, 2) + '\n')
} finally {
  await client.close()
}

import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'

const endpoint = process.argv[2] ?? 'http://127.0.0.1:3080/mcp'
const client = new Client({ name: 'dsh-gpt-mcp-smoke', version: '0.1.0' })
const transport = new StreamableHTTPClientTransport(new URL(endpoint))

try {
  await client.connect(transport)
  const listed = await client.listTools()
  const info = await client.callTool({ name: 'bridge_info', arguments: {} })
  process.stdout.write(JSON.stringify({
    endpoint,
    toolCount: listed.tools.length,
    tools: listed.tools.map(tool => tool.name),
    info,
  }, null, 2) + '\n')
} finally {
  await client.close()
}

// Diagnostic MCP client; never an alternative DSH application launcher.
import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'
const [name, encoded = '{}', toolFilter] = process.argv.slice(2)
if (!name) throw new Error('Usage: node scripts/mcp-call.mjs TOOL JSON_ARGUMENTS [comma-separated-tool-schema-filter]')
const client = new Client({ name: 'dsh-bridge-diagnostic', version: '0.5.0' })
try {
  await client.connect(new StreamableHTTPClientTransport(new URL(process.env.DSH_GPT_MCP_URL ?? 'http://127.0.0.1:3080/mcp')))
  const response = await client.callTool({ name, arguments: JSON.parse(encoded) }, undefined, { timeout: 25000 })
  if (response.isError) process.exitCode = 1
  for (const block of response.content ?? []) {
    if (block.type !== 'text') continue
    const value = JSON.parse(block.text)
    if (toolFilter !== undefined) {
      const names = new Set(toolFilter.split(','))
      for (const item of value.modelRequests ?? value.task?.modelRequests ?? []) {
        if (item.request?.messages) {
          item.request.messages = item.request.messages.map(message => message.source?.form === 'catalog'
            ? { id: message.id, role: message.role, diagnosticOnly: 'Catalog omitted from diagnostic display; full request remains available through agent_model_request' }
            : message)
        }
        if (item.request?.tools) {
          item.allToolNames = item.request.tools.map(tool => tool.name)
          item.request.tools = item.request.tools.filter(tool => names.has(tool.name))
          item.displayFilteredTools = true
        }
      }
    }
    process.stdout.write(JSON.stringify(value, null, 2) + '\n')
  }
} finally { await client.close() }

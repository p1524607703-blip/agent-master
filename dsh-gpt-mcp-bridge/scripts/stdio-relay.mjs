import { Client } from '@modelcontextprotocol/sdk/client/index.js'
import { StreamableHTTPClientTransport } from '@modelcontextprotocol/sdk/client/streamableHttp.js'
import { Server } from '@modelcontextprotocol/sdk/server/index.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js'

const endpoint = process.argv[2] ?? process.env.DSH_GPT_MCP_URL ?? 'http://127.0.0.1:3080/mcp'
const upstream = new Client({ name: 'dsh-gpt-mcp-stdio-relay', version: '0.1.0' })
const upstreamTransport = new StreamableHTTPClientTransport(new URL(endpoint))
const server = new Server(
  { name: 'deepseek-harness-full-access', version: '0.1.0' },
  { capabilities: { tools: {} } },
)

server.setRequestHandler(ListToolsRequestSchema, request => upstream.listTools(request.params))
server.setRequestHandler(CallToolRequestSchema, request => upstream.callTool(request.params))

let closing = false
async function close() {
  if (closing) return
  closing = true
  await Promise.allSettled([server.close(), upstream.close()])
}

process.once('SIGINT', () => { void close().finally(() => process.exit(0)) })
process.once('SIGTERM', () => { void close().finally(() => process.exit(0)) })

try {
  await upstream.connect(upstreamTransport)
  await server.connect(new StdioServerTransport())
} catch (error) {
  process.stderr.write(`DeepSeek Harness MCP relay failed: ${error instanceof Error ? error.message : String(error)}\n`)
  await close()
  process.exitCode = 1
}

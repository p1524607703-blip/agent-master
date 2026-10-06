import type { Plugin } from "@opencode-ai/plugin"
import { appendFile, mkdir } from "node:fs/promises"
import { dirname } from "node:path"

const AGENTS = new Set(["amazon-intent-tagger", "amazon-intent-critic"])
const REQUIRED = /AMAZON_INTENT_RUN\s+run_id=([^\s]+)\s+schema_version=([^\s]+)\s+batch_id=([^\s]+)/
const GUARD = "Do not use ACOS, CVR, CTR, impressions, clicks, orders, sales, ROAS, conversion rate, or behavior_validated. Use only supplied search terms and allowed product fact IDs."
const AUDITED_EVENT_TYPES = new Set([
  "session.created",
  "session.error",
  "session.idle",
])

export const AmazonIntentGuard: Plugin = async () => ({
  "chat.params": async (input, output) => {
    if (!AGENTS.has(input.agent)) return
    output.temperature = 0
    output.topP = 0.1
    output.maxOutputTokens = input.agent === "amazon-intent-critic" ? 6000 : 32768
  },
  "chat.message": async (input, output) => {
    if (!input.agent || !AGENTS.has(input.agent)) return
    const text = output.parts
      .filter((part: any) => part?.type === "text")
      .map((part: any) => part.text || "")
      .join("\n")
    const match = text.match(REQUIRED)
    if (!match) throw new Error("amazon-intent-guard: missing run_id/schema_version/batch_id marker")
    const textPart = output.parts.find((part: any) => part?.type === "text") as any
    if (!textPart) throw new Error("amazon-intent-guard: no text part available for guard constraint")
    textPart.text = `${textPart.text}\n${GUARD}`
  },
  event: async ({ event }) => {
    const path = process.env.AMAZON_INTENT_EVENT_LOG
    if (!path) return
    const raw: any = event as any
    const type = raw?.type || "unknown"
    // Token deltas and message-part updates are high-volume content events.
    // The audit contract requires lifecycle metadata only, never prompt/output text.
    if (!AUDITED_EVENT_TYPES.has(type)) return
    const record = {
      ts: new Date().toISOString(),
      type,
      session_id: raw?.properties?.sessionID || raw?.properties?.session?.id || null,
      status: raw?.properties?.status || null,
      model: raw?.properties?.model?.id || raw?.properties?.modelID || null,
    }
    await mkdir(dirname(path), { recursive: true })
    await appendFile(path, JSON.stringify(record) + "\n", "utf8")
  },
})

export default AmazonIntentGuard

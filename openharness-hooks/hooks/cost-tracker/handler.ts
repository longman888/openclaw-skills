/**
 * cost-tracker Hook Handler
 * 在 agent_end 时写入结构化用量日志
 */

const LOG_FILE = "E:\\.openclaw\\data_bus\\cost-log.jsonl";

interface UsageRecord {
  timestamp: string;
  sessionKey: string;
  model: string;
  totalTokens: number;
  toolCalls: number;
  durationMs: number;
  estimatedCost?: number;
}

const handler = async (event: any) => {
  if (event.type !== "agent" || event.action !== "end") return;

  const ctx = event.context ?? {};
  const usage = ctx.usage ?? {};

  const record: UsageRecord = {
    timestamp: new Date().toISOString(),
    sessionKey: ctx.sessionKey ?? "unknown",
    model: ctx.model ?? "unknown",
    totalTokens: usage.total_tokens ?? 0,
    toolCalls: ctx.toolCalls ?? 0,
    durationMs: ctx.durationMs ?? 0,
    estimatedCost: usage.estimated_cost,
  };

  try {
    const line = JSON.stringify(record) + "\n";
    const fs = await import("fs");
    fs.appendFileSync(LOG_FILE, line, "utf8");
    console.log(`[cost-tracker] ${record.model} | ${record.totalTokens} tokens | $${record.estimatedCost ?? "?"}`);
  } catch (err) {
    console.error(`[cost-tracker] Failed to write log: ${err}`);
  }
};

export default handler;

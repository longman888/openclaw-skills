/**
 * subagent-notify Hook Handler
 * 将 subagent_ended 结果格式化为 XML TaskNotification，推送至父 session
 */

interface TaskNotification {
  taskId: string;
  status: "completed" | "failed" | "timeout" | "cancelled";
  summary: string;
  usage: {
    totalTokens: number;
    durationMs: number;
    model: string;
    toolCalls?: number;
  };
  parentSession: string;
  timestamp: string;
}

const MAX_SUMMARY_CHARS = 80;
const MAX_RESULT_CHARS = 4000;

const escapeXml = (str: string): string =>
  str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const truncate = (str: string, max: number): string =>
  str.length <= max ? str : str.slice(0, max - 3) + "...";

const generateSummary = (result: string): string => {
  const firstLine = result.split("\n").filter(l => l.trim())[0] ?? "";
  return truncate(firstLine, MAX_SUMMARY_CHARS);
};

const handler = async (event: any) => {
  if (event.type !== "agent" || event.action !== "subagent_ended") return;

  const ctx = event.context ?? {};
  const usage = ctx.usage ?? {};

  const notification: TaskNotification = {
    taskId: ctx.taskId ?? ctx.spawnId ?? "unknown",
    status: ctx.status ?? "failed",
    summary: generateSummary(ctx.result ?? ""),
    usage: {
      totalTokens: usage.total_tokens ?? 0,
      durationMs: usage.duration_ms ?? ctx.durationMs ?? 0,
      model: usage.model ?? ctx.model ?? "unknown",
      toolCalls: usage.tool_calls ?? ctx.toolCalls,
    },
    parentSession: ctx.parentSession ?? ctx.sessionKey ?? "unknown",
    timestamp: new Date().toISOString(),
  };

  const xml = `<task-notification>\n` +
    `  <task-id>${escapeXml(notification.taskId)}</task-id>\n` +
    `  <status>${notification.status}</status>\n` +
    `  <summary>${escapeXml(notification.summary)}</summary>\n` +
    `  <usage>\n` +
    `    <total-tokens>${notification.usage.totalTokens}</total-tokens>\n` +
    `    <duration-ms>${notification.usage.durationMs}</duration-ms>\n` +
    `    <model>${escapeXml(notification.usage.model)}</model>\n` +
    `  </usage>\n` +
    `  <parent-session>${escapeXml(notification.parentSession)}</parent-session>\n` +
    `  <timestamp>${notification.timestamp}</timestamp>\n` +
    `</task-notification>`;

  // 推送到父 session（event.messages 会路由到父 session）
  event.messages.push(xml);

  console.log(`[subagent-notify] ${notification.taskId} → ${notification.status} (${notification.usage.durationMs}ms)`);
};

export default handler;

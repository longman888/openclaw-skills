/**
 * dangerous-tool-audit Hook Handler
 * 拦截并记录危险工具调用（exec/write/delete）
 */

const DANGEROUS_PATTERNS = [
  /\brm\s+-rf\b/i,
  /\bformat\b/i,
  /\bfdisk\b/i,
  /\$\(/i,
  /\bdel\s+\/[a-z]/i,
  /\brm\s+\/[a-z]/i,
  /\bdel\s+\/[a-z]/i,
  /\bshutdown\b/i,
  /\breboot\b/i,
];

const AUDITED_TOOLS = ["exec", "write", "delete"];

const handler = async (event: any) => {
  // 只处理 tool:before_tool_call
  if (event.type !== "tool" || event.action !== "before_tool_call") return;

  const tool = event.context?.tool;
  const params = event.context?.params ?? {};
  const paramStr = JSON.stringify(params);

  if (!AUDITED_TOOLS.includes(tool)) return;

  // 检查危险命令模式
  for (const pattern of DANGEROUS_PATTERNS) {
    if (pattern.test(paramStr)) {
      console.warn(`[dangerous-tool-audit] BLOCKED: ${tool} — matched: ${pattern}`);
      return {
        block: true,
        blockReason: `危险命令被拦截 (pattern: ${pattern})`
      };
    }
  }

  // 正常审计日志
  console.log(`[dangerous-tool-audit] AUDIT: ${tool} — ${paramStr.slice(0, 200)}`);
};

export default handler;

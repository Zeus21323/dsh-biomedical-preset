/**
 * 生物医学模式 — 子智能体并发闸（preset 作用域）
 *
 * 为什么不是改 `@deepseek-ai/dsh-subagent` 的 `maxActiveSubagents`：
 * 那个上限属于 Host 平面的进程级池（`SubagentPool` 单例），改它对所有模式生效，
 * standard 也会被一起降到同一个数。真正按预设生效的挂点是 `tools/execute`
 * waterfall —— 工具调用在该 preset 的 scope 里经过这里，返回替换结果即可拒绝。
 *
 * 计数按 agent（会话）分桶：同一会话同时最多 `maxActive` 个子智能体，
 * 多个生物医学会话互不挤占。
 *
 * 为什么名单里没有 `spawn_teammate`：Agent Teams 的派活工具是 fire-and-return
 * （创建常驻成员后立刻返回），`tools/execute` 的包裹期覆盖不到成员的实际运行，
 * 计数会失真。所以 preset 的 prompt 里禁止用它派活（一律走 subagent），
 * 这条闸只管会阻塞到子代理完成的 `subagent` / `subagent_fork`。
 *
 * 局限：只拦"从工具入口发起"的派活。workflow 脚本内部的 agent() 扇出不走
 * tools/execute，那一路由 preset 里 `workflow-ptc.maxConcurrentAgents` 管。
 */

export const name = 'biomedical-subagent-cap'
export const inject = ['tools']

const DEFAULT_TOOLS = ['subagent', 'subagent_fork']
const CODE = 'ACTIVATION_LIMIT_REACHED'

function limitResult(limit, toolName) {
  const message =
    `subagent limit reached (active child limit: ${limit}) — this session already has ` +
    `${limit} running subagents started through "${toolName}". Wait for one to finish, ` +
    `or complete the work with the agents already running. Do not retry in a loop.`
  return {
    content: [{ type: 'text', text: `Error: ${message}` }],
    isError: true,
    error: { message, info: { name: 'SubagentCapError', code: CODE } },
  }
}

export function apply(ctx, config) {
  const limit = Number(config?.maxActive ?? 3)
  const guarded = new Set(config?.tools ?? DEFAULT_TOOLS)
  /** agentId -> 正在运行的受管子智能体数 */
  const active = new Map()

  ctx.on('tools/execute', async (exec, next) => {
    if (!guarded.has(exec.name)) return next()

    const key = String(exec.agent?.id ?? 'unknown-session')
    const running = active.get(key) ?? 0
    if (running >= limit) return limitResult(limit, exec.name)

    active.set(key, running + 1)
    try {
      return await next()
    } finally {
      const left = (active.get(key) ?? 1) - 1
      if (left <= 0) active.delete(key)
      else active.set(key, left)
    }
  })
}

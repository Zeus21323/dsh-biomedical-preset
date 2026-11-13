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
 * 嵌套：计数按调用方 agent 分桶，子智能体再派活会落进新的桶、绕过上限。
 * 所以 preset 里 subagent / subagent_fork 两行都设了 `maxDepth: 1`（只有主智能体能派活），
 * 这里再兜一层：调用方自己就是子智能体（delegationDepth ≥ 1）时直接拒绝。
 * 深度读法与 @deepseek-ai/dsh-subagent 的 delegationDepthOf 一致：
 * max(session.header.delegationDepth, options.subagentDepth)。
 *
 * 局限：只拦"从工具入口发起"的派活。workflow 脚本内部的 agent() 扇出不走
 * tools/execute，那一路由 preset 里 `workflow-ptc.maxConcurrentAgents` 管。
 * 「重计算最多 1 个」仍是 persona 约束：后台任务的并发上限属于全局的 dsh-jobs-local，
 * 不在预设作用域里。
 */

export const name = 'biomedical-subagent-cap'
export const inject = ['tools']

const DEFAULT_TOOLS = ['subagent', 'subagent_fork']
const CODE = 'ACTIVATION_LIMIT_REACHED'
const NESTED_CODE = 'NESTED_DELEGATION_DENIED'

/** 调用方的委派深度：0 = 主智能体，≥1 = 子智能体。读不到按 0 处理。 */
export function delegationDepth(agent) {
  const header = Number(agent?.session?.header?.delegationDepth ?? 0)
  const runtime = Number(agent?.options?.subagentDepth ?? 0)
  const depth = Math.max(Number.isFinite(header) ? header : 0, Number.isFinite(runtime) ? runtime : 0)
  return depth > 0 ? depth : 0
}

function nestedResult(toolName) {
  const message =
    `nested delegation denied — this agent is itself a subagent, so it is a leaf node and cannot call ` +
    `"${toolName}". Do the work directly with your own tools and report back to the parent.`
  return {
    content: [{ type: 'text', text: `Error: ${message}` }],
    isError: true,
    error: { message, info: { name: 'SubagentCapError', code: NESTED_CODE } },
  }
}

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
  const blockNested = config?.blockNested !== false
  /** agentId -> 正在运行的受管子智能体数 */
  const active = new Map()

  ctx.on('tools/execute', async (exec, next) => {
    if (!guarded.has(exec.name)) return next()
    if (blockNested && delegationDepth(exec.agent) >= 1) return nestedResult(exec.name)

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

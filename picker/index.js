/**
 * 生物医学技能选择器（Host half）
 *
 * 单一 skill provider：按 catalog.json 的 34 个功能分类提供 603 个技能。
 * 开关状态只来自 profile 的 biomedical-skills.json（由设置页写入）与会话级覆盖，
 * 本插件刻意不声明 Config —— 这样它只依赖 node 内置模块，不会因为跨包解析
 * （schemastery 等）失败而拖垮整个预设的挂载。
 */
import { readFile, readdir } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { resolveProfileDir } from '../shared/profile.mjs';
import { frontmatter } from '../shared/frontmatter.mjs';

export const name = 'biomedical-skill-picker';
export const inject = ['skills'];

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILLS_ROOT = join(HERE, '..', 'skills');
const CATALOG_PATH = join(HERE, 'catalog.json');

/**
 * 进程级共享区。
 *
 * 为什么需要它：patch 里 13 个预设（1 个全量 + 12 个专项）各声明了一份 picker 行，
 * agent-preset-registry 在**注册时**就把每个预设挂载进独立 scope，所以同一进程里
 * 会有 13 个 picker 实例。而 Host 的 webServer 对同一 (kind, path) 只允许注册一次
 * ——第二个实例 register 会抛 `webserver: duplicate exact route`，异常从 apply 里冒出，
 * 那一行就被 auditRows 记为 failed，**整个预设挂载被拒**（卡片显示「加载失败」）。
 *
 * 因此路由与会话覆盖状态都提到进程级：谁先到谁注册，后来者只加引用计数；
 * 卸载时按引用计数收尾，不会出现「一个实例关掉把别人的路由带走」。
 *
 * 用 Symbol.for 挂在 globalThis 上，是为了在模块被以不同 specifier 加载两次时仍共享同一份。
 */
const SHARED_KEY = Symbol.for('dsh.biomedical.picker.v1');
const SHARED = (globalThis[SHARED_KEY] ??= {
  /** sessionId → 该会话启用的分类 id 集合 */
  overrides: new Map(),
  /** 活着的 picker 实例：token → { preset?: string, only?: Set<string> } */
  instances: new Map(),
  /** 路由引用计数 */
  routeRefs: 0,
  /** 因为已被别的实例注册而跳过的次数（诊断用：等于被修掉的重复注册数） */
  routeCollisions: 0,
  /** 路由注册失败（非重复导致的真实错误）的文本，诊断用 */
  routeError: undefined,
  /** agentPresets 服务引用：用来读每个预设的挂载诊断（broken） */
  presetsSvc: undefined,
  /** agents 服务引用：用来按 sessionId 找到会话，判断它属于哪个预设 */
  agentsSvc: undefined,
  /** 缓存：哪些预设声明了本插件（即「生物医学模式」） */
  biomedIds: undefined,
  /** 最近的 applies 判定（诊断用：能看到每个会话被判成什么预设） */
  appliesLog: [],
  disposeRoutes: undefined,
});

/**
 * profile 目录：apply() 里优先用插件上下文的 profileContext 定位一次并缓存到共享区，
 * 读不到再退回环境变量与 $DSH_HOME/profiles/<name>。不写死任何一台机器的路径。
 */
function profileDir() {
  if (!SHARED.profileDir) SHARED.profileDir = resolveProfileDir();
  return SHARED.profileDir;
}

/** 兜底：catalog 损坏/缺失时直接扫 skills/<domain>/<skill>/SKILL.md，保证技能可用。 */
async function scanAll() {
  const out = [];
  let domains;
  try {
    domains = await readdir(SKILLS_ROOT, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const domain of domains) {
    if (!domain.isDirectory()) continue;
    const domainPath = join(SKILLS_ROOT, domain.name);
    let entries;
    try {
      entries = await readdir(domainPath, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (!entry.isDirectory()) continue;
      const directory = join(domainPath, entry.name);
      const file = join(directory, 'SKILL.md');
      let text;
      try {
        text = await readFile(file, 'utf8');
      } catch {
        continue;
      }
      const { fm } = frontmatter(text);
      if (!fm.name) continue;
      out.push({
        name: fm.name,
        description: fm.description ?? '',
        ...(fm.whenToUse ? { whenToUse: fm.whenToUse } : {}),
        invocation: { modelInvocable: true, userInvocable: true },
        provider: 'biomedical-picker',
        source: 'custom',
        rank: 0,
        locator: { path: file, directory },
        resourceBase: { kind: 'directory', path: directory },
        path: file,
        metadata: { category: 'fallback', categoryLabel: domain.name },
      });
    }
  }
  return out;
}

/** catalog 只读一份（同一个包内 13 个实例读的是同一个文件）。失败不缓存。 */
let catalogCache;
async function loadCatalog() {
  if (catalogCache !== undefined) return catalogCache;
  try {
    catalogCache = JSON.parse(await readFile(CATALOG_PATH, 'utf8'));
  } catch {
    return undefined; // 文件修好后下次即可恢复
  }
  return catalogCache;
}

/**
 * skill_scope：给模型用的工具，让 agent 理解任务后自己把技能目录收窄到相关分类。
 * 写的是和浮窗同一份会话覆盖（SHARED.overrides），下一步 skills.snapshot() 就按新范围出目录。
 * 注意 DSH 每次目录变化都会追加一份完整的新目录，所以只在开工时调一次。
 */
function buildScopeTool(categories, currentEnabled) {
  const ids = new Set(categories.map((c) => c.id));
  const labelOf = new Map(categories.map((c) => [c.id, c.label_zh]));
  const listedOf = new Map(categories.map((c) => [c.id, c.skills.filter((e) => !e.via).length]));
  const catalogText = categories.map((c) => `${c.id}（${c.label_zh}）`).join('；');
  const render = (_args, value) => [{ type: 'text', text: value.text }];
  return {
    name: 'skill_scope',
    description:
      '收窄（或恢复）本会话的生物医学技能目录。理解任务后、加载技能之前调用一次：只保留与任务相关的 2–4 个分类，' +
      '目录会从下一步起只列这些分类的技能，近义技能更少、更容易选对。拿不准任务范围时不要调用；不要反复调用（每次变化都会追加一份新目录）。' +
      'add 为 true 时在当前范围上追加分类（专项模式里加开别的领域用这个），否则用给出的分类替换当前范围。' +
      'reset 为 true 时恢复为当前模式的默认范围。可用分类：' +
      catalogText,
    parameters: {
      type: 'object',
      additionalProperties: false,
      properties: {
        categories: {
          type: 'array',
          items: { type: 'string', enum: [...ids] },
          description: '要保留的分类 id（1–8 个）。',
        },
        add: { type: 'boolean', description: '为 true 时追加到当前范围，而不是替换。' },
        reset: { type: 'boolean', description: '为 true 时清除本会话的范围设置，恢复模式默认。' },
      },
    },
    output: {
      schema: {
        type: 'object',
        additionalProperties: false,
        required: ['text'],
        properties: {
          text: { type: 'string' },
          enabled: { type: 'array', items: { type: 'string' } },
          skills: { type: 'number' },
        },
      },
      render,
    },
    async execute(args, exec) {
      const sid = exec?.agent?.id;
      if (!sid) throw new Error('skill_scope: 拿不到当前会话，无法设置技能范围');
      if (args?.reset === true) {
        SHARED.overrides.delete(String(sid));
        invalidateAll();
        return { text: '已恢复本模式的默认技能范围，下一步生效。' };
      }
      const wanted = Array.isArray(args?.categories) ? [...new Set(args.categories.map(String))] : [];
      if (wanted.length === 0) throw new Error('skill_scope: 至少给一个分类 id，或传 reset: true');
      if (wanted.length > 8) throw new Error('skill_scope: 一次最多保留 8 个分类；范围这么宽就不必收窄');
      const unknown = wanted.filter((id) => !ids.has(id));
      if (unknown.length) throw new Error(`skill_scope: 未知分类 ${unknown.join(', ')}`);
      const finalSet = new Set(wanted);
      if (args?.add === true) for (const id of await currentEnabled(String(sid))) finalSet.add(id);
      SHARED.overrides.set(String(sid), finalSet);
      invalidateAll();
      const enabled = [...finalSet];
      const skills = enabled.reduce((a, id) => a + (listedOf.get(id) ?? 0), 0);
      return {
        text:
          `已把本会话的技能范围设为 ${enabled.length} 类（${enabled.map((id) => labelOf.get(id)).join('、')}），约 ${skills} 个技能，下一步生效。` +
          '缺技能时用 add: true 再加开；reset: true 恢复默认。',
        enabled,
        skills,
      };
    },
  };
}

function invalidateAll() {
  for (const inst of SHARED.instances.values()) {
    try {
      inst.control?.invalidate?.();
    } catch {
      /* 单个实例失效不影响其它实例 */
    }
  }
}

function findEntry(doc, name) {
  for (const category of doc.categories) {
    const entry = category.skills.find((e) => e.name === name);
    if (entry) return entry;
  }
  return undefined;
}

function hasFolded(doc, router) {
  return doc.categories.some((c) => c.skills.some((e) => e.via === router));
}

/** 技能声明的 MCP 工具：SKILL.md frontmatter 的 `mcp:` 优先，其次 catalog 条目的 `mcp` 数组。 */
function declaredMcpTools(fm, entry) {
  const raw = fm?.mcp;
  if (raw) {
    return String(raw)
      .replace(/^\[|\]$/g, '')
      .split(',')
      .map((t) => t.trim().replace(/^["']|["']$/g, '').replace(/^mcp__biomedical__/, ''))
      .filter(Boolean);
  }
  return Array.isArray(entry?.mcp) ? entry.mcp.map(String) : [];
}

/**
 * 入口技能（如 nfcore-catalog）加载时附上的流程索引：只列当前范围内的折叠技能，
 * 给出 SKILL.md 绝对路径。折叠技能不在目录里，skill 工具按名字加载不到，
 * 所以让模型用文件工具直接读。
 */
function renderFoldedIndex(doc, router, enabled) {
  const lines = [
    '---',
    '',
    '## 本地可用的流程技能索引（按当前技能范围生成）',
    '',
    '下列流程技能没有单独列在技能目录里，**不能**用 skill 工具按名字加载。确定要用哪个之后，用文件读取工具打开它的 SKILL.md 并按其中说明执行；同目录下的 references/ 与 scripts/ 是它的资源。',
    '',
  ];
  let count = 0;
  for (const category of doc.categories) {
    if (!enabled.has(category.id)) continue;
    const folded = category.skills.filter((e) => e.via === router);
    if (folded.length === 0) continue;
    lines.push(`### ${category.label_zh}`);
    for (const e of folded) {
      lines.push(`- \`${e.name}\`：${e.desc ?? ''} —— ${join(SKILLS_ROOT, e.path, 'SKILL.md')}`);
      count += 1;
    }
    lines.push('');
  }
  if (count === 0) {
    lines.push('当前技能范围里没有可用的流程技能。需要时先用 `skill_scope` 加开对应分类，再重新加载本技能。');
  }
  return lines.join('\n');
}

async function switches() {
  const dir = profileDir();
  if (!dir) return {};
  try {
    return JSON.parse(await readFile(join(dir, 'biomedical-skills.json'), 'utf8'));
  } catch {
    return {};
  }
}

/**
 * 进程里所有活着的实例合起来能确定的「默认白名单」。
 *
 * - 只有一个专项实例 → 就是它（最精确的常见情况：只开了一个专项模式的会话）。
 * - 全是专项实例但不止一个 → 取并集（无法从请求判定会话属于哪个模式，宁可多列）。
 * - 只要存在一个全量实例 → undefined，表示「按 profile 开关文件」。
 */
function resolvePresetOnly() {
  const all = [...SHARED.instances.values()];
  if (all.length === 0) return undefined;
  const special = all.filter((i) => i.only instanceof Set);
  if (special.length === 0) return undefined;
  if (special.length < all.length) return undefined;
  if (special.length === 1) return special[0].only;
  const union = new Set();
  for (const inst of special) for (const id of inst.only) union.add(id);
  return union;
}

/**
 * 某个会话所属预设的白名单。
 *
 * 不能只看进程里活着哪些实例：全量预设永远在，进程级推断就永远落到「按 profile 开关」，
 * 专项模式的浮窗会把全量模式的开关当成当前状态，用户一勾选就把专项撑回近乎全量。
 * 所以先按会话找到它实际组合的预设 id，再取该预设那份 picker 的 only（全量模式为
 * undefined，即按 profile 开关）。判定不了（会话还没起 agent 等）才退回进程级推断。
 *
 * @returns {Promise<{ only: Set<string> | undefined, presetId: string | undefined }>}
 */
async function presetOnlyFor(sid) {
  if (sid) {
    let verdict;
    try {
      verdict = await resolveApplies(sid);
    } catch {
      verdict = undefined;
    }
    const presetId = verdict?.presetId;
    if (presetId) {
      for (const inst of SHARED.instances.values()) {
        if (inst.preset === presetId) return { only: inst.only, presetId };
      }
    }
  }
  return { only: resolvePresetOnly(), presetId: undefined };
}

function sendJson(response, status, body) {
  try {
    response.writeHead(status, { 'content-type': 'application/json; charset=utf-8' });
    response.end(JSON.stringify(body));
  } catch {
    /* 连接已断，忽略 */
  }
}

async function readJsonBody(request) {
  const chunks = [];
  let bytes = 0;
  for await (const chunk of request) {
    bytes += chunk.length;
    if (bytes > 64 * 1024) throw new Error('body too large');
    chunks.push(chunk);
  }
  if (chunks.length === 0) return {};
  return JSON.parse(Buffer.concat(chunks).toString('utf8'));
}

// ═══════════════════════════════════════════════════════════════════════════
// 路由：进程级只注册一次，处理器读 SHARED（不闭包任何单个实例）。
// ═══════════════════════════════════════════════════════════════════════════
async function handleGet(request, response, logger) {
  if (request.method !== 'GET') {
    response.writeHead(405, { allow: 'GET' });
    response.end();
    return;
  }
  const url = new URL(request.url ?? '/', 'http://127.0.0.1');
  const sid = String(url.searchParams.get('sessionId') ?? '').trim();
  const doc = await loadCatalog().catch((e) => {
    logger?.warn?.(`biomedical-picker: catalog load failed: ${e?.message ?? e}`);
    return undefined;
  });
  const active = sid ? SHARED.overrides.get(sid) : undefined;
  const profileSwitches = await switches();
  const allIds = (doc?.categories ?? []).map((c) => c.id);
  const { only: presetOnly, presetId } = await presetOnlyFor(sid);
  // 本会话此刻真正生效的分类：会话覆盖 > 预设白名单 > profile 开关文件。
  // 前端不该自己猜这个优先级，所以这里直接算好回给 UI。
  const effective = active
    ? [...active]
    : presetOnly
      ? [...presetOnly]
      : allIds.filter((id) => profileSwitches[id] !== false);
  sendJson(response, 200, {
    ok: true,
    sessionId: sid,
    categories: (doc?.categories ?? []).map((c) => ({
      id: c.id,
      label: c.label_zh,
      /** 目录里列出的技能数；折叠技能（经入口技能加载）单独计 folded，不占目录 token */
      count: c.skills.filter((e) => !e.via).length,
      folded: c.skills.filter((e) => e.via).length,
    })),
    enabled: active ? [...active] : null,
    effective,
    source: active ? 'session' : presetOnly ? 'preset' : 'profile',
    presetOnly: presetOnly ? [...presetOnly] : null,
    /** 本会话实际组合的预设 id；null 表示判定不了，presetOnly 来自进程级推断 */
    presetId: presetId ?? null,
    /** 诊断：本进程里挂了几份 picker（13 个预设 = 13）以及被跳过的重复注册次数 */
    instances: SHARED.instances.size,
    routeCollisions: SHARED.routeCollisions,
  });
}

/**
 * 哪些预设算「生物医学模式」？
 *
 * 不硬编码那 13 个 id：直接读每个预设声明的子插件列表（readDocument 的 content 是
 * 声明原文 YAML），看它有没有 `dsh-biomedical-preset/picker`。这样以后加/改预设、
 * 甚至换 id，判断都自动跟着走。结果缓存 60 秒（预设是启动时注册的，几乎不变）。
 */
async function biomedicalPresetIds() {
  const svc = SHARED.presetsSvc;
  if (!svc || typeof svc.list !== 'function' || typeof svc.readDocument !== 'function') return undefined;
  const cached = SHARED.biomedIds;
  if (cached && Date.now() - cached.at < 60_000) return cached.ids;
  let rows;
  try {
    rows = await svc.list();
  } catch {
    return undefined;
  }
  const ids = new Set();
  for (const row of Array.isArray(rows) ? rows : []) {
    if (!row?.id) continue;
    try {
      const doc = await svc.readDocument(row.id);
      if (String(doc?.content ?? '').includes('dsh-biomedical-preset/picker')) ids.add(row.id);
    } catch {
      /* 读不到这个预设的声明就当它不是 */
    }
  }
  SHARED.biomedIds = { at: Date.now(), ids };
  return ids;
}

/**
 * 这个会话是否在生物医学模式下。
 * @returns {{ applies: boolean|undefined, presetId: string|undefined, reason?: string }}
 *   applies=false 表示确定不是；undefined 表示判断不了（前端按「不显示」处理）
 */
async function resolveApplies(sessionId) {
  if (!sessionId) return { applies: undefined, presetId: undefined, reason: 'sessionId required' };
  const presets = SHARED.presetsSvc;
  const agents = SHARED.agentsSvc;
  if (!presets || typeof presets.composedPreset !== 'function') {
    return { applies: undefined, presetId: undefined, reason: 'agentPresets unavailable' };
  }
  if (!agents || typeof agents.get !== 'function') {
    return { applies: undefined, presetId: undefined, reason: 'agents unavailable' };
  }
  const ids = await biomedicalPresetIds();
  if (!ids) return { applies: undefined, presetId: undefined, reason: 'preset declarations unreadable' };
  const agent = agents.get(sessionId);
  if (!agent || !agent.ctx) return { applies: undefined, presetId: undefined, reason: 'session has no live agent' };
  let presetId;
  try {
    presetId = presets.composedPreset(agent.ctx);
  } catch (e) {
    return { applies: undefined, presetId: undefined, reason: `composedPreset failed: ${e?.message ?? e}` };
  }
  if (presetId === undefined) return { applies: false, presetId: undefined, reason: 'no preset bound' };
  return { applies: ids.has(presetId), presetId };
}

/** 面板入口的显示判定：只有生物医学模式的会话才露按键。 */
async function handleApplies(request, response, logger) {
  if (request.method !== 'GET') {
    response.writeHead(405, { allow: 'GET' });
    response.end();
    return;
  }
  const url = new URL(request.url ?? '/', 'http://127.0.0.1');
  const sid = String(url.searchParams.get('sessionId') ?? '').trim();
  let verdict;
  try {
    verdict = await resolveApplies(sid);
  } catch (e) {
    logger?.warn?.(`biomedical-picker: resolveApplies failed: ${e?.message ?? e}`);
    verdict = { applies: undefined, presetId: undefined, reason: String(e?.message ?? e) };
  }
  sendJson(response, 200, {
    ok: true,
    sessionId: sid,
    applies: verdict.applies === undefined ? null : verdict.applies,
    presetId: verdict.presetId ?? null,
    reason: verdict.reason ?? null,
  });
  // 留痕：每个会话的判定都记一条（最近 30 条），/bio-skills/presets 里可查
  try {
    SHARED.appliesLog.push({
      at: Date.now(),
      sessionId: sid,
      presetId: verdict.presetId ?? null,
      applies: verdict.applies === undefined ? null : verdict.applies,
      reason: verdict.reason ?? null,
    });
    if (SHARED.appliesLog.length > 30) SHARED.appliesLog.splice(0, SHARED.appliesLog.length - 30);
  } catch {
    /* 诊断留痕失败不影响返回 */
  }
}

/** 诊断用：把每个预设的挂载诊断（broken）原样透出来。 */
async function handlePresets(request, response) {
  if (request.method !== 'GET') {
    response.writeHead(405, { allow: 'GET' });
    response.end();
    return;
  }
  const svc = SHARED.presetsSvc;
  if (!svc || typeof svc.list !== 'function') {
    sendJson(response, 200, { ok: false, reason: 'agentPresets service unavailable' });
    return;
  }
  let rows;
  try {
    rows = await svc.list();
  } catch (e) {
    sendJson(response, 200, { ok: false, reason: String(e?.message ?? e) });
    return;
  }
  sendJson(response, 200, {
    ok: true,
    instances: SHARED.instances.size,
    routeCollisions: SHARED.routeCollisions,
    routeError: SHARED.routeError ?? null,
    appliesLog: SHARED.appliesLog.slice(-30),
    presets: (Array.isArray(rows) ? rows : []).map((r) => ({
      id: r?.id,
      name: r?.name,
      order: r?.order,
      broken: r?.broken ?? null,
    })),
  });
}

async function handleSet(request, response, logger) {
  if (request.method !== 'POST') {
    response.writeHead(405, { allow: 'POST' });
    response.end();
    return;
  }
  let body;
  try {
    body = await readJsonBody(request);
  } catch (e) {
    sendJson(response, 400, { ok: false, error: String(e?.message ?? e) });
    return;
  }
  const sid = String(body?.sessionId ?? '').trim();
  if (!sid) {
    sendJson(response, 400, { ok: false, error: 'sessionId required' });
    return;
  }
  const enabled = Array.isArray(body?.enabled) ? body.enabled.map(String) : null;
  if (enabled === null) {
    SHARED.overrides.delete(sid);
  } else {
    SHARED.overrides.set(sid, new Set(enabled));
  }
  // 让所有实例的目录缓存失效：覆盖是按会话生效的，不能只刷新注册了路由的那个实例。
  for (const inst of SHARED.instances.values()) {
    try {
      inst.control?.invalidate?.();
    } catch (e) {
      logger?.warn?.(`biomedical-picker: invalidate failed: ${e?.message ?? e}`);
    }
  }
  sendJson(response, 200, {
    ok: true,
    sessionId: sid,
    enabled: enabled ? [...enabled] : null,
  });
}

export function apply(ctx, config = {}) {
  /**
   * 白名单：专项 preset 只列自己要的分类（config.only），不写 34 个布尔值。
   * 给了 only 就完全按 only 走，忽略 profile 级开关文件；否则退回「34 个布尔 + 文件覆盖」
   * 的全量行为，这样全量 preset 仍然可以在设置页自由开关。
   */
  const only = Array.isArray(config?.only) && config.only.length > 0 ? new Set(config.only) : undefined;
  /** 所属预设 id（patch 里写在 picker 行的 config.preset），浮窗按会话找白名单要用 */
  const preset = typeof config?.preset === 'string' && config.preset ? config.preset : undefined;

  if (!SHARED.profileDir) SHARED.profileDir = resolveProfileDir(ctx);

  // ── 实例登记（与路由无关：webServer 不可用时实例照样登记，诊断才准）
  const token = {};
  const instance = { preset, only, control: undefined };
  SHARED.instances.set(token, instance);
  ctx.effect(
    () => () => {
      SHARED.instances.delete(token);
    },
    'biomedical-picker: instance',
  );

  /**
   * 可选服务必须用 ctx.inject 等待就绪，不能用 ctx.get：
   * 冷启动时 apply() 可能早于 webServer / agents 注册，get 会拿到 undefined，
   * 路由就永远注册不上（实测：热加载 available、冷启动 UNAVAILABLE）。
   */
  let agentsSvc;
  ctx.inject(['agents'], (scoped) => {
    agentsSvc = scoped.agents;
    SHARED.agentsSvc = scoped.agents;
    return () => {
      agentsSvc = undefined;
      if (SHARED.agentsSvc === scoped.agents) SHARED.agentsSvc = undefined;
    };
  });

  // 预设挂载诊断：读 agentPresets.list() 的 broken；进程内共享，谁活谁提供。
  ctx.inject(['agentPresets'], (scoped) => {
    SHARED.presetsSvc = scoped.agentPresets;
    return () => {
      if (SHARED.presetsSvc === scoped.agentPresets) SHARED.presetsSvc = undefined;
    };
  });

  // ── skill_scope 工具：可选服务，注册失败只记日志，不影响预设挂载
  ctx.inject(['tools'], (scoped) => {
    let doc;
    try {
      doc = JSON.parse(readFileSync(CATALOG_PATH, 'utf8'));
    } catch (e) {
      ctx.logger?.warn?.(`biomedical-picker: catalog unreadable, skill_scope not registered: ${e?.message ?? e}`);
      return undefined;
    }
    try {
      // 追加模式要知道「当前范围」：会话覆盖 > 本预设白名单 > profile 开关
      const currentEnabled = async (sid) => {
        const override = SHARED.overrides.get(sid);
        if (override) return [...override];
        if (only) return [...only];
        const sw = await switches();
        return doc.categories.map((c) => c.id).filter((id) => sw[id] !== false);
      };
      const undo = scoped.tools.register(buildScopeTool(doc.categories, currentEnabled));
      return typeof undo === 'function' ? undo : undefined;
    } catch (e) {
      ctx.logger?.warn?.(`biomedical-picker: skill_scope register failed: ${e?.message ?? e}`);
      return undefined;
    }
  });

  // ── 路由：引用计数 + 绝不把注册错误抛进 apply（那会让整份预设挂载失败）
  ctx.inject(['webServer'], (scoped) => {
    SHARED.routeRefs += 1;
    if (SHARED.routeRefs === 1) {
      const disposers = [];
      try {
        disposers.push(
          scoped.webServer.register(
            {
              kind: 'exact',
              path: '/bio-skills/get',
              handler: (request, response) => handleGet(request, response, ctx.logger),
            },
            'biomedical-picker: session-skills/get',
          ),
        );
        disposers.push(
          scoped.webServer.register(
            {
              kind: 'exact',
              path: '/bio-skills/set',
              handler: (request, response) => handleSet(request, response, ctx.logger),
            },
            'biomedical-picker: session-skills/set',
          ),
        );
        disposers.push(
          scoped.webServer.register(
            {
              kind: 'exact',
              path: '/bio-skills/presets',
              handler: (request, response) => handlePresets(request, response),
            },
            'biomedical-picker: presets-diagnostic',
          ),
        );
        disposers.push(
          scoped.webServer.register(
            {
              kind: 'exact',
              path: '/bio-skills/applies',
              handler: (request, response) => handleApplies(request, response, ctx.logger),
            },
            'biomedical-picker: applies',
          ),
        );
        SHARED.disposeRoutes = () => {
          for (const dispose of disposers) {
            try {
              dispose();
            } catch {
              /* 已经卸掉，忽略 */
            }
          }
        };
        ctx.logger?.info?.('biomedical-picker: session-skills routes registered');
      } catch (e) {
        // 走到这里说明路径被别的插件占了：记下来，但绝不让它毁掉预设挂载。
        SHARED.routeCollisions += 1;
        SHARED.routeError = String(e?.message ?? e);
        ctx.logger?.warn?.(`biomedical-picker: 路由注册失败（不影响技能）：${SHARED.routeError}`);
        for (const dispose of disposers) {
          try {
            dispose();
          } catch {
            /* 忽略 */
          }
        }
        SHARED.disposeRoutes = undefined;
      }
    } else {
      // 已经有实例注册过了（13 个预设各一份 picker），直接复用。
      SHARED.routeCollisions += 1;
      ctx.logger?.info?.(
        `biomedical-picker: 复用已注册的路由（第 ${SHARED.routeRefs} 个实例，共 ${SHARED.instances.size}）`,
      );
    }

    return () => {
      SHARED.routeRefs = Math.max(0, SHARED.routeRefs - 1);
      if (SHARED.routeRefs === 0 && SHARED.disposeRoutes) {
        SHARED.disposeRoutes();
        SHARED.disposeRoutes = undefined;
      }
    };
  });

  /** 当前会话此刻生效的分类（会话覆盖 > 预设白名单 > profile 开关）。list() 与 get() 共用。 */
  async function enabledCategoryIds(doc) {
    const { only: _only, preset: _preset, ...defaults } = config ?? {};
    const effective = { ...defaults, ...(await switches()) };
    let sessionSet;
    let currentSid;
    try {
      const sid = agentsSvc?.currentInitiator?.()?.id;
      currentSid = sid;
      if (sid) sessionSet = SHARED.overrides.get(sid);
    } catch (e) {
      ctx.logger?.warn?.(`biomedical-picker: currentInitiator failed: ${e?.message ?? e}`);
    }
    if (SHARED.overrides.size > 0) {
      ctx.logger?.info?.(
        `biomedical-picker: list() sid=${currentSid ?? 'undefined'} overrides=${SHARED.overrides.size} hit=${Boolean(sessionSet)}`,
      );
    }
    const ids = new Set();
    for (const category of doc.categories) {
      const on = sessionSet ? sessionSet.has(category.id) : only ? only.has(category.id) : effective[category.id] !== false;
      if (on) ids.add(category.id);
    }
    return ids;
  }

  async function readCandidate(entry, category) {
    const directory = join(SKILLS_ROOT, entry.path);
    const file = join(directory, 'SKILL.md');
    let text;
    try {
      text = await readFile(file, 'utf8');
    } catch {
      return undefined;
    }
    const { fm } = frontmatter(text);
    if (!fm.name) return undefined;
    return {
      name: fm.name,
      description: fm.description ?? '',
      ...(fm.whenToUse ? { whenToUse: fm.whenToUse } : {}),
      invocation: { modelInvocable: true, userInvocable: true },
      provider: 'biomedical-picker',
      source: 'custom',
      rank: 0,
      locator: { path: file, directory },
      resourceBase: { kind: 'directory', path: directory },
      path: file,
      metadata: { category: category.id, categoryLabel: category.label_zh },
    };
  }

  const dispose = ctx.skills.registerProvider((control) => {
    instance.control = control;
    return {
      name: 'biomedical-picker',

      async list() {
        const doc = await loadCatalog();
        if (!doc || !Array.isArray(doc.categories) || doc.categories.length === 0) {
          ctx.logger?.warn?.('biomedical-picker: catalog empty, falling back to full directory scan');
          return scanAll();
        }
        const enabled = await enabledCategoryIds(doc);
        // 用户（浮窗「全部关闭」或设置页全关）主动选了 0 类：就是不加载本包技能。
        // 以前这里也退回全量扫描，结果「全部关闭」反而加载了全部技能、目录成本最高。
        if (enabled.size === 0) {
          ctx.logger?.info?.('biomedical-picker: 0 categories enabled, providing no bundled skills');
          return [];
        }

        const out = [];
        const listed = new Set();
        /** 折叠技能（catalog 里带 via 的，如 152 个 nfcore-* 流程）不进目录，只记下需要露出的入口技能 */
        const routers = new Set();
        for (const category of doc.categories) {
          if (!enabled.has(category.id)) continue;
          for (const entry of category.skills) {
            if (entry.via) {
              routers.add(entry.via);
              continue;
            }
            const candidate = await readCandidate(entry, category);
            if (!candidate) continue;
            out.push(candidate);
            listed.add(candidate.name);
          }
        }
        // 入口技能可能属于没开启的分类（nfcore-catalog 在「计算流程与可复现性」）：
        // 只要范围内有被它折叠的流程，就把它放进目录。
        for (const router of routers) {
          if (listed.has(router)) continue;
          for (const category of doc.categories) {
            const entry = category.skills.find((e) => e.name === router);
            if (!entry) continue;
            const candidate = await readCandidate(entry, category);
            if (candidate) {
              out.push(candidate);
              listed.add(router);
            }
            break;
          }
        }
        // 选了分类却一个文件都读不到：说明 skills/ 目录坏了，才退回全量扫描兜底。
        if (out.length === 0) {
          ctx.logger?.warn?.('biomedical-picker: enabled categories are unreadable, falling back to full scan');
          return scanAll();
        }
        return out;
      },

      async get(candidate) {
        const text = await readFile(candidate.locator.path, 'utf8');
        const { fm, body } = frontmatter(text);
        const doc = await loadCatalog();
        const entry = doc ? findEntry(doc, candidate.name) : undefined;
        const parts = [];
        const tools = declaredMcpTools(fm, entry);
        if (tools.length > 0) {
          parts.push(
            `> 本技能常用的 MCP 数据工具：${tools.map((t) => `\`mcp__biomedical__${t}\``).join('、')}。需要查库时优先用它们；当前模式没有提供的工具不要硬调。`,
            '',
          );
        }
        parts.push(body);
        if (doc && hasFolded(doc, candidate.name)) {
          let enabled;
          try {
            enabled = await enabledCategoryIds(doc);
          } catch {
            enabled = new Set(doc.categories.map((c) => c.id));
          }
          parts.push('', renderFoldedIndex(doc, candidate.name, enabled));
        }
        return { ...candidate, content: parts.join('\n') };
      },
    };
  });

  ctx.effect(() => dispose, 'biomedical-skill-picker: provider');
}

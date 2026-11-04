/**
 * 生物医学技能选择器（Host half）
 *
 * 单一 skill provider：按 catalog.json 的 34 个功能分类提供 603 个技能。
 * 开关状态只来自 profile 的 biomedical-skills.json（由 dsh-biomedical-skill-settings
 * 的设置页写入），本插件刻意不声明 Config —— 这样它只依赖 node 内置模块，
 * 不会因为跨包解析（schemastery 等）失败而拖垮整个预设的挂载。
 */
import { readFile, readdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export const name = 'biomedical-skill-picker';
export const inject = ['skills'];

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILLS_ROOT = join(HERE, '..', 'skills');
const CATALOG_PATH = join(HERE, 'catalog.json');

/** Host 进程不总是导出 DSH_PROFILE_DIR；用存在性探测兜底。 */
function profileDir() {
  const candidates = [process.env.DSH_PROFILE_DIR, 'C:/Users/20735/.dsh/profiles/desktop'];
  for (const dir of candidates) {
    if (dir && existsSync(join(dir, 'package.json'))) return dir;
  }
  return undefined;
}

function frontmatter(text) {
  const m = /^---\r?\n([\s\S]*?)\r?\n---/.exec(text);
  if (!m) return { fm: {}, body: text };
  const fm = {};
  let key = null;
  for (const line of m[1].split(/\r?\n/)) {
    const kv = /^([A-Za-z0-9_-]+):\s*(.*)$/.exec(line);
    if (kv) {
      key = kv[1];
      fm[key] = kv[2];
    } else if (key !== null && /^\s+\S/.test(line)) {
      fm[key] = `${fm[key] ?? ''} ${line.trim()}`;
    }
  }
  for (const k of Object.keys(fm)) {
    let v = fm[k];
    if (v === '|' || v === '>') v = '';
    v = v.replace(/^["']|["']$/g, '').trim();
    fm[k] = v;
  }
  if (!fm.description) {
    const block = /^description:\s*[|>]\s*\r?\n((?:[ \t]+.*\r?\n?)+)/m.exec(m[1]);
    if (block) {
      fm.description = block[1]
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean)
        .join(' ');
    }
  }
  return { fm, body: text.slice(m[0].length).replace(/^\r?\n/, '') };
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

export function apply(ctx, config = {}) {
  let catalog;
  const load = async () => {
    if (catalog !== undefined) return catalog;
    try {
      catalog = JSON.parse(await readFile(CATALOG_PATH, 'utf8'));
    } catch {
      return undefined; // 不缓存失败：文件修好后下次即可恢复
    }
    return catalog;
  };

  const switches = async () => {
    const dir = profileDir();
    if (!dir) return {};
    try {
      return JSON.parse(await readFile(join(dir, 'biomedical-skills.json'), 'utf8'));
    } catch {
      return {};
    }
  };

  /**
   * 白名单：专项 preset 只列自己要的分类（config.only），不写 34 个布尔值。
   * 给了 only 就完全按 only 走，忽略 profile 级开关文件；否则退回「34 个布尔 + 文件覆盖」
   * 的全量行为，这样全量 preset 仍然可以在设置页自由开关。
   */
  const only = Array.isArray(config?.only) && config.only.length > 0 ? new Set(config.only) : undefined;

  // ══════════════════════════════════════════════════════════════════════
  // 会话级覆盖：每个会话可以单独选启用哪些分类，优先于 preset 白名单与
  // profile 级开关文件。存在内存里（重启清空），由 Web UI 通过下面两个
  // HTTP 路由读写；skills.snapshot() 每个 step 都会重新查询，所以改完
  // 下一个 step 就生效，不需要新开会话。
  // ══════════════════════════════════════════════════════════════════════
  /** @type {Map<string, Set<string>>} sessionId → 该会话启用的分类 id */
  const sessionOverrides = new Map();

  /** provider 的 control，改动配置后用它让目录缓存失效 */
  let controlRef;

  /**
   * 可选服务必须用 ctx.inject 等待就绪，不能用 ctx.get：
   * 冷启动时 apply() 可能早于 webServer / agents 注册，get 会拿到 undefined，
   * 路由就永远注册不上（实测：热加载时 available，冷启动时 UNAVAILABLE）。
   */
  let agentsSvc;
  ctx.inject(['agents'], (scoped) => {
    agentsSvc = scoped.agents;
    return () => {
      agentsSvc = undefined;
    };
  });

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

  ctx.inject(['webServer'], (scoped) => {
    const disposeGet = scoped.webServer.register(
      {
        kind: 'exact',
        path: '/bio-skills/get',
        handler: async (request, response) => {
          if (request.method !== 'GET') {
            response.writeHead(405, { allow: 'GET' });
            response.end();
            return;
          }
          const url = new URL(request.url ?? '/', 'http://127.0.0.1');
          const sid = String(url.searchParams.get('sessionId') ?? '').trim();
          const doc = await load();
          const active = sid ? sessionOverrides.get(sid) : undefined;
          const profileSwitches = await switches();
          const allIds = (doc?.categories ?? []).map((c) => c.id);
          // 本会话此刻真正生效的分类：会话覆盖 > preset 白名单 > profile 开关文件。
          // 前端不该自己猜这个优先级，所以这里直接算好回给 UI。
          const effective = active
            ? [...active]
            : only
              ? [...only]
              : allIds.filter((id) => profileSwitches[id] !== false);
          sendJson(response, 200, {
            ok: true,
            sessionId: sid,
            categories: (doc?.categories ?? []).map((c) => ({
              id: c.id,
              label: c.label_zh,
              count: c.skills.length,
            })),
            enabled: active ? [...active] : null,
            effective,
            source: active ? 'session' : only ? 'preset' : 'profile',
            presetOnly: only ? [...only] : null,
          });
        },
      },
      'biomedical-picker: session-skills/get',
    );

    const disposeSet = scoped.webServer.register(
      {
        kind: 'exact',
        path: '/bio-skills/set',
        handler: async (request, response) => {
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
            sessionOverrides.delete(sid);
          } else {
            sessionOverrides.set(sid, new Set(enabled));
          }
          try {
            controlRef?.invalidate?.();
          } catch {}
          sendJson(response, 200, {
            ok: true,
            sessionId: sid,
            enabled: enabled ? [...enabled] : null,
          });
        },
      },
      'biomedical-picker: session-skills/set',
    );

    ctx.logger?.info?.('biomedical-picker: session-skills routes registered');

    return () => {
      try {
        disposeGet();
      } catch {}
      try {
        disposeSet();
      } catch {}
    };
  });

  const dispose = ctx.skills.registerProvider((control) => {
    controlRef = control;
    return {
      name: 'biomedical-picker',

    async list() {
      const doc = await load();
      if (!doc || !Array.isArray(doc.categories) || doc.categories.length === 0) {
        ctx.logger?.warn?.('biomedical-picker: catalog empty, falling back to full directory scan');
        return scanAll();
      }
      const effective = { ...config, ...(await switches()) };

      // 会话级覆盖优先：该会话显式选过分类，就完全按它走
      let sessionSet;
      let currentSid;
      try {
        const agent = agentsSvc?.currentInitiator?.();
        const sid = agent?.id;
        currentSid = sid;
        if (sid) sessionSet = sessionOverrides.get(sid);
      } catch (e) {
        ctx.logger?.warn?.(`biomedical-picker: currentInitiator failed: ${e?.message ?? e}`);
      }
      if (sessionOverrides.size > 0) {
        ctx.logger?.info?.(
          `biomedical-picker: list() sid=${currentSid ?? 'undefined'} overrides=${sessionOverrides.size} hit=${Boolean(sessionSet)}`,
        );
      }

      const out = [];
      for (const category of doc.categories) {
        if (sessionSet) {
          if (!sessionSet.has(category.id)) continue;
        } else if (only) {
          if (!only.has(category.id)) continue;
        } else if (effective[category.id] === false) continue;
        for (const entry of category.skills) {
          const directory = join(SKILLS_ROOT, entry.path);
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
            metadata: { category: category.id, categoryLabel: category.label_zh },
          });
        }
      }
      if (out.length === 0) {
        ctx.logger?.warn?.('biomedical-picker: every category disabled or unreadable, falling back to full scan');
        return scanAll();
      }
      return out;
    },

    async get(candidate) {
      const text = await readFile(candidate.locator.path, 'utf8');
      const { body } = frontmatter(text);
      return { ...candidate, content: body };
    },
    };
  });

  ctx.effect(() => dispose, 'biomedical-skill-picker: provider');
}

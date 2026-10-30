/**
 * 生物医学技能选择器（Host half）
 *
 * 单一 skill provider：按 catalog.json 的 34 个功能分类提供 603 个技能。
 * 开关状态只来自 profile 的 biomedical-skills.json（由 dsh-biomedical-skill-settings
 * 的设置页写入），本插件刻意不声明 Config —— 这样它只依赖 node 内置模块，
 * 不会因为跨包解析（schemastery 等）失败而拖垮整个预设的挂载。
 */
import { readFile } from 'node:fs/promises';
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

export function apply(ctx, config = {}) {
  let catalog;
  const load = async () => {
    if (catalog === undefined) catalog = JSON.parse(await readFile(CATALOG_PATH, 'utf8'));
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

  const dispose = ctx.skills.registerProvider(() => ({
    name: 'biomedical-picker',

    async list() {
      const doc = await load();
      const effective = { ...config, ...(await switches()) };
      const out = [];
      for (const category of doc.categories) {
        if (effective[category.id] === false) continue;
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
      return out;
    },

    async get(candidate) {
      const text = await readFile(candidate.locator.path, 'utf8');
      const { body } = frontmatter(text);
      return { ...candidate, content: body };
    },
  }));

  ctx.effect(() => dispose, 'biomedical-skill-picker: provider');
}

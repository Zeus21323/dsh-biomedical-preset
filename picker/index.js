/**
 * 生物医学技能选择器（Host half）
 *
 * 用一个自定义 skill provider 取代 6 个 skill-filesystem hub：
 * 按 catalog.json 里的功能分类分组，Config 里每个分类一个开关。
 * Config 变更会让 Cordis 重启本插件，provider 重新注册，技能目录随之变化。
 */
import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Config } from './config.mjs';

export const name = 'biomedical-skill-picker';
export const inject = ['skills'];
export { Config };

const HERE = dirname(fileURLToPath(import.meta.url));
const SKILLS_ROOT = join(HERE, '..', 'skills');
const CATALOG_PATH = join(HERE, 'catalog.json');

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
  // description 用块标量时，从原文补齐
  if (!fm.description) {
    const block = /^description:\s*[|>]\s*\r?\n((?:[ \t]+.*\r?\n?)+)/m.exec(m[1]);
    if (block) fm.description = block[1].split(/\r?\n/).map((l) => l.trim()).filter(Boolean).join(' ');
  }
  return { fm, body: text.slice(m[0].length).replace(/^\r?\n/, '') };
}

export function apply(ctx, config = {}) {
  let catalog;
  const load = async () => {
    if (catalog === undefined) catalog = JSON.parse(await readFile(CATALOG_PATH, 'utf8'));
    return catalog;
  };

  // 设置页（dsh-biomedical-skill-settings）把开关镜像到这个文件；
  // 文件优先于本行的 config，这样页面改动无需重启 preset 即可生效。
  const switches = async () => {
    // Host 进程不一定导出 DSH_PROFILE_DIR；与设置插件保持同一套兜底。
    const dir = process.env.DSH_PROFILE_DIR || 'C:/Users/20735/.dsh/profiles/desktop';
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

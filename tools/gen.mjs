/**
 * 生成器：把「技能目录 + 模式定义」变成各处需要同步的产物，消灭手工复制。
 *
 * 数据源（只改这里）：
 *   picker/catalog.json            34 个分类 × 技能（name / path / desc）
 *   spec/modes.json                12 个专项模式（id、名称、说明、排序、分类、浮窗图标与颜色）
 *   spec/settings-groups.json      设置页的 6 个大组
 *   spec/specialist-preset.yml.tpl 专项模式的预设模板（共享纪律、MCP 等都通过 YAML 锚点引用全量模式）
 *
 * 产物（各自只改标记区间，区间外的手写内容不动）：
 *   cordis.patch.yml     gen:specialist-presets、gen:settings-switches
 *   client.js            LABELS / GROUPS / SKILLS / SECTIONS 四个常量
 *   settings/config.mjs  34 个开关的 Config
 *   README.md            gen:modes-table、gen:groups-table、gen:categories-table
 *   locale/{en,zh}.json  技能总数
 *
 * 跑法：
 *   node tools/gen.mjs          重新生成并写回
 *   node tools/gen.mjs --check  只比较，有差异就退出 1（提交前 / CI 用）
 */
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PKG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CHECK = process.argv.includes('--check');
const rd = (p) => readFileSync(path.join(PKG, p), 'utf8');
const json = (p) => JSON.parse(rd(p));

const catalog = json('picker/catalog.json');
const modes = json('spec/modes.json');
const groups = json('spec/settings-groups.json');
const tpl = rd('spec/specialist-preset.yml.tpl');
const domains = json('mcp/domains.json');
const domainOf = (tool) => Object.entries(domains).find(([, d]) => d.prefixes.some((p) => tool.startsWith(p)))?.[0];

/** 一个技能在目录里大约占多少 token（README 实测：603 个 ≈ 33 400）。 */
const TOKENS_PER_SKILL = 55.4;

// ───────────────────────────────────────────────────────────── 校验
const problems = [];
const cats = new Map(catalog.categories.map((c) => [c.id, c]));
const names = new Set();
for (const c of catalog.categories) {
  for (const s of c.skills) {
    if (names.has(s.name)) problems.push(`技能重名：${s.name}`);
    names.add(s.name);
    if (!existsSync(path.join(PKG, 'skills', s.path, 'SKILL.md'))) problems.push(`catalog 指向不存在的技能：${s.path}`);
    if (!s.desc) problems.push(`技能缺 desc：${s.name}`);
  }
}
const seen = new Map();
for (const m of modes) {
  for (const c of m.cats) {
    if (!cats.has(c)) problems.push(`模式 ${m.id} 引用未知分类 ${c}`);
    if (seen.has(c)) problems.push(`分类 ${c} 同时属于 ${seen.get(c)} 与 ${m.id}`);
    seen.set(c, m.id);
  }
}
for (const c of cats.keys()) if (!seen.has(c)) problems.push(`分类 ${c} 不属于任何专项模式`);
// MCP 领域：模式声明的领域要存在；模式内技能声明的 MCP 工具必须落在该模式开放的领域里
for (const m of modes) {
  const allowed = new Set(m.mcpDomains ?? []);
  if (allowed.size === 0) problems.push(`模式 ${m.id} 没有声明 mcpDomains`);
  for (const d of allowed) if (!domains[d]) problems.push(`模式 ${m.id} 声明了未知 MCP 领域 ${d}`);
  for (const c of m.cats) {
    for (const s of cats.get(c)?.skills ?? []) {
      for (const tool of s.mcp ?? []) {
        const d = domainOf(tool);
        if (!d) problems.push(`技能 ${s.name} 声明的 MCP 工具 ${tool} 不属于任何领域`);
        else if (!allowed.has(d)) problems.push(`模式 ${m.id} 没开放「${d}」领域，但其中的技能 ${s.name} 声明了 ${tool}`);
      }
    }
  }
}
const grouped = new Set(groups.flatMap((g) => g.cats));
for (const c of cats.keys()) if (!grouped.has(c)) problems.push(`分类 ${c} 不属于设置页任何大组`);
if (problems.length) {
  console.error(problems.join('\n'));
  process.exit(1);
}

const total = catalog.categories.reduce((a, c) => a + c.skills.length, 0);
const listedIn = (c) => c.skills.filter((s) => !s.via).length;
/** 折叠的流程（经入口加载，如 nf-core）；被合并的重复技能（merged）单独计 */
const foldedIn = (c) => c.skills.filter((s) => s.via && !s.merged).length;
const mergedIn = (c) => c.skills.filter((s) => s.merged).length;
const countOf = (ids) => ids.reduce((a, id) => a + cats.get(id).skills.length, 0);
/** 目录里实际列出的技能数：折叠技能不算，但范围内有折叠技能时入口技能要算上（若不在范围内）。 */
function listedCount(ids) {
  const set = new Set(ids);
  let n = ids.reduce((a, id) => a + listedIn(cats.get(id)), 0);
  const routers = new Set(ids.flatMap((id) => cats.get(id).skills.filter((s) => s.via).map((s) => s.via)));
  for (const r of routers) {
    const home = catalog.categories.find((c) => c.skills.some((s) => s.name === r));
    if (home && !set.has(home.id)) n += 1;
  }
  return n;
}
const foldedCount = (ids) => ids.reduce((a, id) => a + foldedIn(cats.get(id)), 0);
const totalListed = listedCount([...cats.keys()]);
const totalFolded = foldedCount([...cats.keys()]);
const totalMerged = catalog.categories.reduce((a, c) => a + mergedIn(c), 0);
const skillsCell = (ids) => (foldedCount(ids) ? `${listedCount(ids)}（+${foldedCount(ids)} 个流程）` : `${listedCount(ids)}`);
const tokens = (n) => Math.round((n * TOKENS_PER_SKILL) / 100) * 100;
const fmtTokens = (n) => tokens(n).toLocaleString('en-US').replace(/,/g, ' ');

// ───────────────────────────────────────────────────────────── 工具
const outputs = new Map();
function replaceRegion(text, startMarker, endMarker, body, file) {
  const a = text.indexOf(startMarker);
  const b = text.indexOf(endMarker, a);
  if (a < 0 || b < 0) throw new Error(`${file}: 找不到标记 ${startMarker} … ${endMarker}`);
  const lineEnd = text.indexOf('\n', a) + 1;
  const endLineStart = text.lastIndexOf('\n', b) + 1;
  return text.slice(0, lineEnd) + body + text.slice(endLineStart);
}
function replaceConst(text, name, close, value) {
  const head = `    const ${name} = `;
  const a = text.indexOf(head);
  const b = text.indexOf(`\n    ${close};\n`, a);
  if (a < 0 || b < 0) throw new Error(`client.js: 找不到常量 ${name}`);
  const body = JSON.stringify(value, null, 4).split('\n').join('\n    ');
  return text.slice(0, a + head.length) + body + text.slice(b + `\n    ${close}`.length);
}
const fill = (t, vars) => t.replace(/\{\{(\w+)\}\}/g, (_, k) => {
  if (!(k in vars)) throw new Error(`模板变量没给：${k}`);
  return vars[k];
});

// ───────────────────────────────────────────────────────────── cordis.patch.yml
{
  let text = rd('cordis.patch.yml');
  const blocks = [...modes]
    .sort((a, b) => a.order - b.order)
    .map((m) =>
      fill(tpl, {
        ID: m.id,
        NAME: m.name,
        DESC: m.description,
        ORDER: String(m.order),
        N: String(listedCount(m.cats)),
        K: String(m.cats.length),
        LABELS: m.cats.map((c) => cats.get(c).label_zh).join('、'),
        ONLY: m.cats.map((c) => `                - ${c}`).join('\n'),
        MCP_DOMAINS: m.mcpDomains.join(','),
        MCP_DOMAINS_ZH: m.mcpDomains.map((d) => domains[d].label).join('、'),
      }),
    );
  text = replaceRegion(text, '    # >>> gen:specialist-presets', '    # <<< gen:specialist-presets', blocks.join('\n'), 'cordis.patch.yml');
  text = replaceRegion(
    text,
    '        # >>> gen:settings-switches',
    '        # <<< gen:settings-switches',
    catalog.categories.map((c) => `        "${c.id}": true\n`).join(''),
    'cordis.patch.yml',
  );
  outputs.set('cordis.patch.yml', text);
}

// ───────────────────────────────────────────────────────────── client.js
{
  let text = rd('client.js');
  const LABELS = Object.fromEntries(
    catalog.categories.map((c) => [c.id, { label: c.label_zh, desc: c.desc_zh, count: listedIn(c), folded: foldedIn(c) }]),
  );
  const SKILLS = Object.fromEntries(
    catalog.categories.map((c) => [c.id, c.skills.map((s) => ({ name: s.name, desc: s.desc, ...(s.via ? { via: s.via } : {}) }))]),
  );
  const SECTIONS = [...modes]
    .sort((a, b) => a.order - b.order)
    .map((m) => ({ id: m.section, label: m.sectionLabel ?? m.name, emoji: m.emoji, color: m.color, cats: m.sectionCats ?? m.cats }));
  text = replaceConst(text, 'LABELS', '}', LABELS);
  text = replaceConst(text, 'GROUPS', ']', groups);
  text = replaceConst(text, 'SKILLS', '}', SKILLS);
  text = replaceConst(text, 'SECTIONS', ']', SECTIONS);
  outputs.set('client.js', text);
}

// ───────────────────────────────────────────────────────────── settings/config.mjs
{
  const text = rd('settings/config.mjs');
  const a = text.indexOf('export const Config = z.object({');
  const b = text.indexOf('\n});', a);
  if (a < 0 || b < 0) throw new Error('settings/config.mjs: 找不到 Config');
  const lines = catalog.categories
    .map((c) => `  "${c.id}": z.boolean().default(true).volatile().description("${c.label_zh}（${listedIn(c)} 个技能${foldedIn(c) ? `，另有 ${foldedIn(c)} 个 nf-core 流程经入口加载` : ''}）"),`)
    .join('\n');
  outputs.set('settings/config.mjs', text.slice(0, a) + 'export const Config = z.object({\n' + lines + text.slice(b));
}

// ───────────────────────────────────────────────────────────── README.md
{
  let text = rd('README.md');
  const modesRows = [
    '| 模式（新建会话时选） | 覆盖的分类 | 技能 | 约 token |',
    '|---|---|---|---|',
    `| **生物医学模式**（全量） | 全部 ${cats.size} 类 | ${skillsCell([...cats.keys()])} | ${fmtTokens(totalListed)} |`,
    ...[...modes]
      .sort((a, b) => a.order - b.order)
      .map((m) => `| ${m.name} | ${m.cats.map((c) => cats.get(c).label_zh).join('、')} | ${skillsCell(m.cats)} | ${fmtTokens(listedCount(m.cats))} |`),
  ];
  const groupRows = [
    '| 大组 | 分类数 | 技能数 |',
    '|---|---|---|',
    ...groups.map((g) => `| ${g.label} | ${g.cats.length} | ${skillsCell(g.cats)} |`),
  ];
  const catRows = [
    '| 分类 | id | 技能数 | 覆盖 |',
    '|---|---|---|---|',
    ...catalog.categories.map((c) => `| ${c.label_zh} | \`${c.id}\` | ${skillsCell([c.id])} | ${c.desc_zh} |`),
  ];
  for (const [name, rows] of [['modes-table', modesRows], ['groups-table', groupRows], ['categories-table', catRows]]) {
    text = replaceRegion(text, `<!-- gen:${name}`, `<!-- /gen:${name} -->`, rows.join('\n') + '\n', 'README.md');
  }
  outputs.set('README.md', text);
}

// ───────────────────────────────────────────────────────────── locale
for (const [file, re, fmt] of [
  ['locale/en.json', /\d+ workflow skills/, (n) => `${n} workflow skills`],
  ['locale/zh.json', /\d+ 个流程技能/, (n) => `${n} 个流程技能`],
]) {
  const text = rd(file);
  if (!re.test(text)) throw new Error(`${file}: 找不到技能数`);
  outputs.set(file, text.replace(re, fmt(total)));
}

// ───────────────────────────────────────────────────────────── 写回 / 检查
const stale = [];
for (const [file, text] of outputs) {
  if (rd(file) === text) continue;
  stale.push(file);
  if (!CHECK) writeFileSync(path.join(PKG, file), text);
}
if (CHECK) {
  if (stale.length) {
    console.error(`以下文件与数据源不一致，请运行 node tools/gen.mjs：\n  ${stale.join('\n  ')}`);
    process.exit(1);
  }
  console.log(`生成产物与数据源一致（${total} 个技能：目录列出 ${totalListed} 个，${totalFolded} 个流程经入口加载，${totalMerged} 个已并入主技能 / ${cats.size} 类 / ${modes.length} 个专项模式）`);
} else {
  console.log(stale.length ? `已更新：${stale.join('、')}` : '无变化');
  console.log(`${total} 个技能 / ${cats.size} 类 / ${modes.length} 个专项模式`);
}

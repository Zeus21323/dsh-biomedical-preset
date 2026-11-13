/**
 * 13 个预设的结构体检
 *
 * 背景：12 个专项模式曾因 picker 抢路由导致整个预设挂载被拒，问题被「第一行失败」
 * 遮住，后面可能还压着别的结构错误。修好 picker 后它们会真正走 auditRows，
 * 所以提交前先静态查一遍：行数、picker/mcp/persona/cap 是否都在、only 白名单
 * 是否都指向真实分类、12 个专项合起来是否正好覆盖 34 类且不重叠。
 *
 * 跑法：node tools/lint-presets.mjs
 */
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PKG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
// 可选第一个参数指向别的 patch 文件，便于反向验证 lint 本身（例如故意删掉一行守卫）。
const PATCH = process.argv[2] ? path.resolve(process.argv[2]) : path.join(PKG, 'cordis.patch.yml');
const CATALOG = path.join(PKG, 'picker', 'catalog.json');

const text = await readFile(PATCH, 'utf8');
const catalog = JSON.parse(await readFile(CATALOG, 'utf8'));
const knownCats = new Set(catalog.categories.map((c) => c.id));

const blocks = [];
let cur = null;
for (const line of text.split('\n')) {
  const m = /^    - id: (preset-[\w-]+)\s*$/.exec(line);
  if (m) {
    cur = { patchId: m[1], lines: [] };
    blocks.push(cur);
    continue;
  }
  if (cur) cur.lines.push(line);
}

const problems = [];
const notes = [];

for (const b of blocks) {
  const body = b.lines.join('\n');
  const get = (k) => {
    const m = new RegExp(`^        ${k}: (.+)$`, 'm').exec(body);
    return m ? m[1].trim() : undefined;
  };
  b.id = get('id');
  const name = get('name');
  const order = get('order');

  if (!b.id) problems.push(`${b.patchId}: 缺 config.id`);
  if (!name) problems.push(`${b.patchId}: 缺 config.name`);
  if (order === undefined) problems.push(`${b.patchId}: 缺 order`);

  b.rows = [...body.matchAll(/^          - id: ([\w-]+)$/gm)].map((m) => m[1]);

  // only 白名单：按行缩进取，别用 \s*（它会吞掉换行，把第一项吃掉）
  b.only = [];
  for (let k = 0; k < b.lines.length; k++) {
    const m = /^([ \t]+)only:[ \t]*$/.exec(b.lines[k]);
    if (!m) continue;
    const ind = m[1].length;
    for (let j = k + 1; j < b.lines.length; j++) {
      const mm = new RegExp(`^[ \\t]{${ind + 2}}- (.+)$`).exec(b.lines[j]);
      if (!mm) break;
      b.only.push(mm[1].trim().replace(/^['"]|['"]$/g, ''));
    }
    break;
  }

  for (const row of ['biomedical-skill-picker', 'bio-mcp', 'persona', 'subagent-cap']) {
    if (!b.rows.includes(row)) problems.push(`${b.patchId}: 没有 ${row} 行`);
  }

  const unknown = b.only.filter((c) => !knownCats.has(c));
  if (unknown.length > 0) problems.push(`${b.patchId}: only 里有未知分类 ${unknown.join(',')}`);
  if (new Set(b.only).size !== b.only.length) problems.push(`${b.patchId}: only 有重复项`);
  if (b.id !== 'biomedical' && b.only.length === 0) problems.push(`${b.patchId}: 专项模式没有 only 白名单`);

  if (!/prefix: \|/.test(body)) problems.push(`${b.patchId}: persona 没有 prefix`);
  // 共享纪律（方法适配裁决、结论纪律、PHI 等）必须每个模式都挂，专项模式曾经全部漏掉
  if (!/suffix: (&bio-discipline \||\*bio-discipline)\s*$/m.test(body)) {
    problems.push(`${b.patchId}: persona 没有挂共享纪律 suffix（&bio-discipline / *bio-discipline）`);
  }
  if (!new RegExp(`^              preset: ${b.id}$`, 'm').test(body)) {
    problems.push(`${b.patchId}: picker 行缺 config.preset: ${b.id}（浮窗按会话找白名单要用）`);
  }
  if (b.rows.length < 18) problems.push(`${b.patchId}: 插件行只有 ${b.rows.length} 行（预期 ≥ 22）`);

  // 平台守卫：漏了会让 tool-bash 在 Windows 上被启用，那一行失败 → 整个预设挂载被拒
  // （2026-11-04 实测事故：12 个专项模式全都是这个原因）
  if (!/disabled: !!js process\.platform === 'win32'/.test(body)) {
    problems.push(`${b.patchId}: tool-bash 缺少 disabled: !!js process.platform === 'win32'`);
  }
  if (!/disabled: !!js process\.platform !== 'win32'/.test(body)) {
    problems.push(`${b.patchId}: tool-pwsh 缺少 disabled: !!js process.platform !== 'win32'`);
  }

  // 必填 config：这两项在各自 Config 里是 .required()，没有默认值。
  // 漏了 → 该行 invalid config → auditRows 判预设 failed → 挂载被拒。
  // （2026-11-04 实测事故：12 个专项模式就是漏了这两项；原先误当成「走默认值」）
  if (!/maxBytes:[ \t]*\d+/.test(body)) {
    problems.push(`${b.patchId}: agent-instructions 缺少必填 config maxBytes（该行会 invalid config）`);
  }
  if (!/sampleOverCapGlobResults:[ \t]*(true|false)/.test(body)) {
    problems.push(`${b.patchId}: tool-fs-search 缺少必填 config sampleOverCapGlobResults（该行会 invalid config）`);
  }

  const nameCount = [...body.matchAll(/^            name: /gm)].length;
  if (nameCount < b.rows.length) problems.push(`${b.patchId}: ${b.rows.length} 个行只找到 ${nameCount} 个 name:`);

  notes.push(
    `${b.patchId.padEnd(28)} id=${String(b.id).padEnd(24)} rows=${String(b.rows.length).padStart(2)} only=${String(b.only.length).padStart(2)} ${name}`,
  );
}

// persona 里点名的技能必须真实存在（技能改名后 persona 曾留着 5 个失效名字）。
// 检查「X 走 `a` / `b`」这类点名行里的反引号名字；带 * 的通配（如 nfcore-*）只要求至少匹配一个。
{
  const skillNames = new Set(catalog.categories.flatMap((c) => c.skills.map((s) => s.name)));
  for (const [i, line] of text.split('\n').entries()) {
    if (!/走 `/.test(line)) continue;
    for (const [, tok] of line.matchAll(/`([a-z0-9][a-z0-9*-]*)`/g)) {
      const ok = tok.includes('*')
        ? [...skillNames].some((n) => new RegExp(`^${tok.replace(/[-]/g, '\\-').replace(/\*/g, '.*')}$`).test(n))
        : skillNames.has(tok);
      if (!ok) problems.push(`第 ${i + 1} 行 persona 点名的技能不存在：${tok}`);
    }
  }
}

// 不许出现某台机器的绝对路径（曾经写死 C:/Users/<用户名>/、F:/... ，别人装上后 MCP 静默起不来）
for (const [i, line] of text.split('\n').entries()) {
  if (/^\s*#/.test(line)) continue;
  if (/(^|[\s'"])([A-Za-z]:[\\/]|\/Users\/|\/home\/)/.test(line)) problems.push(`第 ${i + 1} 行写死了本机绝对路径：${line.trim().slice(0, 80)}`);
}

const ids = blocks.map((b) => b.id).filter(Boolean);
const dupIds = ids.filter((v, i) => ids.indexOf(v) !== i);
if (dupIds.length > 0) problems.push(`重复的 preset id: ${[...new Set(dupIds)].join(',')}`);
if (blocks.length !== 13) problems.push(`预设数 ${blocks.length}，预期 13`);

const special = blocks.filter((b) => b.id && b.id !== 'biomedical');
const seen = new Map();
for (const b of special) {
  for (const cat of b.only) {
    if (seen.has(cat)) problems.push(`分类 ${cat} 同时出现在 ${seen.get(cat)} 与 ${b.patchId}`);
    seen.set(cat, b.patchId);
  }
}
const notCovered = [...knownCats].filter((c) => !seen.has(c));
if (notCovered.length > 0) problems.push(`没有专项模式覆盖的分类: ${notCovered.join(',')}`);
if (seen.size !== knownCats.size) problems.push(`专项模式覆盖 ${seen.size} 类，catalog 有 ${knownCats.size} 类`);

console.log(notes.join('\n'));
console.log(`\n预设数: ${blocks.length}（1 全量 + ${special.length} 专项）`);
console.log(`分类覆盖: ${seen.size} / ${knownCats.size}`);
if (problems.length > 0) {
  console.log('\n' + problems.join('\n'));
  console.log(`\n结果：${problems.length} 个问题`);
  process.exit(1);
}
console.log('\n结果：结构体检全部通过');

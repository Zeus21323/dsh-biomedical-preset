/**
 * 技能库体检：目录与 catalog 一致、名字不撞、没有不能再分发的许可证、没有开发残留。
 *
 * 跑法：node tools/lint-skills.mjs
 */
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadMcpTools } from '../shared/mcp-tools.mjs';
import { frontmatter } from '../shared/frontmatter.mjs';

const PKG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const SKILLS = path.join(PKG, 'skills');
const catalog = JSON.parse(readFileSync(path.join(PKG, 'picker', 'catalog.json'), 'utf8'));
const problems = [];

// 1. 目录 ↔ catalog
const inCatalog = new Set(catalog.categories.flatMap((c) => c.skills.map((s) => s.path)));
const onDisk = new Set();
for (const domain of readdirSync(SKILLS)) {
  const d = path.join(SKILLS, domain);
  if (!statSync(d).isDirectory()) continue;
  for (const skill of readdirSync(d)) {
    if (statSync(path.join(d, skill)).isDirectory()) onDisk.add(`${domain}/${skill}`);
  }
}
for (const p of onDisk) if (!inCatalog.has(p)) problems.push(`skills/${p} 不在 catalog 里（不会被加载）`);
for (const p of inCatalog) if (!onDisk.has(p)) problems.push(`catalog 里的 ${p} 在磁盘上不存在`);

// 2. frontmatter name 与目录名一致、全局不重名
const names = new Map();
for (const p of onDisk) {
  const file = path.join(SKILLS, p, 'SKILL.md');
  if (!existsSync(file)) {
    problems.push(`skills/${p} 缺 SKILL.md`);
    continue;
  }
  const fm = /^---\r?\n([\s\S]*?)\r?\n---/.exec(readFileSync(file, 'utf8'));
  const name = fm && /^name:\s*["']?([^"'\r\n]+?)["']?\s*$/m.exec(fm[1])?.[1];
  if (!name) problems.push(`skills/${p}/SKILL.md 缺 name`);
  else if (name !== path.basename(p)) problems.push(`skills/${p}: name「${name}」与目录名不一致`);
  if (name && names.has(name)) problems.push(`技能重名：${name}（${names.get(name)} 与 ${p}）`);
  if (name) names.set(name, p);
}

// 2b. 技能声明的 MCP 工具必须真实存在（catalog 的 mcp 数组与 SKILL.md frontmatter 的 mcp 字段）
{
  let toolNames;
  try {
    toolNames = new Set(loadMcpTools().map((t) => t.name));
  } catch (e) {
    problems.push(`无法读取 MCP 工具清单：${e.message}`);
  }
  if (toolNames) {
    for (const c of catalog.categories) {
      for (const s of c.skills) {
        const fromFm = frontmatter(readFileSync(path.join(SKILLS, s.path, 'SKILL.md'), 'utf8')).fm.mcp;
        const declared = [
          ...(s.mcp ?? []),
          ...(fromFm ? String(fromFm).replace(/^\[|\]$/g, '').split(',').map((t) => t.trim().replace(/^["']|["']$/g, '').replace(/^mcp__biomedical__/, '')).filter(Boolean) : []),
        ];
        for (const t of declared) if (!toolNames.has(t)) problems.push(`技能 ${s.name} 声明的 MCP 工具不存在：${t}`);
        if (s.via && !inCatalog.has(catalog.categories.flatMap((x) => x.skills).find((x) => x.name === s.via)?.path)) {
          problems.push(`技能 ${s.name} 的入口 ${s.via} 不在 catalog 里`);
        }
      }
    }
  }
}

// 2c. 描述规范：目录里模型只看得到 name + description（截断 500 字），描述就是路由依据
//   - 不能为空、不超过 500 字（超出部分被截掉，后面的触发词等于没写）
//   - 必须有中文（目录统一中文，英文与中文描述混排会让检索和模型都偏向某一种语言）
//   - 不能是「在 X 领域开展“Y”任务时使用」这类模板句（法医类曾经全是，路由命中率 0%）
//   - 同分类内词面相似度 ≥ SIMILAR_ERROR 的两条描述必须互相点名（写清何时用哪个）
const SIMILAR_ERROR = 0.4;
const SIMILAR_WARN = 0.3;
const warnings = [];
{
  const bigrams = (t) => {
    const x = t.toLowerCase().replace(/\s+/g, '');
    const out = new Set();
    for (let i = 0; i + 1 < x.length; i++) out.add(x.slice(i, i + 2));
    return out;
  };
  let over300 = 0;
  for (const c of catalog.categories) {
    const rows = [];
    for (const s of c.skills) {
      const d = frontmatter(readFileSync(path.join(SKILLS, s.path, 'SKILL.md'), 'utf8')).fm.description ?? '';
      if (!d) problems.push(`技能 ${s.name} 没有 description`);
      else if (d.length > 500) problems.push(`技能 ${s.name} 的 description 有 ${d.length} 字，超过 500 字的部分会被目录截掉`);
      if (d && !/[一-鿿]/.test(d)) problems.push(`技能 ${s.name} 的 description 没有中文`);
      if (/^在.{1,16}领域开展[“"].+[”"]任务时使用/.test(d)) problems.push(`技能 ${s.name} 的 description 是模板句，写不出它和同类技能的区别`);
      if (d.length > 300) over300++;
      if (!s.via) rows.push([s.name, d, bigrams(d)]);
    }
    for (let i = 0; i < rows.length; i++) {
      for (let j = i + 1; j < rows.length; j++) {
        const [a, da, ba] = rows[i];
        const [b, db, bb] = rows[j];
        let inter = 0;
        for (const g of ba) if (bb.has(g)) inter++;
        const jac = inter / Math.max(1, ba.size + bb.size - inter);
        const crossRef = da.includes(b) || db.includes(a);
        if (jac >= SIMILAR_ERROR && !crossRef) problems.push(`${a} 与 ${b} 的描述高度相似（${jac.toFixed(2)}），请在描述里写清何时用哪个`);
        else if (jac >= SIMILAR_WARN && !crossRef) warnings.push(`${a} ~ ${b}（${jac.toFixed(2)}）`);
      }
    }
  }
  if (over300) warnings.push(`${over300} 条描述超过 300 字（建议精简，关键名词放最前面）`);
}

// 3. 许可证 & 残留文件
const RESIDUE = [/_audit_result_v\d+\.json$/, /^eval_report_.*_result\.json$/, /_FIXED[._]/, /^SKILL_TEST_FEEDBACK\.md$/, /^COMPARISON_.*\.md$/, /^\.env(\..+)?$/, /\.pyc$/];
const ALLOWED_ENV = /^\.env\.(template|example)$/;
function walk(dir) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    const rel = path.relative(PKG, full);
    if (entry.isDirectory()) {
      if (entry.name === '__pycache__' || entry.name === 'node_modules') problems.push(`${rel} 是构建/缓存目录，不应进仓库`);
      else walk(full);
      continue;
    }
    if (RESIDUE.some((re) => re.test(entry.name)) && !ALLOWED_ENV.test(entry.name)) problems.push(`${rel} 像开发残留（评测报告 / 调试产物 / 密钥文件）`);
    if (/^licen[cs]e/i.test(entry.name)) {
      const text = readFileSync(full, 'utf8');
      if (/all rights reserved/i.test(text) && !/permission is hereby granted|apache license|bsd/i.test(text)) {
        problems.push(`${rel} 是保留所有权利的许可证，不能随 MIT 包再分发`);
      }
    }
  }
}
walk(SKILLS);

const total = inCatalog.size;
if (warnings.length) console.log(`提示（不影响通过）：\n  ${warnings.join('\n  ')}\n`);
if (problems.length) {
  console.log(problems.join('\n'));
  console.log(`\n结果：${problems.length} 个问题（${total} 个技能）`);
  process.exit(1);
}
console.log(`结果：技能库体检通过（${total} 个技能）`);

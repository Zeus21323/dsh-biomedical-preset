/**
 * 技能库体检：目录与 catalog 一致、名字不撞、没有不能再分发的许可证、没有开发残留。
 *
 * 跑法：node tools/lint-skills.mjs
 */
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

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
if (problems.length) {
  console.log(problems.join('\n'));
  console.log(`\n结果：${problems.length} 个问题（${total} 个技能）`);
  process.exit(1);
}
console.log(`结果：技能库体检通过（${total} 个技能）`);

/**
 * 技能自动定级（质量把关与合规）。
 *
 * 规则全部可复现：只看仓库里的文件，不靠人工名单。结果写进 picker/catalog.json 每个技能的
 * `grade` 字段，并生成 COMPLIANCE.md。picker 按 tier 在目录里加标记、加载技能时附合规提示。
 *
 * 等级（按优先级判定，命中即止）：
 *   deprecated  已并入其他技能（catalog 条目 merged: true）
 *   restricted  可执行代码会把内容发送到生成式 AI 服务（OpenAI / OpenRouter / SpeedAI / Anthropic /
 *               Gemini / HuggingFace 推理 / ESM Forge 等）——使用前必须征得用户同意
 *   experimental 有质量缺陷：占位式命名、失效的相对链接、脚本无法编译、正文不足 200 字且没有资源
 *   core        许可证明确且宽松，带 scripts/ 或 references/，并且有测试或正文 ≥ 40 行
 *   standard    其余
 *
 * 只出提示、不改变等级的标记（flags）：
 *   phi            涉及患者或受试者数据（所在分类或描述命中临床关键词）——先去标识化
 *   egress-sequence 文档指引把序列发到公共计算服务（ColabFold MSA 服务器、ESM Forge）——未公开序列改用本地
 *   needs-key       需要第三方 API 密钥（列出变量名）——密钥只放环境变量
 *   license-unknown / license-copyleft  许可证不明或为 copyleft——公开分发前要确认
 *
 * 跑法：
 *   node tools/grade.mjs          重新定级，写回 catalog 与 COMPLIANCE.md
 *   node tools/grade.mjs --check  只比较，不一致时退出 1（自检用）
 */
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { frontmatter } from '../shared/frontmatter.mjs';

const PKG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const CHECK = process.argv.includes('--check');
const CATALOG = path.join(PKG, 'picker', 'catalog.json');
const REPORT = path.join(PKG, 'COMPLIANCE.md');

const catalog = JSON.parse(readFileSync(CATALOG, 'utf8'));

// ───────────────────────────────────────────────────────────── 规则常量
const AI_SERVICES = [
  ['OpenAI', /api\.openai\.com|OPENAI_API_KEY/],
  ['OpenRouter', /openrouter\.ai|OPENROUTER_API_KEY/],
  ['SpeedAI', /speedai|SPEEDAI_API_KEY|SPEEDAPI_API_KEY/i],
  ['Anthropic', /api\.anthropic\.com|ANTHROPIC_API_KEY/],
  ['Google Gemini', /generativelanguage\.googleapis|GEMINI_API_KEY/],
  ['HuggingFace 推理', /api-inference\.huggingface/],
  ['ESM Forge', /forge\.evolutionaryscale|ESM_API_KEY/],
  ['NVIDIA NIM', /NVIDIA_API_KEY|integrate\.api\.nvidia\.com/],
];
const SEQUENCE_SERVICES = [
  ['ColabFold 公共 MSA 服务器', /api\.colabfold\.com|--msa-server|use_msa_server|msa_server|MSA server/],
  ['ESM Forge', /forge\.evolutionaryscale|ESM_API_KEY/],
];
const PHI_CATEGORIES = new Set([
  'variant-interpretation-clinical',
  'clinical-precision-medicine',
  'medical-imaging-radiomics',
  'pharmacogenomics-dosing',
  'forensic-identity-genetics',
]);
const PHI_WORDS = /患者|病人|病历|受试者|临床数据|电子病历|EHR|FHIR|DICOM|PHI|去标识|patient/i;
const PLACEHOLDER_NAME = /scaffold-replace|off-target-scaffold|(^|-)skill-\d+($|-)/;
const CODE_EXT = /\.(py|sh|js|mjs|ts|R|r)$/;
const TEXT_EXT = /\.(md|py|sh|js|mjs|ts|R|r|ya?ml|json|txt|toml|cfg)$/;
const PERMISSIVE = /^(MIT|Apache-2\.0|BSD|ISC|PSF|CC0|Unlicense)/i;

// ───────────────────────────────────────────────────────────── 工具函数
function walk(dir) {
  const out = [];
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    if (e.name === '__pycache__' || e.name === 'node_modules') continue;
    const full = path.join(dir, e.name);
    if (e.isDirectory()) out.push(...walk(full));
    else out.push(full);
  }
  return out;
}

function readText(file) {
  try {
    if (statSync(file).size > 2_000_000) return '';
    return readFileSync(file, 'utf8');
  } catch {
    return '';
  }
}

function detectLicense(dir, fm) {
  const file = readdirSync(dir).find((n) => /^licen[cs]e/i.test(n));
  if (file) {
    const t = readText(path.join(dir, file));
    if (/Permission is hereby granted/i.test(t)) return 'MIT';
    if (/Apache License/i.test(t)) return 'Apache-2.0';
    if (/Redistribution and use in source and binary forms/i.test(t)) return 'BSD';
    if (/GNU (LESSER |AFFERO )?GENERAL PUBLIC/i.test(t)) return 'GPL';
    if (/all rights reserved/i.test(t)) return 'proprietary';
    return 'unknown';
  }
  const raw = String(fm.license ?? '').trim();
  if (!raw) return 'unknown';
  if (/\bMIT\b/i.test(raw)) return 'MIT';
  if (/apache/i.test(raw)) return 'Apache-2.0';
  if (/\bBSD\b|3[- ]clause/i.test(raw)) return 'BSD';
  if (/\bGPL\b/i.test(raw)) return 'GPL';
  return 'unknown';
}

/** 正文里指向本技能目录内文件的相对链接，排除代码块里的示例与明显不是路径的写法。 */
function brokenLinks(dir, body) {
  const prose = body.replace(/```[\s\S]*?```/g, '').replace(/`[^`\n]*`/g, '');
  const broken = [];
  for (const [, target] of prose.matchAll(/\]\(([^)\s]+)\)/g)) {
    if (/^(https?:|mailto:|#)/.test(target)) continue;
    if (!/[./]/.test(target) || /[(){}$*]/.test(target)) continue;
    const clean = decodeURIComponent(target.split('#')[0]);
    if (!existsSync(path.resolve(dir, clean))) broken.push(target);
  }
  return broken;
}

function findPython() {
  const candidates = [
    process.env.BIO_MCP_PYTHON,
    path.join(homedir(), '.dsh', 'dsh-runtimes', 'dsh-primary-runtime', 'dependencies', 'python', process.platform === 'win32' ? 'python.exe' : 'bin/python3'),
    process.platform === 'win32' ? 'python' : 'python3',
  ].filter(Boolean);
  for (const py of candidates) {
    try {
      execFileSync(py, ['-c', 'pass']);
      return py;
    } catch {
      /* 下一个 */
    }
  }
  return undefined;
}

/** 只编译不执行：返回编译失败的 Python 文件。 */
function pythonCompileErrors(files) {
  if (files.length === 0) return new Map();
  const py = findPython();
  if (!py) throw new Error('找不到 python，无法检查脚本能否编译（可设 BIO_MCP_PYTHON）');
  const code =
    'import json,sys,warnings\nwarnings.simplefilter("ignore")\nbad={}\n' +
    'for f in json.load(sys.stdin):\n' +
    '    try: compile(open(f,encoding="utf-8").read(), f, "exec")\n' +
    '    except Exception as e: bad[f]=type(e).__name__+": "+str(e)[:120]\n' +
    'print(json.dumps(bad))';
  const out = execFileSync(py, ['-I', '-B', '-c', code], { input: JSON.stringify(files), encoding: 'utf8' });
  return new Map(Object.entries(JSON.parse(out)));
}

// ───────────────────────────────────────────────────────────── 采集
const entries = catalog.categories.flatMap((c) => c.skills.map((s) => ({ s, category: c.id })));
const allPy = [];
const facts = new Map();
for (const { s, category } of entries) {
  const dir = path.join(PKG, 'skills', s.path);
  const files = walk(dir);
  const md = readFileSync(path.join(dir, 'SKILL.md'), 'utf8');
  const { fm, body } = frontmatter(md);
  const codeText = files.filter((f) => CODE_EXT.test(f)).map(readText).join('\n');
  const docText = files.filter((f) => TEXT_EXT.test(f) && !CODE_EXT.test(f)).map(readText).join('\n');
  const py = files.filter((f) => f.endsWith('.py'));
  allPy.push(...py);
  const keys = [...new Set([...(codeText + docText).matchAll(/\b([A-Z][A-Z0-9_]{2,}_(?:API_KEY|TOKEN))\b/g)].map((m) => m[1]))]
    .filter((k) => !/^(YOUR|EXAMPLE|MY)_/.test(k))
    .sort();
  facts.set(s.name, {
    s,
    category,
    dir,
    fm,
    license: detectLicense(dir, fm),
    aiServices: AI_SERVICES.filter(([, re]) => re.test(codeText)).map(([n]) => n),
    seqServices: SEQUENCE_SERVICES.filter(([, re]) => re.test(docText) || re.test(codeText)).map(([n]) => n),
    keys,
    bodyLines: body.split('\n').filter((l) => l.trim()).length,
    bodyChars: body.replace(/\s+/g, '').length,
    hasResources: ['scripts', 'references', 'assets'].some((d) => existsSync(path.join(dir, d))),
    hasTests: files.some((f) => /[\\/]tests?[\\/]/.test(f) || /[\\/]test_[^\\/]+\.py$/.test(f)),
    broken: brokenLinks(dir, body),
    py,
    phi: PHI_CATEGORIES.has(category) || PHI_WORDS.test(String(fm.description ?? '')),
  });
}
const compileErrors = pythonCompileErrors(allPy);

// ───────────────────────────────────────────────────────────── 定级
const grades = new Map();
for (const [name, f] of facts) {
  const issues = [];
  if (PLACEHOLDER_NAME.test(name)) issues.push('占位式命名');
  for (const l of f.broken) issues.push(`失效链接 ${l}`);
  for (const p of f.py) if (compileErrors.has(p)) issues.push(`脚本无法编译 ${path.relative(f.dir, p)}`);
  if (f.bodyChars < 200 && !f.hasResources) issues.push(`正文只有 ${f.bodyChars} 字`);

  const flags = [];
  if (f.phi) flags.push('phi');
  if (f.seqServices.length) flags.push('egress-sequence');
  if (f.keys.length) flags.push('needs-key');
  if (f.license === 'unknown') flags.push('license-unknown');
  if (f.license === 'GPL') flags.push('license-copyleft');

  let tier;
  if (f.s.merged) tier = 'deprecated';
  else if (f.aiServices.length) tier = 'restricted';
  else if (issues.length) tier = 'experimental';
  else if (PERMISSIVE.test(f.license) && f.hasResources && (f.hasTests || f.bodyLines >= 40)) tier = 'core';
  else tier = 'standard';

  grades.set(name, {
    tier,
    license: f.license,
    ...(flags.length ? { flags } : {}),
    ...(f.aiServices.length ? { services: f.aiServices } : {}),
    ...(f.seqServices.length ? { sequenceServices: f.seqServices } : {}),
    ...(f.keys.length ? { keys: f.keys } : {}),
    ...(issues.length ? { issues } : {}),
  });
}

// ───────────────────────────────────────────────────────────── 写回 catalog
const next = JSON.parse(JSON.stringify(catalog));
for (const c of next.categories) for (const s of c.skills) s.grade = grades.get(s.name);
const nextText = JSON.stringify(next, null, 2) + '\n';

// ───────────────────────────────────────────────────────────── 合规报告
const TIER_LABEL = { core: '核心', standard: '标准', experimental: '实验', restricted: '受限', deprecated: '弃用（已并入）' };
const byTier = {};
for (const [name, g] of grades) (byTier[g.tier] ??= []).push(name);
const count = (pred) => [...grades.values()].filter(pred).length;
const licenseCount = {};
for (const g of grades.values()) licenseCount[g.license] = (licenseCount[g.license] ?? 0) + 1;
const listBy = (pred, fmt) =>
  entries
    .filter(({ s }) => pred(grades.get(s.name), s))
    .map(({ s, category }) => fmt(s, grades.get(s.name), category));

const report = [
  '# 合规与质量报告',
  '',
  '> 由 `node tools/grade.mjs` 根据仓库内容自动生成，不要手改。规则见 `tools/grade.mjs` 文件头。',
  '',
  '## 等级分布',
  '',
  '| 等级 | 数量 | 运行时处理 |',
  '|---|---|---|',
  `| 核心 | ${byTier.core?.length ?? 0} | 正常列出 |`,
  `| 标准 | ${byTier.standard?.length ?? 0} | 正常列出 |`,
  `| 实验 | ${byTier.experimental?.length ?? 0} | 目录描述前加〔实验〕，加载时要求额外核验并在报告中注明 |`,
  `| 受限 | ${byTier.restricted?.length ?? 0} | 目录描述前加〔受限〕，加载时要求先告知用户并取得同意 |`,
  `| 弃用（已并入） | ${byTier.deprecated?.length ?? 0} | 不进目录，原文由主技能的索引引用 |`,
  '',
  '## 受限：会把内容发送到生成式 AI 服务',
  '',
  ...listBy((g) => g.tier === 'restricted', (s, g) => `- \`${s.name}\`：${g.services.join('、')}`),
  '',
  '## 序列外发到公共计算服务（加载时提示，不降级）',
  '',
  ...listBy((g) => g.flags?.includes('egress-sequence'), (s, g) => `- \`${s.name}\`：${g.sequenceServices.join('、')}`),
  '',
  '## 需要第三方 API 密钥',
  '',
  ...listBy((g) => g.flags?.includes('needs-key'), (s, g) => `- \`${s.name}\`：${g.keys.join('、')}`),
  '',
  '## 涉及患者或受试者数据（加载时提示先去标识化）',
  '',
  `共 ${count((g) => g.flags?.includes('phi'))} 个，按分类与描述关键词自动识别。`,
  '',
  '## 实验级：质量缺陷',
  '',
  ...(byTier.experimental?.length
    ? listBy((g) => g.tier === 'experimental', (s, g) => `- \`${s.name}\`：${g.issues.join('；')}`)
    : ['当前没有。']),
  '',
  '## 许可证',
  '',
  '| 许可证 | 数量 |',
  '|---|---|',
  ...Object.entries(licenseCount)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => `| ${k === 'unknown' ? '不明' : k} | ${v} |`),
  '',
  '许可证不明的技能在公开分发前需逐个确认来源许可（见 THIRD_PARTY.md），确认后在 SKILL.md frontmatter 写 `license:` 或在目录放 LICENSE，再运行 `node tools/grade.mjs`。',
  '',
  '### copyleft',
  '',
  ...(listBy((g) => g.license === 'GPL', (s) => `- \`${s.name}\``).length
    ? listBy((g) => g.license === 'GPL', (s) => `- \`${s.name}\`：再分发需随附源码与许可证文本`)
    : ['当前没有。']),
  '',
  '### 许可证不明（按分类）',
  '',
  ...catalog.categories
    .map((c) => {
      const names = c.skills.filter((s) => grades.get(s.name).license === 'unknown').map((s) => s.name);
      return names.length ? `- ${c.label_zh}（${names.length}）：${names.map((n) => `\`${n}\``).join('、')}` : null;
    })
    .filter(Boolean),
  '',
].join('\n');

// ───────────────────────────────────────────────────────────── 写回 / 检查
const stale = [];
if (readFileSync(CATALOG, 'utf8') !== nextText) stale.push('picker/catalog.json');
if (!existsSync(REPORT) || readFileSync(REPORT, 'utf8') !== report) stale.push('COMPLIANCE.md');
const summary = Object.entries(TIER_LABEL)
  .map(([k, label]) => `${label} ${byTier[k]?.length ?? 0}`)
  .join(' / ');
if (CHECK) {
  if (stale.length) {
    console.error(`定级结果与仓库内容不一致，请运行 node tools/grade.mjs：${stale.join('、')}`);
    process.exit(1);
  }
  console.log(`定级结果是最新的（${summary}）`);
} else {
  if (stale.includes('picker/catalog.json')) writeFileSync(CATALOG, nextText);
  if (stale.includes('COMPLIANCE.md')) writeFileSync(REPORT, report);
  console.log(stale.length ? `已更新：${stale.join('、')}` : '无变化');
  console.log(summary);
}

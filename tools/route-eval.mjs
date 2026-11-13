/**
 * 技能 / MCP 工具路由评测。
 *
 * 问题：给 agent 一份技能目录和 MCP 工具清单，它能不能为一条真实请求选对技能与工具？
 * 用例在 eval/routing/cases.json（skills / tools 是「任一命中即算对」的可接受答案集）。
 *
 * 每条用例跑两种目录：
 *   full        全量模式：597 个技能全部可见
 *   specialist  该用例正确答案所在的专项模式（spec/modes.json），只看这个模式的技能
 * 两者的差距就是「先缩小候选」能带来多少准确率。
 *
 * 路由器：
 *   --router bm25   离线词法检索（中文双字 + 英文词），不需要网络；用来跑通流程、做下限基线
 *   --router llm    调 OpenAI 兼容的 Chat Completions 接口，让模型像在 DSH 里一样看目录选技能
 *                   环境变量：ROUTE_EVAL_API_KEY（或 DEEPSEEK_API_KEY）
 *                             ROUTE_EVAL_BASE_URL（默认 https://api.deepseek.com）
 *                             ROUTE_EVAL_MODEL（默认 deepseek-chat）
 *                   结果按「模型 + 提示词」哈希缓存在 eval/routing/.cache/，重跑不重复计费
 *
 * 用法：
 *   node tools/route-eval.mjs --validate                 只校验用例（自检用，不跑模型）
 *   node tools/route-eval.mjs --router bm25
 *   node tools/route-eval.mjs --router llm --mode both --concurrency 4
 *   node tools/route-eval.mjs --router llm --baseline eval/routing/results/<旧结果>.json
 *   其它：--mode full|specialist|both  --tag <tag>  --limit <n>  --out <file>  --python <path>
 *
 * 指标：
 *   skill@1   第一选择在可接受答案里
 *   skill@3   前三个里有可接受答案
 *   MRR       可接受答案的倒数排名均值
 *   invalid   模型给出的技能名不在目录里的比例（编造技能名）
 *   tool@3    前三个工具里有可接受工具
 */
import { readFileSync, writeFileSync, mkdirSync, existsSync } from 'node:fs';
import { createHash } from 'node:crypto';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { frontmatter } from '../shared/frontmatter.mjs';
import { loadMcpTools, loadDomains, domainOf } from '../shared/mcp-tools.mjs';

const PKG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const EVAL_DIR = path.join(PKG, 'eval', 'routing');
const DESC_LIMIT = 500; // 与目录截断一致
const TOP_K = 3;

// ───────────────────────────────────────────────────────────── 参数
const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && i + 1 < args.length && !args[i + 1].startsWith('--') ? args[i + 1] : dflt;
};
const flag = (name) => args.includes(`--${name}`);
const ROUTER = opt('router', 'bm25');
const MODE = opt('mode', 'both');
const TAG = opt('tag');
const LIMIT = Number(opt('limit', 0)) || Infinity;
const CONCURRENCY = Math.max(1, Number(opt('concurrency', 4)));
const BASELINE = opt('baseline');

// ───────────────────────────────────────────────────────────── 数据
const catalog = JSON.parse(readFileSync(path.join(PKG, 'picker', 'catalog.json'), 'utf8'));
const modes = JSON.parse(readFileSync(path.join(PKG, 'spec', 'modes.json'), 'utf8'));
const { cases: allCases } = JSON.parse(readFileSync(path.join(EVAL_DIR, 'cases.json'), 'utf8'));

const skills = [];
const skillCat = new Map();
/** 折叠技能 → 入口技能（catalog 里的 via）。折叠技能不进目录，选中入口即视为走对了路 */
const viaOf = new Map();
for (const c of catalog.categories) {
  for (const s of c.skills) {
    const { fm } = frontmatter(readFileSync(path.join(PKG, 'skills', s.path, 'SKILL.md'), 'utf8'));
    const desc = (fm.description ?? '').slice(0, DESC_LIMIT);
    skills.push({ name: s.name, desc, cat: c.id, via: s.via });
    skillCat.set(s.name, c.id);
    if (s.via) viaOf.set(s.name, s.via);
  }
}
const domains = loadDomains();
const modeOfCat = new Map(modes.flatMap((m) => m.cats.map((c) => [c, m])));

const tools = loadMcpTools(opt('python'));
const toolNames = new Set(tools.map((t) => t.name));

// ───────────────────────────────────────────────────────────── 校验
function validate() {
  const problems = [];
  const ids = new Set();
  const covered = new Set();
  for (const c of allCases) {
    if (ids.has(c.id)) problems.push(`重复 id：${c.id}`);
    ids.add(c.id);
    if (!c.query) problems.push(`${c.id}: 缺 query`);
    if (!Array.isArray(c.skills)) problems.push(`${c.id}: skills 必须是数组（不考察技能时写 []）`);
    for (const s of c.skills ?? []) {
      if (!skillCat.has(s)) problems.push(`${c.id}: 技能不存在 ${s}`);
      else covered.add(skillCat.get(s));
    }
    for (const t of c.tools ?? []) if (!toolNames.has(t)) problems.push(`${c.id}: MCP 工具不存在 ${t}`);
    if ((c.skills ?? []).length === 0 && !(c.tools ?? []).length) problems.push(`${c.id}: skills 与 tools 至少要考察一项`);
  }
  for (const c of catalog.categories) if (!covered.has(c.id)) problems.push(`分类 ${c.id} 没有任何用例`);
  return problems;
}

if (flag('validate')) {
  const problems = validate();
  if (problems.length) {
    console.log(problems.join('\n'));
    console.log(`\n结果：${problems.length} 个问题`);
    process.exit(1);
  }
  console.log(`结果：路由用例有效（${allCases.length} 条，覆盖 ${catalog.categories.length} 类，技能 ${skills.length} 个，MCP 工具 ${tools.length} 个）`);
  process.exit(0);
}
{
  const problems = validate();
  if (problems.length) {
    console.error(problems.join('\n'));
    process.exit(1);
  }
}

// ───────────────────────────────────────────────────────────── 目录视图
/**
 * 一条用例在某种模式下能看到的技能与 MCP 工具，与 picker / MCP 服务的实际行为一致：
 *   - 折叠技能（via）不进目录；范围内有折叠技能时，入口技能进目录
 *   - specialist 取第一个正确答案所在的专项模式，MCP 工具按该模式的 mcpDomains 过滤
 */
function viewOf(allowedCats, label, mcpDomains) {
  const listed = skills.filter((s) => allowedCats.has(s.cat) && !s.via);
  const names = new Set(listed.map((s) => s.name));
  for (const r of new Set(skills.filter((s) => allowedCats.has(s.cat) && s.via).map((s) => s.via))) {
    const router = skills.find((s) => s.name === r);
    if (router && !names.has(r)) listed.push(router);
  }
  const visibleTools = mcpDomains ? tools.filter((t) => mcpDomains.has(domainOf(t.name, domains))) : tools;
  return { skills: listed, tools: visibleTools, label };
}
const fullView = viewOf(new Set(catalog.categories.map((c) => c.id)), 'biomedical', null);
function visibleSkills(c, mode) {
  if (mode === 'full') return fullView;
  const anchor = (c.skills ?? [])[0];
  if (!anchor) return null; // 只考察工具的用例没有对应专项模式
  const m = modeOfCat.get(skillCat.get(anchor));
  return viewOf(new Set(m.cats), m.id, new Set(m.mcpDomains ?? Object.keys(domains)));
}

// ───────────────────────────────────────────────────────────── BM25
function tokenize(text) {
  const t = String(text).toLowerCase();
  const out = t.match(/[a-z0-9][a-z0-9.+-]*/g) ?? [];
  for (const run of t.match(/[一-鿿]+/g) ?? []) {
    if (run.length === 1) out.push(run);
    for (let i = 0; i + 1 < run.length; i++) out.push(run.slice(i, i + 2));
  }
  return out;
}
function bm25Index(docs) {
  const toks = docs.map((d) => tokenize(d));
  const df = new Map();
  for (const ts of toks) for (const w of new Set(ts)) df.set(w, (df.get(w) ?? 0) + 1);
  const avg = toks.reduce((a, t) => a + t.length, 0) / Math.max(1, toks.length);
  const N = docs.length;
  return (query, k = TOP_K) => {
    const q = [...new Set(tokenize(query))];
    const scores = toks.map((ts) => {
      const tf = new Map();
      for (const w of ts) tf.set(w, (tf.get(w) ?? 0) + 1);
      let s = 0;
      for (const w of q) {
        const f = tf.get(w);
        if (!f) continue;
        const idf = Math.log(1 + (N - df.get(w) + 0.5) / (df.get(w) + 0.5));
        s += (idf * f * 2.2) / (f + 1.2 * (0.25 + 0.75 * (ts.length / avg)));
      }
      return s;
    });
    return scores
      .map((s, i) => [s, i])
      .filter(([s]) => s > 0)
      .sort((a, b) => b[0] - a[0])
      .slice(0, k)
      .map(([, i]) => i);
  };
}
const bm25Cache = new Map();
const allNames = skills.map((s) => s.name);
/**
 * 「X 用 Y」这类分工子句是写给读者看的「不该选我的情况」，词法检索会把它当成命中，
 * 所以建索引时去掉点名了其他技能的子句，近似一个能读懂否定的读者。
 */
function routingText(s) {
  const clauses = s.desc.split(/(?<=[。；;])/);
  const kept = clauses.filter((cl) => !allNames.some((n) => n !== s.name && cl.includes(n)));
  return `${s.name.replace(/-/g, ' ')} ${kept.join('')}`;
}
function bm25Route(c, view) {
  if (!bm25Cache.has(view.label)) {
    bm25Cache.set(view.label, {
      skill: bm25Index(view.skills.map(routingText)),
      tool: bm25Index(view.tools.map((t) => `${t.name.replace(/_/g, ' ')} ${t.desc}`)),
    });
  }
  const idx = bm25Cache.get(view.label);
  return {
    skills: idx.skill(c.query).map((i) => view.skills[i].name),
    tools: idx.tool(c.query).map((i) => view.tools[i].name),
  };
}

// ───────────────────────────────────────────────────────────── LLM
const LLM = {
  key: process.env.ROUTE_EVAL_API_KEY || process.env.DEEPSEEK_API_KEY,
  base: (process.env.ROUTE_EVAL_BASE_URL || 'https://api.deepseek.com').replace(/\/+$/, ''),
  model: process.env.ROUTE_EVAL_MODEL || 'deepseek-chat',
};
function systemPrompt(view) {
  const skillLines = view.skills.map((s) => `- ${s.name}: ${s.desc}`).join('\n');
  const toolLines = view.tools.map((t) => `- mcp__biomedical__${t.name}: ${t.desc}`).join('\n');
  return [
    '你是 DeepSeek Harness「生物医学模式」里的研究助手。下面是你可以加载的技能目录和可以调用的 MCP 数据工具。',
    '',
    '<available_skills>',
    skillLines,
    '</available_skills>',
    '',
    '<available_mcp_tools>',
    toolLines,
    '</available_mcp_tools>',
    '',
    '收到用户请求后，在动手之前先决定：',
    `1. 最应该先加载哪些技能（最多 ${TOP_K} 个，按优先级排序）；不需要技能就给空数组。`,
    `2. 最应该先调用哪些 MCP 工具（最多 ${TOP_K} 个，按优先级，写不带 mcp__biomedical__ 前缀的工具名）；不需要就给空数组。`,
    '只能使用上面列表里出现过的名字，不要编造。',
    '只输出一个 JSON 对象，不要输出其它文字：{"skills": ["..."], "tools": ["..."]}',
  ].join('\n');
}
async function llmRoute(c, view) {
  if (!LLM.key) throw new Error('--router llm 需要环境变量 ROUTE_EVAL_API_KEY 或 DEEPSEEK_API_KEY');
  const body = {
    model: LLM.model,
    temperature: 0,
    response_format: { type: 'json_object' },
    messages: [
      { role: 'system', content: systemPrompt(view) },
      { role: 'user', content: c.query },
    ],
  };
  const cacheDir = path.join(EVAL_DIR, '.cache');
  const key = createHash('sha256').update(LLM.base).update(JSON.stringify(body)).digest('hex');
  const cacheFile = path.join(cacheDir, `${key}.json`);
  let content;
  if (existsSync(cacheFile)) {
    content = JSON.parse(readFileSync(cacheFile, 'utf8')).content;
  } else {
    for (let attempt = 0; ; attempt++) {
      const res = await fetch(`${LLM.base}/chat/completions`, {
        method: 'POST',
        headers: { 'content-type': 'application/json', authorization: `Bearer ${LLM.key}` },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        content = data.choices?.[0]?.message?.content ?? '';
        mkdirSync(cacheDir, { recursive: true });
        writeFileSync(cacheFile, JSON.stringify({ model: LLM.model, content, usage: data.usage ?? null }));
        break;
      }
      if ((res.status === 429 || res.status >= 500) && attempt < 4) {
        await new Promise((r) => setTimeout(r, 2000 * (attempt + 1)));
        continue;
      }
      throw new Error(`LLM 请求失败 HTTP ${res.status}: ${(await res.text()).slice(0, 300)}`);
    }
  }
  let parsed;
  try {
    parsed = JSON.parse(content.replace(/^```(?:json)?\s*|\s*```$/g, ''));
  } catch {
    parsed = {};
  }
  const clean = (xs) => (Array.isArray(xs) ? xs.map(String).map((x) => x.replace(/^mcp__biomedical__/, '')).slice(0, TOP_K) : []);
  return { skills: clean(parsed.skills), tools: clean(parsed.tools), raw: content };
}

// ───────────────────────────────────────────────────────────── 评测
const route = ROUTER === 'llm' ? llmRoute : ROUTER === 'bm25' ? async (c, v) => bm25Route(c, v) : null;
if (!route) {
  console.error(`未知路由器：${ROUTER}（可选 bm25 / llm）`);
  process.exit(1);
}
const modesToRun = MODE === 'both' ? ['full', 'specialist'] : [MODE];
const cases = allCases.filter((c) => !TAG || (c.tags ?? []).includes(TAG)).slice(0, LIMIT);

const jobs = [];
for (const c of cases) {
  for (const mode of modesToRun) {
    const view = visibleSkills(c, mode);
    if (view) jobs.push({ c, mode, view });
  }
}

const results = new Array(jobs.length);
let next = 0;
let done = 0;
async function worker() {
  while (next < jobs.length) {
    const i = next++;
    const { c, mode, view } = jobs[i];
    const visible = new Set(view.skills.map((s) => s.name));
    let out;
    try {
      out = await route(c, view);
    } catch (e) {
      out = { skills: [], tools: [], error: String(e?.message ?? e) };
      if (/需要环境变量/.test(out.error)) {
        console.error(out.error);
        process.exit(1);
      }
    }
    // 答案是折叠技能时，选中它的入口技能也算对（目录里本来就看不到折叠技能）
    const gold = new Set((c.skills ?? []).flatMap((s) => (viaOf.has(s) ? [s, viaOf.get(s)] : [s])));
    // 只考察本视图里看得到的工具（专项模式按 MCP 领域过滤后可能一个都不剩）
    const visibleToolNames = new Set(view.tools.map((t) => t.name));
    const goldTools = new Set((c.tools ?? []).filter((t) => visibleToolNames.has(t)));
    const rank = out.skills.findIndex((s) => gold.has(s));
    const tRank = out.tools.findIndex((t) => goldTools.has(t));
    results[i] = {
      id: c.id,
      mode,
      preset: view.label,
      tags: c.tags ?? [],
      category: gold.size ? skillCat.get(c.skills[0]) : null,
      predicted: out.skills,
      predictedTools: out.tools,
      gold: c.skills ?? [],
      goldTools: c.tools ?? [],
      skillScored: gold.size > 0,
      toolScored: goldTools.size > 0,
      hit1: gold.size > 0 && rank === 0,
      hit3: gold.size > 0 && rank >= 0,
      rr: gold.size > 0 && rank >= 0 ? 1 / (rank + 1) : 0,
      invalid: out.skills.filter((s) => !visible.has(s)),
      toolHit3: goldTools.size > 0 && tRank >= 0,
      invalidTools: out.tools.filter((t) => !visibleToolNames.has(t)),
      error: out.error ?? null,
    };
    done++;
    if (process.stderr.isTTY) process.stderr.write(`\r${done}/${jobs.length}`);
  }
}
await Promise.all(Array.from({ length: Math.min(CONCURRENCY, jobs.length) }, worker));
if (process.stderr.isTTY) process.stderr.write('\n');

// ───────────────────────────────────────────────────────────── 汇总
function summarize(rows) {
  const s = rows.filter((r) => r.skillScored);
  const t = rows.filter((r) => r.toolScored);
  const pct = (n, d) => (d ? Math.round((1000 * n) / d) / 10 : null);
  const predictedCount = s.reduce((a, r) => a + r.predicted.length, 0);
  return {
    n: s.length,
    skill1: pct(s.filter((r) => r.hit1).length, s.length),
    skill3: pct(s.filter((r) => r.hit3).length, s.length),
    mrr: s.length ? Math.round((1000 * s.reduce((a, r) => a + r.rr, 0)) / s.length) / 1000 : null,
    invalid: pct(s.reduce((a, r) => a + r.invalid.length, 0), predictedCount),
    nTools: t.length,
    tool3: pct(t.filter((r) => r.toolHit3).length, t.length),
    errors: rows.filter((r) => r.error).length,
  };
}
const byMode = Object.fromEntries(modesToRun.map((m) => [m, summarize(results.filter((r) => r.mode === m))]));
const groupBy = (key) => {
  const out = {};
  for (const m of modesToRun) {
    const rows = results.filter((r) => r.mode === m);
    const keys = new Set(rows.flatMap((r) => (key === 'tag' ? r.tags : [r[key]])).filter(Boolean));
    for (const k of keys) {
      out[k] ??= {};
      out[k][m] = summarize(rows.filter((r) => (key === 'tag' ? r.tags.includes(k) : r[key] === k)));
    }
  }
  return out;
};
const byCategory = groupBy('category');
const byTag = groupBy('tag');

// 混淆：正确答案 → 实际第一选择（只统计 top-1 错的）
const confusions = {};
for (const r of results.filter((x) => x.skillScored && !x.hit1)) {
  const k = `${r.gold[0]} → ${r.predicted[0] ?? '（未选）'}`;
  confusions[k] ??= { count: 0, cases: [] };
  confusions[k].count++;
  confusions[k].cases.push(`${r.id}/${r.mode}`);
}

const report = {
  router: ROUTER,
  model: ROUTER === 'llm' ? LLM.model : null,
  at: new Date().toISOString(),
  skills: skills.length,
  tools: tools.length,
  cases: cases.length,
  byMode,
  byCategory,
  byTag,
  confusions: Object.fromEntries(Object.entries(confusions).sort((a, b) => b[1].count - a[1].count)),
  results,
};

// ───────────────────────────────────────────────────────────── 输出
const fmt = (v, suffix = '%') => (v === null || v === undefined ? '—' : `${v}${suffix}`);
console.log(`\n路由评测 · router=${ROUTER}${report.model ? ` · model=${report.model}` : ''} · ${cases.length} 条用例 · 全量目录 ${fullView.skills.length} 个技能（另 ${viaOf.size} 个经入口加载）/ ${tools.length} MCP 工具\n`);
console.log('| 目录 | 用例 | skill@1 | skill@3 | MRR | 编造技能名 | 工具用例 | tool@3 |');
console.log('|---|---|---|---|---|---|---|---|');
for (const m of modesToRun) {
  const s = byMode[m];
  console.log(`| ${m === 'full' ? `全量（${fullView.skills.length}）` : '专项模式'} | ${s.n} | ${fmt(s.skill1)} | ${fmt(s.skill3)} | ${fmt(s.mrr, '')} | ${fmt(s.invalid)} | ${s.nTools} | ${fmt(s.tool3)} |`);
}
console.log('\n按标签（skill@1）：');
for (const [tag, v] of Object.entries(byTag).sort()) {
  console.log(`  ${tag.padEnd(8)} ${modesToRun.map((m) => `${m}=${fmt(v[m]?.skill1)}(n=${v[m]?.n ?? 0})`).join('  ')}`);
}
const worstCats = Object.entries(byCategory)
  .map(([k, v]) => [k, v.full?.skill1 ?? v.specialist?.skill1 ?? 0, v])
  .sort((a, b) => a[1] - b[1])
  .slice(0, 8);
console.log('\n最弱的分类（全量 skill@1）：');
for (const [k, s, v] of worstCats) console.log(`  ${k.padEnd(38)} ${fmt(s)}  (n=${v.full?.n ?? v.specialist?.n ?? 0})`);
console.log('\n最常见的选错（正确答案 → 实际首选）：');
for (const [k, v] of Object.entries(report.confusions).slice(0, 12)) console.log(`  ${String(v.count).padStart(2)}× ${k}`);
if (report.byMode.full?.errors || report.byMode.specialist?.errors) console.log(`\n注意：有调用出错的用例，见结果文件 results[].error`);

if (BASELINE) {
  const base = JSON.parse(readFileSync(path.resolve(BASELINE), 'utf8'));
  console.log(`\n与基线对比（${path.basename(BASELINE)}）：`);
  for (const m of modesToRun) {
    const a = base.byMode?.[m];
    const b = byMode[m];
    if (!a) continue;
    const d = (x, y) => (x === null || y === null ? '—' : `${y - x >= 0 ? '+' : ''}${Math.round((y - x) * 10) / 10}`);
    console.log(`  ${m}: skill@1 ${fmt(a.skill1)} → ${fmt(b.skill1)} (${d(a.skill1, b.skill1)})，skill@3 ${fmt(a.skill3)} → ${fmt(b.skill3)} (${d(a.skill3, b.skill3)})，tool@3 ${fmt(a.tool3)} → ${fmt(b.tool3)}`);
  }
  const baseHit = new Map(base.results.map((r) => [`${r.id}/${r.mode}`, r.hit1]));
  const regressed = results.filter((r) => r.skillScored && baseHit.get(`${r.id}/${r.mode}`) === true && !r.hit1);
  if (regressed.length) console.log(`  退步的用例：${regressed.map((r) => `${r.id}/${r.mode}`).join('、')}`);
}

const outFile =
  opt('out') ??
  path.join(EVAL_DIR, 'results', `${new Date().toISOString().slice(0, 10)}-${ROUTER}${report.model ? `-${report.model.replace(/[^\w.-]+/g, '_')}` : ''}.json`);
mkdirSync(path.dirname(outFile), { recursive: true });
writeFileSync(outFile, JSON.stringify(report, null, 2) + '\n');
console.log(`\n结果已写入 ${path.relative(PKG, outFile)}`);

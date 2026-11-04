/**
 * 会话级技能面板 · 离线验证（不需要浏览器）
 *
 * 用最小 React 替身跑组件、用假 ctx 跑 plugin.apply()、再单独跑 picker 的
 * GET/SET handler（真文件、假 request/response）。全部断言都对应一条真实故障：
 *
 *   - 模块 id ≠ 包名         → web boot: duplicate factory registration（2026-11-02 崩溃）
 *   - apply() 抛异常         → web boot: entry did not activate（启动报错弹窗）
 *   - 13 份 picker 抢路由    → webserver: duplicate exact route → 12 个预设挂载被拒
 *
 * 跑法：node tools/scope-test.mjs
 */
import { readFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PKG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const problems = [];
const notes = [];
const ok = (label, extra = '') => notes.push(`ok   ${label}${extra ? ' — ' + extra : ''}`);
const bad = (label, extra = '') => problems.push(`FAIL ${label}${extra ? ' — ' + extra : ''}`);

// ─────────────────────────────────────────────────────────── mini React
let CURRENT = null;

const shallow = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const sameDeps = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length && a.every((v, i) => Object.is(v, b[i]));

function makeReact() {
  return {
    createElement(type, props, ...children) {
      return { type, props: props ?? {}, children: children.flat(4).filter((x) => x !== null && x !== undefined && x !== false) };
    },
    useState(init) {
      const s = CURRENT;
      const k = s.i++;
      if (!(k in s.hooks)) s.hooks[k] = typeof init === 'function' ? init() : init;
      const set = (v) => {
        const next = typeof v === 'function' ? v(s.hooks[k]) : v;
        if (shallow(next, s.hooks[k])) return;
        s.hooks[k] = next;
        s.dirty = true;
      };
      return [s.hooks[k], set];
    },
    useRef(init) {
      const s = CURRENT;
      const k = s.i++;
      if (!(k in s.hooks)) s.hooks[k] = { current: init };
      return s.hooks[k];
    },
    useCallback(fn, deps) {
      const s = CURRENT;
      const k = s.i++;
      const prev = s.hooks[k];
      if (prev && sameDeps(prev.deps, deps)) return prev.fn;
      s.hooks[k] = { fn, deps };
      return fn;
    },
    useMemo(fn, deps) {
      const s = CURRENT;
      const k = s.i++;
      const prev = s.hooks[k];
      if (prev && sameDeps(prev.deps, deps)) return prev.value;
      const value = fn();
      s.hooks[k] = { value, deps };
      return value;
    },
    useEffect(fn, deps) {
      const s = CURRENT;
      const k = s.i++;
      const prev = s.hooks[k];
      if (!prev || !sameDeps(prev.deps, deps)) s.effects.push(fn);
      s.hooks[k] = { deps };
    },
  };
}

const sleep = (ms = 0) => new Promise((r) => setTimeout(r, ms));
const makeSlot = () => ({ hooks: [], effects: [], i: 0, dirty: false });

/** 渲染一个组件直到不再变化（含 effect 触发的异步 setState）。 */
async function render(slot, Component, props, { rounds = 14 } = {}) {
  let out;
  let idle = 0;
  for (let r = 0; r < rounds; r++) {
    slot.i = 0;
    slot.dirty = false;
    slot.effects = [];
    CURRENT = slot;
    try {
      out = Component(props);
    } catch (e) {
      throw new Error(`render threw: ${e && e.stack ? e.stack.split('\n').slice(0, 4).join(' | ') : e}`);
    } finally {
      CURRENT = null;
    }
    const effects = slot.effects;
    slot.effects = [];
    for (const fn of effects) fn();
    await sleep(8);
    const changed = slot.dirty || effects.length > 0;
    slot.dirty = false;
    if (!changed) {
      if (++idle >= 2) break;
    } else idle = 0;
  }
  slot.i = 0;
  slot.dirty = false;
  slot.effects = [];
  CURRENT = slot;
  try {
    out = Component(props);
  } finally {
    CURRENT = null;
  }
  return out;
}

function walk(node, visit) {
  if (node === null || node === undefined || node === false) return;
  if (Array.isArray(node)) {
    node.forEach((n) => walk(n, visit));
    return;
  }
  if (typeof node !== 'object') {
    visit(node);
    return;
  }
  visit(node);
  if (node.children) node.children.forEach((n) => walk(n, visit));
}

const textOf = (node) => {
  const parts = [];
  walk(node, (n) => {
    if (typeof n === 'string') parts.push(n);
  });
  return parts.join('').replace(/\s+/g, ' ');
};

// ─────────────────────────────────────────────────────────── 假环境
const store = new Map();
const win = {
  localStorage: {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, v),
    removeItem: (k) => store.delete(k),
  },
  listeners: {},
  addEventListener(type, fn) {
    (this.listeners[type] ??= []).push(fn);
  },
  removeEventListener(type, fn) {
    this.listeners[type] = (this.listeners[type] ?? []).filter((f) => f !== fn);
  },
  innerWidth: 1440,
  innerHeight: 900,
};
win.window = win;
globalThis.window = win;

const calls = [];
let nextPayload = null;
globalThis.fetch = async (url, init = {}) => {
  calls.push({ url: String(url), init });
  const body = typeof nextPayload === 'function' ? nextPayload(String(url), init) : nextPayload;
  return { ok: true, status: 200, json: async () => body };
};

// ─────────────────────────────────────────────────────────── 载入 client.js
const captured = [];
win.__ModuleLoader__ = { load: (def) => captured.push(def) };

const React = makeReact();
await import(pathToFileURL(path.join(PKG, 'client.js')).href);
const def = captured[0];
if (!def) bad('client.js 没有调用 __ModuleLoader__.load');
else if (def.id !== 'dsh-biomedical-preset') bad('模块 id 与包名不一致', def.id);
else ok('模块 id = 包名', def.id);

const plugin = def.factory((name) => {
  if (name === 'react') return React;
  throw new Error(`unexpected require(${name})`);
});
if (!plugin || typeof plugin.apply !== 'function') bad('factory 没返回 { apply }');
else ok('factory 返回 apply', `inject=${JSON.stringify(plugin.inject)}`);

// ─────────────────────────────────────────────────────────── 跑 apply()
const registrations = [];
const fakeCtx = {
  remote: { settings: { describe: async () => ({ ok: true, value: { namespaces: [] } }), mutate: async () => ({ ok: true }) } },
  slots: {
    inject(_key, fn) {
      return fn();
    },
    register(options, component, extra) {
      registrations.push({ options, component, extra });
      return () => {};
    },
  },
};
const warnings = [];
const origWarn = console.warn;
console.warn = (...a) => warnings.push(a.map(String).join(' '));
try {
  plugin.apply(fakeCtx);
  ok('apply() 未抛异常');
} catch (e) {
  bad('apply() 抛异常', String(e && e.message));
}

const byId = new Map(registrations.map((r) => [r.options.id, r]));
for (const [id, slot] of [
  ['biomedical-skills', 'settings.section'],
  ['biomedical-scope-entry', 'conversation.input.right'],
  ['biomedical-scope-panel', 'shell.overlay'],
]) {
  const r = byId.get(id);
  if (!r) bad(`缺少注册 ${id}`);
  else if (r.options.name !== slot) bad(`${id} 挂错 slot`, r.options.name);
  else ok(`注册 ${id} → ${slot}`, `order=${r.options.order}`);
}
const entryReg = byId.get('biomedical-scope-entry');
if (entryReg && typeof entryReg.extra?.inject !== 'function') bad('入口缺 inject(sessionId)');
else if (entryReg) ok('入口 inject(sessionId) 可用', JSON.stringify(entryReg.extra.inject('sess-abc')));

// ── 加固：register / slots.inject 抛错时 apply 不能炸
{
  const boom = {
    remote: {},
    slots: {
      inject(_k, fn) {
        return fn();
      },
      register() {
        throw new Error('simulated duplicate entry id');
      },
    },
  };
  warnings.length = 0;
  try {
    plugin.apply(boom);
    if (warnings.length === 0) bad('register 抛错时没有 warn');
    else ok('register 抛错 → apply 存活并 warn', `${warnings.length} 条`);
  } catch (e) {
    bad('register 抛错把 apply 带崩了', String(e?.message ?? e));
  }
}
{
  const boom = {
    remote: {},
    slots: {
      inject() {
        throw new Error('simulated inject failure');
      },
      register() {
        return () => {};
      },
    },
  };
  try {
    plugin.apply(boom);
    ok('slots.inject 抛错 → apply 存活');
  } catch (e) {
    bad('slots.inject 抛错把 apply 带崩了', String(e?.message ?? e));
  }
}
console.warn = origWarn;

// ─────────────────────────────────────────────────────────── 分类快照（来自 catalog）
const catalog = JSON.parse(await readFile(path.join(PKG, 'picker', 'catalog.json'), 'utf8'));
const live = {
  ok: true,
  sessionId: 'sess-abc',
  categories: catalog.categories.map((c) => ({ id: c.id, label: c.label_zh, count: c.skills.length })),
  enabled: null,
  presetOnly: null,
};
if (live.categories.length !== 34) bad('catalog 分类数不是 34', String(live.categories.length));

// ── 1) 入口按钮 + 关闭时不渲染
const ScopeEntry = entryReg?.component;
const ScopePanel = byId.get('biomedical-scope-panel')?.component;
const panelSlot = makeSlot();
nextPayload = live;
if ((await render(panelSlot, ScopePanel, {})) !== null) bad('面板关闭时应返回 null');
else ok('面板关闭时不渲染');

const entrySlot = makeSlot();
const entryTree = await render(entrySlot, ScopeEntry, entryReg?.extra?.inject('sess-abc'));
const entryBtn = [];
walk(entryTree, (n) => {
  if (n.type === 'button') entryBtn.push(n);
});
if (entryBtn.length !== 1) bad('入口按钮数量异常', String(entryBtn.length));
else if (!/技能/.test(textOf(entryBtn[0]))) bad('入口按钮没有文字', textOf(entryBtn[0]));
else ok('入口按钮渲染', textOf(entryBtn[0]));

entryBtn[0]?.props?.onClick?.({});
const openedTree = await render(entrySlot, ScopeEntry, entryReg?.extra?.inject('sess-abc'));
const openedBtn = [];
walk(openedTree, (n) => {
  if (n.type === 'button') openedBtn.push(n);
});
if (!openedBtn[0]?.props?.['aria-expanded']) bad('点击后 aria-expanded 没变 true');
else ok('点击入口 → 面板打开');

// ── 2) 面板主体
calls.length = 0;
const panelTree = await render(panelSlot, ScopePanel, {});
const switches = [];
walk(panelTree, (n) => {
  if (n.props?.role === 'switch') switches.push(n);
});
const got = calls.find((c) => c.url.includes('/bio-skills/get'));
if (!got) bad('没有请求 /bio-skills/get', calls.map((c) => c.url).join(','));
else if (!got.url.includes('sessionId=sess-abc')) bad('请求没带 sessionId', got.url);
else ok('GET 带 sessionId', got.url);

const panelText = textOf(panelTree);
const EXPECT = [
  '测序与变异检出',
  '基因组组装与群体遗传',
  '临床解读与精准医学',
  '肿瘤与免疫组学',
  '转录组与差异表达',
  '单细胞与空间组学',
  '表观遗传与调控',
  '蛋白组与代谢组',
  '结构与药物设计',
  '微生物组与宏基因组',
  '影像·细胞表型·法医',
  '文献·写作与工程',
];
const missing = EXPECT.filter((t) => !panelText.includes(t));
if (missing.length > 0) bad('面板缺大类标题', missing.join(' / '));
else ok('12 大类全部渲染');
if (switches.length !== 12) bad('大类开关数量不是 12', String(switches.length));
else ok('12 个大类开关');
if (!/≈\d+(\.\d)?k token/.test(panelText)) bad('没有 token 估算');
else ok('token 估算显示', (panelText.match(/≈\d+(\.\d)?k token/) ?? [''])[0]);
if (!/只影响本会话/.test(panelText)) bad('缺少范围说明');
else ok('范围说明存在');

// ── 3) 点一个大类开关 → POST
calls.length = 0;
nextPayload = (url) => (url.includes('/bio-skills/set') ? { ok: true, sessionId: 'sess-abc', enabled: ['x'] } : live);
await switches[0]?.props?.onClick?.({});
await sleep(5);
const post = calls.find((c) => c.url.includes('/bio-skills/set') && c.init?.method === 'POST');
if (!post) bad('切换大类没有发起 POST');
else {
  const body = JSON.parse(post.init.body);
  if (body.sessionId !== 'sess-abc') bad('POST 缺 sessionId', post.init.body);
  else if (!Array.isArray(body.enabled)) bad('POST enabled 不是数组');
  else if (body.enabled.includes('sequencing-qc-alignment')) bad('关掉大类后分类还在 enabled 里');
  else ok('POST /bio-skills/set', `enabled=${body.enabled.length} 类`);
}

// ── 4) 新 Host 形状（effective + source）
nextPayload = {
  ok: true,
  sessionId: 'sess-abc',
  categories: live.categories,
  enabled: ['proteomics'],
  effective: ['proteomics'],
  source: 'session',
  presetOnly: null,
  instances: 13,
};
const tree2 = await render(makeSlot(), ScopePanel, {});
const t2 = textOf(tree2);
if (!t2.includes('本会话自定义')) bad('没有显示「本会话自定义」');
else ok('source=session 文案正确');
const sw2 = [];
walk(tree2, (n) => {
  if (n.props?.role === 'switch') sw2.push(n);
});
const full = sw2.filter((s) => s.props['aria-checked'] === 'true').length;
const mixed = sw2.filter((s) => s.props['aria-checked'] === 'mixed').length;
if (full !== 0 || mixed !== 1) bad('只有 proteomics 开时三态不对', `all=${full} some=${mixed}`);
else ok('三态开关按 effective 回显（部分选 = mixed）');

nextPayload = {
  ok: true,
  sessionId: 'sess-abc',
  categories: live.categories,
  enabled: ['proteomics', 'metabolomics-lipidomics'],
  effective: ['proteomics', 'metabolomics-lipidomics'],
  source: 'session',
  presetOnly: null,
  instances: 13,
};
const tree2b = await render(makeSlot(), ScopePanel, {});
const sw2b = [];
walk(tree2b, (n) => {
  if (n.props?.role === 'switch') sw2b.push(n);
});
const full2 = sw2b.filter((s) => s.props['aria-checked'] === 'true').length;
if (full2 !== 1) bad('整组全开时全开大类数不为 1', String(full2));
else ok('整组全开 → 大类显示已开');

// ── 5) Esc 关闭
const keyHandlers = win.listeners.keydown ?? [];
if (keyHandlers.length === 0) bad('没有注册 Esc 监听');
else {
  keyHandlers[0]({ key: 'Escape' });
  if ((await render(panelSlot, ScopePanel, {})) !== null) bad('Esc 没关掉面板');
  else ok('Esc 关闭面板');
}

// ── 6) ✕ 按钮必须能关（实测 bug：标题栏 setPointerCapture 抢走 pointerup，按钮收不到 click）
{
  openedBtn[0]?.props?.onClick?.({});
  nextPayload = live;
  const treeX = await render(makeSlot(), ScopePanel, {});
  const closeBtn = [];
  walk(treeX, (n) => {
    if (n.type === 'button' && textOf(n).trim() === '✕') closeBtn.push(n);
  });
  if (closeBtn.length !== 1) bad('找不到 ✕ 按钮', String(closeBtn.length));
  else {
    // 按钮区必须在 pointerdown 阶段就切断冒泡，否则标题栏会 setPointerCapture
    let stopped = false;
    const bar = [];
    walk(treeX, (n) => {
      if (n.props?.onPointerDown && !n.props?.onPointerMove) bar.push(n);
    });
    if (bar.length === 0) bad('按钮区没有 onPointerDown 拦截');
    else {
      bar[0].props.onPointerDown({ stopPropagation: () => (stopped = true) });
      if (!stopped) bad('按钮区没有 stopPropagation');
      else ok('按钮区拦截 pointerdown（不再被拖动抢走）');
    }
    closeBtn[0].props.onClick({});
    if ((await render(panelSlot, ScopePanel, {})) !== null) bad('点 ✕ 没关掉面板');
    else ok('点 ✕ 关闭面板');
  }
}

// ── 7) 拖动：空白处可拖；从按钮/非左键按下不拖
openedBtn[0]?.props?.onClick?.({});
nextPayload = live;
{
  const slotD = makeSlot();
  const treeD = await render(slotD, ScopePanel, {});
  let captureCalls = 0;
  const heads = [];
  walk(treeD, (n) => {
    if (n.props?.onPointerDown && n.props?.onPointerMove) heads.push(n);
  });
  if (heads.length !== 1) bad('拖动把手数量异常', String(heads.length));
  else {
    const headNode = heads[0];
    const ev = (extra = {}) => ({
      clientX: 300,
      clientY: 300,
      pointerId: 1,
      button: 0,
      currentTarget: { setPointerCapture: () => (captureCalls += 1) },
      target: { closest: () => null },
      ...extra,
    });

    // 空白处：应该开始拖
    headNode.props.onPointerDown(ev());
    if (captureCalls !== 1) bad('空白处按下没有开始拖动');
    else ok('空白处 pointerdown 开始拖动');
    headNode.props.onPointerMove({ clientX: 340, clientY: 330 });
    headNode.props.onPointerUp({});
    await sleep(5);
    const saved = store.get('dsh-biomedical-scope-panel');
    if (!saved) bad('拖动后没写 localStorage');
    else ok('拖动位置已记住', saved);

    // 从按钮上按下：不应该拖（这是 ✕ 失效的根因）
    captureCalls = 0;
    store.delete('dsh-biomedical-scope-panel');
    headNode.props.onPointerDown(ev({ target: { closest: () => ({ tagName: 'BUTTON' }) } }));
    if (captureCalls !== 0) bad('从按钮上按下仍开始了拖动');
    else ok('从按钮上按下不拖动');

    // 非左键：不拖
    captureCalls = 0;
    headNode.props.onPointerDown(ev({ button: 2 }));
    if (captureCalls !== 0) bad('右键也开始了拖动');
    else ok('非左键不拖动');
  }
}

// ─────────────────────────────────────────────────────────── picker：13 实例共存
const pickerUrl = pathToFileURL(path.join(PKG, 'picker', 'index.js')).href;
const picker = await import(pickerUrl);

function makeWebServer() {
  const routes = new Map();
  return {
    routes,
    register(spec) {
      if (routes.has(spec.path)) throw new Error(`webserver: duplicate ${spec.kind} route "${spec.path}"`);
      routes.set(spec.path, spec.handler);
      return () => routes.delete(spec.path);
    },
  };
}
function makeCtx({ webServer, sid = 'sess-abc' }) {
  const disposers = [];
  const ctx = {
    logger: { info() {}, warn() {} },
    effect(fn) {
      const dispose = fn();
      disposers.push(dispose);
      return dispose;
    },
    inject(_deps, cb) {
      const dispose = cb({ agents: { currentInitiator: () => ({ id: sid }) }, webServer });
      if (typeof dispose === 'function') disposers.push(dispose);
      return dispose;
    },
    skills: {
      registerProvider(create) {
        ctx._control = {
          invalidate() {
            ctx.invalidated = (ctx.invalidated ?? 0) + 1;
          },
        };
        ctx._provider = create(ctx._control);
        return () => {};
      },
    },
    teardown() {
      for (const dispose of [...disposers].reverse()) {
        try {
          dispose?.();
        } catch {
          /* 卸载不应抛 */
        }
      }
    },
  };
  return ctx;
}
function mount(config, webServer, mod = picker) {
  const ctx = makeCtx({ webServer });
  let thrown;
  try {
    mod.apply(ctx, config);
  } catch (e) {
    thrown = e;
  }
  return { ctx, thrown };
}

const shared = globalThis[Symbol.for('dsh.biomedical.picker.v1')];

const ws = makeWebServer();
const a = mount({}, ws);
if (a.thrown) bad('实例 1 apply 抛异常', String(a.thrown.message));
else ok('实例 1（全量）apply 无异常');
if (ws.routes.size !== 3) bad('路由没注册全', [...ws.routes.keys()].join(','));
else ok('实例 1 注册了路由', [...ws.routes.keys()].join(' + '));

async function callGet(url) {
  let out;
  await ws.routes.get('/bio-skills/get')({ method: 'GET', url }, { writeHead() {}, end: (b) => (out = b) });
  return JSON.parse(out);
}
async function callSet(payload) {
  let out;
  await ws.routes.get('/bio-skills/set')(
    {
      method: 'POST',
      async *[Symbol.asyncIterator]() {
        yield Buffer.from(JSON.stringify(payload));
      },
    },
    { writeHead() {}, end: (b) => (out = b) },
  );
  return JSON.parse(out);
}

const g1 = await callGet('/bio-skills/get?sessionId=probe');
if (!Array.isArray(g1.categories) || g1.categories.length !== 34) bad('GET categories 不是 34 类', String(g1.categories?.length));
else ok('GET categories', '34 类');
if (g1.source !== 'profile') bad('全量实例生效时 source 应为 profile', g1.source);
else ok('全量模式 source=profile', `effective=${g1.effective.length}`);

const more = [];
for (let i = 0; i < 12; i++) {
  const r = mount({ only: ['proteomics', 'metabolomics-lipidomics'] }, ws);
  if (r.thrown) bad(`实例 ${i + 2} apply 抛异常`, String(r.thrown.message));
  more.push(r);
}
if (more.every((r) => !r.thrown)) ok('12 个专项实例并发挂载全部无异常', `共 ${shared.instances.size} 个实例`);
if (shared.routeCollisions < 12) bad('重复注册没有被计数', String(shared.routeCollisions));
else ok('重复注册被复用而非抛错', `collisions=${shared.routeCollisions}`);
if (ws.routes.size !== 3) bad('多实例后路由数量异常', String(ws.routes.size));
else ok('多实例后路由仍是 2 条（引用计数）');

const g2 = await callGet('/bio-skills/get?sessionId=probe');
if (g2.instances !== 13) bad('instances 计数不对', String(g2.instances));
else ok('GET 回报实例数', String(g2.instances));

await callSet({ sessionId: 'sess-abc', enabled: ['proteomics', 'metabolomics-lipidomics'] });
const g3 = await callGet('/bio-skills/get?sessionId=sess-abc');
if (g3.source !== 'session' || g3.effective.length !== 2) bad('会话覆盖没生效', JSON.stringify(g3.effective));
else ok('会话覆盖生效', `effective=${g3.effective.join(',')}`);
if (!a.ctx.invalidated || !more[0].ctx.invalidated) bad('invalidate 没有广播到所有实例', `a=${a.ctx.invalidated} b=${more[0].ctx.invalidated}`);
else ok('invalidate 广播到每个实例', `${a.ctx.invalidated} / ${more[0].ctx.invalidated}`);

const listed = await more[0].ctx._provider.list();
const catsInList = new Set(listed.map((s) => s.metadata?.category));
if (catsInList.size !== 2) bad('list() 没按会话覆盖过滤', [...catsInList].join(','));
else ok('list() 按会话覆盖过滤', `${listed.length} 个技能 / ${[...catsInList].join(',')}`);

await callSet({ sessionId: 'sess-abc', enabled: null });
const g4 = await callGet('/bio-skills/get?sessionId=sess-abc');
if (g4.enabled !== null) bad('覆盖清除失败', JSON.stringify(g4.enabled));
else ok('覆盖可清除', `source=${g4.source}`);

// 模块二次加载：SHARED 必须还是同一份
{
  const picker2 = await import(`${pickerUrl}?second=1`);
  const before = shared.instances.size;
  const ws3 = makeWebServer();
  const r = mount({}, ws3, picker2);
  if (r.thrown) bad('二次加载的模块 apply 抛异常', String(r.thrown.message));
  else if (shared.instances.size !== before + 1) bad('二次加载没有共享 SHARED', `${before} → ${shared.instances.size}`);
  else ok('模块二次加载仍共享 SHARED', `instances=${shared.instances.size}`);
  if (ws3.routes.size !== 0) bad('二次加载的模块抢先注册了路由（应复用）', String(ws3.routes.size));
  else ok('二次加载的模块不重复注册路由');
}

// 全新 SHARED：单进程从零开始的引用计数与「路由被占」
{
  const KEY = Symbol.for('dsh.biomedical.picker.v1');
  delete globalThis[KEY];
  const picker3 = await import(`${pickerUrl}?third=1`);
  const fresh = globalThis[KEY];
  if (!fresh || fresh === shared) bad('无法拿到全新的 SHARED');
  else ok('拿到全新 SHARED（模拟进程重启）', `instances=${fresh.instances.size}`);

  const ws4 = makeWebServer();
  const r1 = mount({}, ws4, picker3);
  const r2 = mount({}, ws4, picker3);
  const count = ws4.routes.size;
  r2.ctx.teardown();
  const afterOne = ws4.routes.size;
  r1.ctx.teardown();
  const afterAll = ws4.routes.size;
  if (count !== 3) bad('引用计数初值不对', String(count));
  else if (afterOne !== 3) bad('卸载一个实例就把路由带走了', String(afterOne));
  else if (afterAll !== 0) bad('全部卸载后路由没注销', String(afterAll));
  else ok('引用计数：卸载最后一个才注销路由');
  if (fresh.instances.size !== 0) bad('卸载后实例没清干净', String(fresh.instances.size));
  else ok('卸载后实例登记清空');

  const occupied = makeWebServer();
  occupied.register({ kind: 'exact', path: '/bio-skills/get' });
  const r3 = mount({}, occupied, picker3);
  if (r3.thrown) bad('路由被占时 apply 抛异常了', String(r3.thrown.message));
  else if (!fresh.routeError) bad('路由被占却没有记录 routeError');
  else ok('路由被占 → apply 存活并记录原因', String(fresh.routeError).slice(0, 48));
  if (!r3.ctx._provider) bad('路由失败时技能 provider 没注册');
  else ok('路由失败时技能 provider 仍注册');
}

console.log('\n' + notes.join('\n'));
if (problems.length > 0) {
  console.log('\n' + problems.join('\n'));
  console.log(`\n结果：${notes.length} 通过，${problems.length} 失败`);
  process.exit(1);
}
console.log(`\n结果：全部 ${notes.length} 项通过`);

/**
 * SKILL.md frontmatter 的极简解析（picker 与路由评测共用，保证评测看到的描述
 * 就是模型在技能目录里看到的描述）。只依赖 JS 内置能力。
 *
 * 支持：`key: value`、续行、`|` / `>` 块标量及其 `-` / `+` 修饰（`>-`、`|+` 等）。
 */
const BLOCK_INDICATOR = /^[|>][+-]?$/;

export function frontmatter(text) {
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
    let v = fm[k].trim();
    // 块标量：指示符本身不是内容（以前 `>-` 会原样留在描述开头）
    const first = v.split(/\s+/, 1)[0];
    if (BLOCK_INDICATOR.test(first)) v = v.slice(first.length);
    v = v.trim().replace(/^["']|["']$/g, '').trim();
    fm[k] = v;
  }
  return { fm, body: text.slice(m[0].length).replace(/^\r?\n/, '') };
}

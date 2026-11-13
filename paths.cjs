'use strict';
/**
 * 包内路径（CommonJS，供 cordis.patch.yml 里的 `!!js` 表达式同步 require）。
 *
 * patch 里不能写死本机绝对路径：别人装上后路径不存在，bio-mcp 又是
 * failOnStartupError: false，51 个数据工具会静默消失。`!!js` 表达式不能用
 * await import()，所以这里用 .cjs，让表达式经 createRequire 按包名同步解析：
 *
 *   process.getBuiltinModule('node:module')
 *     .createRequire(<profile 目录>/)('dsh-biomedical-preset/paths').mcpScript
 *
 * 包名解析与 Loader 加载 `dsh-biomedical-preset/picker` 走的是同一条路径；
 * link: 安装时解析结果是真实路径（开发目录），同样正确。
 */
const { join } = require('node:path');

const root = __dirname;

module.exports = {
  root,
  mcpDir: join(root, 'mcp'),
  mcpScript: join(root, 'mcp', 'biomedical_mcp.py'),
  skillsDir: (domain) => join(root, 'skills', domain),
};

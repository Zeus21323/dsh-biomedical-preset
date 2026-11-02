/**
 * 包根入口（Host 半）。
 *
 * 本包在 profile 里以「裸包名」作为 Loader 行的 specifier —— 这是必须的：
 * dsh-client-modules 的 exactPackageSpecifier() 只接受不含 `/` 的裸包名，
 * 带子路径（如 `dsh-biomedical-preset/settings`）的 entry 永远不会被当作
 * client 包，`dsh.client` 声明的浏览器半就加载不出来。
 *
 * 所以 Host 逻辑（34 个开关的 Config + 镜像写入）在 settings/ 里实现，
 * 这里只做转出；浏览器半在包根的 client.js。
 */
export { name, apply } from './settings/index.js';
export { Config } from './settings/config.mjs';

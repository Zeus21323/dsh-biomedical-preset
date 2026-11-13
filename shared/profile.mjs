/**
 * 定位当前 DSH profile 目录（picker 读开关文件、设置页写开关文件、config.mjs 解析
 * schemastery 都要用）。只依赖 node 内置模块。
 *
 * 不能写死某台机器的路径。按可靠程度依次尝试：
 *   1. 插件上下文的 profileContext 服务（Host 以 profile 启动时一定有）；
 *   2. DSH_PROFILE_DIR 环境变量（DSH 只保证在 shell 调用里有，Host 进程不一定）；
 *   3. $DSH_HOME（缺省 ~/.dsh）/profiles/$DSH_PROFILE（缺省 desktop）。
 * 只认存在 package.json 的目录。
 */
import { existsSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';

function isProfileDir(dir) {
  return typeof dir === 'string' && dir.length > 0 && existsSync(join(dir, 'package.json'));
}

/** 不依赖插件上下文的候选目录（模块顶层也能用）。 */
export function profileDirCandidates() {
  const home = process.env.DSH_HOME || join(homedir(), '.dsh');
  return [process.env.DSH_PROFILE_DIR, join(home, 'profiles', process.env.DSH_PROFILE || 'desktop')];
}

/**
 * @param {any} [ctx] 插件上下文；给了就优先读 profileContext.dir
 * @returns {string | undefined}
 */
export function resolveProfileDir(ctx) {
  let fromCtx;
  try {
    fromCtx = ctx?.get?.('profileContext')?.dir;
  } catch {
    fromCtx = undefined;
  }
  for (const dir of [fromCtx, ...profileDirCandidates()]) {
    if (isProfileDir(dir)) return dir;
  }
  return undefined;
}

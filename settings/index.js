/**
 * Host half of the biomedical skill settings page.
 *
 * Owns the Config schema (34 category switches, generated into ./config.mjs),
 * registers this instance's settings-page policy, and mirrors the live values
 * to a JSON file that the preset's provider reads on every `list()`.
 */
import { writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { Config } from './config.mjs';

export const name = 'biomedical-skill-settings';
export { Config };

const FILE = 'biomedical-skills.json';

/** Host processes do not always export DSH_PROFILE_DIR; fall back to the known profile. */
function profileDir() {
  const candidates = [process.env.DSH_PROFILE_DIR, 'C:/Users/20735/.dsh/profiles/desktop'];
  for (const dir of candidates) {
    if (dir && existsSync(join(dir, 'package.json'))) return dir;
  }
  return undefined;
}

export function apply(ctx, config = {}) {
  const write = async () => {
    const dir = profileDir();
    if (!dir) return;
    try {
      await writeFile(join(dir, FILE), JSON.stringify(config ?? {}, null, 0), 'utf8');
    } catch {
      /* 设置页只是镜像开关；写失败不应影响插件本身 */
    }
  };
  ctx.effect(() => {
    void write();
    return () => {};
  }, 'biomedical-skill-settings: mirror switches');

  // 主动声明本实例的设置页策略：没有这一步，settings.describe() 不会列出本行。
  const settings = ctx.get('settings');
  if (settings !== undefined) {
    ctx.effect(() => settings.configure({ auto: true }), 'biomedical-skill-settings: page policy');
  }
}

/**
 * 读取 MCP 服务的工具清单与领域定义（评测、lint 共用）。只依赖 node 内置模块。
 * 工具清单直接调 mcp/biomedical_mcp.py 的 tool_specs()，保证与服务实际暴露的一致。
 */
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { homedir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const PKG = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MCP = path.join(PKG, 'mcp', 'biomedical_mcp.py');

export function loadDomains() {
  return JSON.parse(readFileSync(path.join(PKG, 'mcp', 'domains.json'), 'utf8'));
}

export function domainOf(name, domains = loadDomains()) {
  for (const [id, d] of Object.entries(domains)) if (d.prefixes.some((p) => name.startsWith(p))) return id;
  return undefined;
}

export function loadMcpTools(python) {
  const candidates = [
    python,
    process.env.BIO_MCP_PYTHON,
    path.join(homedir(), '.dsh', 'dsh-runtimes', 'dsh-primary-runtime', 'dependencies', 'python', process.platform === 'win32' ? 'python.exe' : 'bin/python3'),
    process.platform === 'win32' ? 'python' : 'python3',
  ].filter(Boolean);
  const code =
    'import importlib.util,json,sys;sys.argv=["x"];' +
    's=importlib.util.spec_from_file_location("m",' + JSON.stringify(MCP) + ');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);' +
    'print(json.dumps([{"name":t["name"],"desc":t["description"]} for t in m.tool_specs()],ensure_ascii=False))';
  for (const py of candidates) {
    try {
      return JSON.parse(execFileSync(py, ['-I', '-B', '-c', code], { encoding: 'utf8' }));
    } catch {
      /* 换下一个解释器 */
    }
  }
  throw new Error('找不到能运行 mcp/biomedical_mcp.py 的 python（可设 BIO_MCP_PYTHON）');
}

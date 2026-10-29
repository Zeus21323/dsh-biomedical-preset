# 生物医学模式 · dsh-biomedical-preset

DeepSeek Harness 的 agent 预设（bundle）：一个面向生物医学研究的协作模式，自带数据源 MCP 服务与 63 个流程技能，不依赖任何外部插件目录。

## 组成

| 层 | 内容 |
|---|---|
| 身份 | `persona`（生物医学研究者 prefix + 8 条结论纪律 suffix）、`agent-instructions`、`time-context` |
| 执行 | `tool-pwsh`/`tool-bash`、`tool-fs`、`tool-fs-search`、`tool-jobs` |
| 技能 | `skills/biomedical`（30）+ `skills/science-core`（33），由预设内 `skill-filesystem` 挂载 |
| 数据 | `mcp/biomedical_mcp.py` —— 51 个公开数据源工具的 stdio MCP 服务（纯标准库，零第三方依赖） |
| 编排 | `plan-mode`、`compaction`、`subagent`/`subagent_fork`/`workflow`、`todo`、`goal` |
| 并发闸 | `subagent-cap.mjs` —— 同一会话同时最多 3 个子智能体（`tools/execute` 作用域拦截） |
| 交付 | `tool-web`（文献与库 API）、`present`（图表与稿件） |

MCP 工具覆盖：PubMed、Ensembl/BioMart、NCBI Gene、dbSNP、ClinVar、gnomAD、GTEx、GEO、PRIDE、BioStudies、ArrayExpress、InterPro、STRING、HPA、PDB、AlphaFold DB、Rfam、ChEMBL、PubChem、Rhea、Open Targets、CIViC、openFDA、OpenAlex、arXiv、bioRxiv、cBioPortal、cellxgene 等。

## 安装

### 从插件市场

1. 打开 **插件** → **更多** → 启用 **自定义插件市场**；
2. **发现** → **添加索引源**，填入：
   ```
   https://raw.githubusercontent.com/Zeus21323/dsh-biomedical-preset/main/market/index.json
   ```
3. 在市场里安装 **Biomedical Mode**，然后新建会话时选择「生物医学模式」。

### 从 Git 直接安装

```sh
dsh plugin --profile desktop add git+https://github.com/Zeus21323/dsh-biomedical-preset.git#<40位commit>
```

或在 agent 里让 `plugin_manager` 以 `install_bundle` 安装该 spec。

### 本地开发

```sh
git clone https://github.com/Zeus21323/dsh-biomedical-preset
```

然后用 `plugin_manager` `install_bundle` 指向该目录（`link:` 安装，改动即时生效，需重新激活预设才读取新的 persona）。

## 平台要求

- DSH `^0.2.1-rc.2`
- Python 3（MCP 服务只用标准库；默认调用 DSH 自带运行时 `dsh-primary-runtime` 的 python）
- 出网访问公开 REST API（NCBI / EBI / Ensembl / RCSB / Broad 等）

## 已验证

- 市场索引通过官方校验器 `@deepseek-ai/dsh-plugin-market-index`（format 1）
- `npm pack` 产物 289 个文件 / 0.60 MB packed / 2.05 MB unpacked，patch、技能、MCP、locale、icon 齐全
- 预设在本机 `fiberPhase: active`，MCP 子进程与 63 个技能均正常挂载

## 目录

```
cordis.patch.yml      预设装配（23 个插件行）
package.json          包声明 + exports + files + engines.dsh
subagent-cap.mjs      子智能体并发闸（3/会话）
mcp/biomedical_mcp.py 51 个数据源工具（stdio JSON-RPC）
skills/biomedical/    30 个技能
skills/science-core/  33 个技能
locale/{en,zh}.json   市场与设置页展示元数据
icon.svg              原创图标
market/index.json     插件市场索引（format 1）+ icons/
```

## 许可

MIT

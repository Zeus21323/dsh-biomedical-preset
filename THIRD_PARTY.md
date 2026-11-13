# 第三方内容与许可证

本包代码（`picker/`、`settings/`、`client.js`、`subagent-cap.mjs`、`mcp/`、`tools/` 等）以 MIT 发布。
`skills/` 下的技能来自多个来源，**各自的许可证以技能目录内的 LICENSE / SKILL.md 声明为准**，不因本包的 MIT 而改变。

## 已确认许可证的来源

| 来源 | 范围 | 许可证 | 依据 |
|---|---|---|---|
| nf-core 流程封装 | `skills/*/nfcore-*` 中带 LICENSE 的 140 个目录（另有 13 个 `nfcore-*` 目录未附 LICENSE，归入下方「待作者补全」） | MIT | 各目录 `LICENSE` |
| nature-skills | `skills/methods/bioinformatics-writer/assets/licenses/` | Apache-2.0 | 随附许可证文本 |
| K-Dense 等在 frontmatter 中声明 `license:` 的技能 | 见各 `SKILL.md` 的 `license` 字段 | 按声明 | `SKILL.md` frontmatter |
| 自建技能 | `skills/omics/`（21 个） | MIT（随本包） | 本仓库 |

## 待作者补全

其余上游技能取自 27 个技能插件的发布内容（2026-10-30 版本，见 README「技能来源」），目录内**没有**附带许可证文件。
公开分发前，请逐个插件确认其许可证是否允许再分发，并把结果补进上表；不允许再分发的，应从 `skills/` 移除并从 `picker/catalog.json` 删掉条目，再运行 `node tools/gen.mjs`。

## 已移除

| 技能 | 原因 | 替代 |
|---|---|---|
| `docx`、`pdf`、`xlsx` | 许可证为「© Anthropic, PBC. All rights reserved」，不能随本包再分发 | DSH 自带 `office-docx`、`office-xlsx`、`office-export-pdf` |

`tools/lint-skills.mjs` 会拒绝任何「保留所有权利」且不含开源授权条款的 LICENSE 文件。每个技能识别到的许可证、许可证不明的完整名单见自动生成的 [COMPLIANCE.md](COMPLIANCE.md)；许可证不明的技能不会被评为「核心」级。

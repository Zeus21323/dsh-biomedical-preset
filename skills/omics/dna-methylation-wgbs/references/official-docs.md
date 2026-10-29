# 官方文档来源清单（逐一抓取确认）

抓取日期：2026-10-29。下表记录本技能每条命令的来源页面、版本状态与抓取结果。

## 1. Bismark

| # | URL | 内容 | 版本 | 抓取 |
| --- | --- | --- | --- | --- |
| B1 | https://felixkrueger.github.io/Bismark/quick-reference/ | 子命令对照表、`bismark prepare` / `bismark` / `bismark dedup` / `bismark extract` 典型命令、去重适用性 | Rust v3.1.0 | OK |
| B2 | https://felixkrueger.github.io/Bismark/options/genome-preparation/ | `bismark prepare` 全部选项、产物目录树 | Rust v3.x | OK |
| B3 | https://felixkrueger.github.io/Bismark/options/alignment/ | `bismark` 全部选项、USAGE、`--genome_folder` 等价说明、输出命名 | Rust v3.x | OK |
| B4 | https://felixkrueger.github.io/Bismark/options/methylation-extraction/ | `bismark extract` 全部选项（`--comprehensive`、`--cytosine_report`、`--genome_folder`、`--ignore*`、`--merge_non_CpG`）、四种输出格式 | Rust v3.x | OK |
| B5 | https://felixkrueger.github.io/Bismark/usage/methylation-extraction/ | 提取器完整三种典型命令（含 `--cytosine_report --genome_folder`）、12 个链特异文件 vs `--comprehensive`、M-bias | Rust v3.x | OK |
| B6 | https://felixkrueger.github.io/Bismark/faq/conversion-efficiency/ | 转换效率判据（非 CG 最低值、CpGi/线粒体/叶绿体、Lambda/phiX/M13/pUC19 spike-in） | Rust v3.x | OK |
| B7 | https://felixkrueger.github.io/Bismark/usage/filtering-non-conversion/ | `bismark filter` 命令与 `--threshold` / `--percentage_cutoff` / `--minimum_count` | Rust v3.x | OK |
| B8 | https://felixkrueger.github.io/Bismark/ | 首页流水线（Install → prepare → align → dedup → extract） | Rust v3.1.0 | OK |
| B9 | https://github.com/FelixKrueger/Bismark | README：`mamba install -c bioconda -c conda-forge bismark`、Rust 化说明 | master | OK |
| B10 | https://felixkrueger.github.io/Bismark/usage/alignment/ | USAGE、定向/非定向库、甲基化 call 字符串字母表（`Z/z/X/x/H/h/U/u/.`） | Rust v3.x | OK |
| B11 | https://raw.githubusercontent.com/FelixKrueger/Bismark/master/docs/bismark/alignment.md （经 cdn.jsdelivr.net 镜像 @v0.25.1 抓取） | 旧版 Perl 文档的 alignment 章节，确认旧版亦只用 `--genome` | v0.25.1 | OK（镜像） |
| B12 | https://api.github.com/repos/FelixKrueger/Bismark/git/trees/v0.25.1 | v0.25.1 文件树：`bismark_genome_preparation`、`bismark_methylation_extractor`、`coverage2cytosine`、`filter_non_conversion` 等 Perl 脚本仍在此 tag | v0.25.1 | OK |

### 关于用户指定参数 `--genome_folder` / `--paired-end` / `--comprehensive` / `--cytosine_report`

| 参数 | 官方位置 | 结论 |
| --- | --- | --- |
| `--genome_folder` | B3（alignment 的 ARGUMENTS）、B4（extract 的 cytosine report 选项） | aligner 侧为 `--genome` 的等价写法；extractor 侧为 `--cytosine_report` 的**强制**参数 |
| `--paired-end` | B4（extractor `-p/--paired-end`） | **仅在提取器**中存在。B3 / B10 / B1 / B11 的 aligner 选项表均无此参数，配对由 `-1/-2` 决定 |
| `--comprehensive` | B4、B5 | 存在，逐字说明已引用 |
| `--cytosine_report` | B4、B5 | 存在，逐字说明与格式已引用 |

> 注：Bismark 现为 Rust v3 套件，Perl v0.25.x 进入 maintenance-freeze。两者命令名互为别名
> （`bismark extract` = `bismark_methylation_extractor` 等），因此旧命令名仍可直接使用。

### 不可访问 / 未采用的 Bismark 资源

- `https://raw.githubusercontent.com/FelixKrueger/Bismark/master/Docs/Bismark_User_Guide.md` → HTTP 404
  （master 上已无 `Docs/` 目录，文档迁至 `docs/` 目录 + Astro 站点）。
- 直接抓取 `raw.githubusercontent.com/.../v0.25.1/docs/bismark/*.md` → 连接失败；
  改用 `cdn.jsdelivr.net/gh/FelixKrueger/Bismark@v0.25.1/...` 成功。
- `http://www.bioinformatics.babraham.ac.uk/projects/bismark/Bismark_User_Guide.pdf` → 未抓取
  （PDF 不在可解析范围）。

## 2. bwa-meth

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| M1 | https://github.com/brentp/bwa-meth | README：`bwameth.py index` / `index-mem2` / `--reference` 比对、stdout SAM 变更、MethylDackel/biscuit 分工、安装 | OK |
| M2 | https://raw.githubusercontent.com/brentp/bwa-meth/master/README.md | 同上（纯文本版，用于逐字引用） | OK |

## 3. methylKit

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| K1 | https://bioconductor.org/packages/release/bioc/vignettes/methylKit/inst/doc/methylKit.html | 官方 vignette（规范 URL） | **超时**（30 s） |
| K2 | https://raw.githubusercontent.com/al2na/methylKit/master/vignettes/methylKit.Rmd | 同一 vignette 源文件（内容一一对应），用于逐字引用 `methRead` / `filterByCoverage` / `unite` / `calculateDiffMeth` / `overdispersion="MN"` / `test="Chisq"` / genomation 注释 / MeDIP 不适用的 FAQ | OK |

> 引用时正文使用 K1（规范 URL），命令文本取自 K2（同源）。

## 4. DSS

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| D1 | https://bioconductor.org/packages/release/bioc/vignettes/DSS/inst/doc/DSS.html | 官方 vignette（规范 URL） | **超时**（30 s） |
| D2 | https://raw.githubusercontent.com/haowulab/DSS/master/vignettes/DSS.Rmd | 同源 vignette：输入格式 `chr/pos/N/X`、`makeBSseqData`、`DMLtest`（`smoothing`、500 bp 默认）、`callDML`（`p.threshold`/`delta`）、`callDMR`、`showOneDMR`、`areaStat`、无重复伪重复、`ncores`、Windows 限制、注释需外部工具 | OK |
| D3 | https://api.github.com/repos/haowulab/DSS/contents/vignettes | 目录列表（确认 D2 路径） | OK |

## 5. bsseq

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| S1 | https://bioconductor.org/packages/release/bioc/vignettes/bsseq/inst/doc/bsseq.html | 官方 vignette（规范 URL） | 未直连（沿用同源源文件） |
| S2 | https://raw.githubusercontent.com/hansenlab/bsseq/master/vignettes/bsseq.Rmd | 同源 vignette：`M`/`Cov` 数据模型、`BSseq()`、`orderBSseq`、`BSmooth`、`BSmooth.tstat`、`dmrFinder`、`read.bismark(BACKEND="HDF5Array")`、`saveHDF5SummarizedExperiment`、`fisherTests`、内存与并行注意 | OK |

## 6. MEDIPS

| # | URL | 内容 | 抓取 |
| --- | --- | --- | --- |
| P1 | https://bioconductor.org/packages/release/bioc/html/MEDIPS.html | 官方包页：功能定位原文（MeDIP-seq / 任意定量测序 / 差异 coverage / saturation 与 correlation）、依赖、版本 1.54.0、Documentation 栏（仅 PDF + R Script） | OK（经清华镜像同内容页） |
| P2 | https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.18/bioc/html/MEDIPS.html | 同 P1（镜像，官方内容） | OK |
| P3 | https://bioconductor.org/packages/release/bioc/vignettes/MEDIPS/inst/doc/MEDIPS.html | 期望的 HTML vignette | **HTTP 404（不存在）**：该包不发布 HTML vignette |
| P4 | https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.18/bioc/vignettes/MEDIPS/inst/doc/MEDIPS.Rnw | vignette 源文件 | **不可读**：`application/octet-stream` |
| P5 | https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.18/bioc/vignettes/MEDIPS/inst/doc/MEDIPS.R | vignette R 脚本 | **不可读**：`application/octet-stream` |
| P6 | https://mirrors.tuna.tsinghua.edu.cn/bioconductor/packages/3.18/bioc/vignettes/MEDIPS/inst/doc/MEDIPS.pdf | vignette PDF | **不可读**：`application/pdf` 不支持 |
| P7 | https://code.bioconductor.org/browse/MEDIPS/raw/master/vignettes/MEDIPS.Rnw | 代码浏览器原始文件 | **连接失败**（两次） |

> 结论：MEDIPS 的**可执行调用**（如建集、耦合、差异 coverage 的函数签名）在本环境下无法从官方
> 文本取得。按硬性规则 2，SKILL.md 第 7 节只写流程与判据，并给出 R 内 `browseVignettes("MEDIPS")`
> 这一官方指引（P1 原文提供），不写任何未验证的 MEDIPS 函数调用。

## 7. 统计

**正文引用的独立官方 URL：23 个**（去重后）

| 组 | URL 数 | 明细 |
| --- | --- | --- |
| Bismark 站点 | 9 | B1、B2、B3、B4、B5、B6、B7、B8、B10 |
| Bismark GitHub | 3 | B9（README）、B11（v0.25.1 alignment 章节镜像）、B12（v0.25.1 文件树 API） |
| bwa-meth | 2 | M1（仓库页）、M2（raw README） |
| methylKit | 2 | K1（规范 vignette URL）、K2（同源 .Rmd） |
| DSS | 3 | D1（规范 URL）、D2（同源 .Rmd）、D3（vignettes 目录 API） |
| bsseq | 2 | S1（规范 URL）、S2（同源 .Rmd） |
| MEDIPS | 2 | P1（官方包页）、P2（镜像同内容页） |
| 合计 | **23** | |

**抓取状态**：20 个直接抓取成功；3 个规范 URL 未取得可用文本
（K1、D1 超时 30 s；S1 未直连，改抓同源 S2），其命令文本一律取自同源 GitHub vignette 源文件，
内容与 Bioconductor 发布版一一对应。

**失败或不可读的目标清单**（供后续复核）：

1. `raw.githubusercontent.com/FelixKrueger/Bismark/master/Docs/Bismark_User_Guide.md` → HTTP 404
2. `raw.githubusercontent.com/FelixKrueger/Bismark/v0.25.1/docs/bismark/genome_preparation.md` → 连接失败
3. `raw.githubusercontent.com/FelixKrueger/Bismark/v0.25.1/docs/bismark/alignment.md` → 连接失败（两次）
4. `github.com/FelixKrueger/Bismark/raw/v0.25.1/docs/bismark/genome_preparation.md` → 连接失败
5. `bioconductor.org/.../methylKit/inst/doc/methylKit.html` → 超时
6. `bioconductor.org/.../DSS/inst/doc/DSS.html` → 超时
7. `bioconductor.org/.../MEDIPS/inst/doc/MEDIPS.html` → HTTP 404（该包无 HTML vignette）
8. `mirrors.tuna.tsinghua.edu.cn/.../MEDIPS/inst/doc/MEDIPS.html` → HTTP 404
9. `mirrors.tuna.tsinghua.edu.cn/.../MEDIPS/inst/doc/MEDIPS.Rnw` → `application/octet-stream`
10. `mirrors.tuna.tsinghua.edu.cn/.../MEDIPS/inst/doc/MEDIPS.R` → `application/octet-stream`
11. `mirrors.tuna.tsinghua.edu.cn/.../MEDIPS/inst/doc/MEDIPS.pdf` → `application/pdf` 不支持
12. `code.bioconductor.org/browse/MEDIPS/raw/master/vignettes/MEDIPS.Rnw` → 连接失败（两次）
13. `code.bioconductor.org/browse/MEDIPS/RELEASE_3_18/vignettes/MEDIPS.Rnw` → 连接失败
14. `raw.githubusercontent.com/Bioconductor/MEDIPS/master/vignettes/MEDIPS.Rnw` → 超时
15. `bioconductor.org/packages/release/bioc/html/MEDIPS.html` → 超时（改用 P1/P2 镜像同内容页）

> 上述 MEDIPS 项全部落在"无法取得可执行命令"一类，已在 SKILL.md 第 7.2 节按硬性规则 2 处理。

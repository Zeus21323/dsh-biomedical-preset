# 糖链命名、编码与数据库入口对照

全部内容取自官方页面，逐字处用引号标出并附 URL；凡官方页面抓取不到的部分明确写「未取到」，
不作补写。抓取状态见 `official-docs.md`。

---

## 1. 三种编码的分工（一张表定位置）

| 编码 | 定位（官方原文要点） | 规范载体 | 本技能可否逐字引用语法 |
|---|---|---|---|
| **GlycoCT** | "a unifying sequence format for carbohydrates"（Herget 2008, Carbohydr Res 343(12):2162-71, PMID:18436199） | 仓库内 `GlycoCT.pdf`，**版本 4 (KIROI)**，2007 | **不可**（PDF 未解析）；只用官方样例串 |
| **WURCS** | "Web3 Unique Representation of Carbohydrate Structures"，目标是「线性、可作 URI、且能唯一表示任何已发表结构，包含非标准单糖、组成、重复单元与连接未知的模糊结构」 | `WURCS 2.0` wiki（WURCS-notations / WURCS-components） | **可**（wiki 为纯文本） |
| **CFG 相关（LinearCode）** | 官方转换器把 `LinearCode` 列为可 import 的格式之一 | GlycanFormatConverter CLI README | 只知格式名；**官方 README 未把 `LinearCode` 明确等同 CFG 线性码**，不作等同断言 |

> 来源：<https://github.com/glycoinfo/GlycoCT>、<https://github.com/glycoinfo/WURCS/wiki>、
> <https://gitlab.com/glycoinfo/GlycanFormatConverter-cli>

### 1.1 官方转换矩阵（逐字，行=输入，列=输出）

来源：<https://gitlab.com/glycoinfo/GlycanFormatConverter-cli>（README 的 Supported formats 表）

| Input \ Output | IUPAC-Extended | IUPAC-Condensed | IUPAC-Short | GlycoCT | WURCS | GlycanWeb |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| WURCS | ✔︎ | ✔ | ✔ | ✔︎ | — | ✔ |
| IUPAC-Extended | — | ✔ | ✔ | — | ✔ | ✔ |
| IUPAC-Condensed | — | — | ✔ | — | ✔ | ✔ |
| KCF | ✔ | ✔ | ✔ | — | ✔ | ✔ |
| LinearCode | ✔ | ✔ | ✔ | — | ✔ | ✔ |
| GlycoCT | ✔ | ✔ | ✔ | — | ✔ | ✔ |

读法（这三条最容易踩）：

1. **不能同格式互转**：`GlycoCT→GlycoCT`、`WURCS→WURCS` 两格为空。需要「规范化」时先转出到
   IUPAC-Extended 再转回，且要接受一次信息损耗。
2. **`GlycoCT` 只能作为 import 侧，且只有 WURCS 能直出 GlycoCT**：`GlycoCT` 列里唯一有 ✔ 的是 `WURCS` 行，
   其余行（IUPAC-Extended / IUPAC-Condensed / KCF / LinearCode）在该列均为空。因此
   「IUPAC → GlycoCT」必须两步：`IUPAC → WURCS → GlycoCT`；写成一步的命令是错的。
3. `GlycanWeb` 只能作输出，不能作输入。

---

## 2. GlyTouCan accession

### 2.1 形态与稳定性

- 观测样本（官方页面原文出现）：`G00051MO`、`G00055MO`、`G00047MO`、`G00065MO`、`G66357CN`。
  → 形态为 **`G` + 5 位数字 + 2 位大写字母**。
- 官方明示非流水号：`"Since the accession numbers are randomly generated, they may differ between the
  production and beta environments."`
  来源：<http://code.glytoucan.org/system/cli/>
- **修正**：任务描述里的「G00000XX（零填充序号）」不成立。不能按数字大小推断注册先后，
  也不能假定后缀固定；跨环境（beta/production）比对时必须重新解析，不能只比数字段。
- 结构页 URL：`https://glytoucan.org/Structures/Glycans/{ACCESSION}`（官方 CLI 页给出 `G66357CN` 实例）。

### 2.2 注册语义（影响注释口径）

| 情形 | 官方说法 | 对注释的影响 |
|---|---|---|
| 连接位置未知 | "The position would be considered ambigous. It would be registered as ambiguous and when searching, the similar structures with any linkage position will be queried." | 一个 accession 可能代表「连接位置模糊」的结构；不能把它当唯一确定结构用 |
| 苷元（aglycon） | "Currently aglycons and glycoconjugates are not supported." | 糖肽/糖脂上的**苷元不进入 GlyTouCan**；糖肽的「肽段部分」必须另存，不能塞进 accession |
| 提交 401 | 到 `https://glytoucan.org/Users/profile` 点 "Generate API Key" | 自动化脚本失败先查 API key 是否为空 |

来源：<http://code.glytoucan.org/FAQ>

### 2.3 提交命令（**官方已标 DEPRECATED**）

摘要（完整参数见 `official-docs.md` §1 T4）：

```
groovy gtc -u [contributor id] -a [API key] -s '[sequence]'
groovy gtc -u [contributor id] -a [API key] -c [csvFile] -o tsv -m uafh
export API_HOSTNAME="https://api.glytoucan.org"
```

引用时必须同时写：该页顶部原文 `DEPRECATED` / "Please use direct REST access from the command line."，
且官方指向的替代物是仓库 `glytoucan/databaseSync` 里的 bash 脚本
（`curlRemove.sh`、`curlRemoveBySeq.sh`）。

---

## 3. GlycoCT

### 3.1 官方样例串（唯一可逐字引用的语法证据）

来源：<http://code.glytoucan.org/system/cli/>（官方注明 "note the carriage returns are \"\\n\""）

```
RES
1b:b-dglc-HEX-1:5
2s:n-acetyl
3b:b-dgal-HEX-1:5
LIN
1:1d(2+1)2n
2:1o(4+1)3d
```

命令行里的写法（同一页面逐字）：

```
RES\n1b:b-dglc-HEX-1:5\n2s:n-acetyl\n3b:b-dgal-HEX-1:5\nLIN\n1:1d(2+1)2n\n2:1o(4+1)3d\n
```

### 3.2 从样例能安全推出的只有这些

- 两段结构：`RES`（残基表）与 `LIN`（连接表）。
- 残基行形态 `序号` + 类型字母（`b` 主链糖 / `s` 取代基）+ `:` + 残基描述；
  描述含异头构型（`b-`/`a-`）、糖名（`dglc`、`dgal`）、`HEX` 类别与环化信息（`-1:5`）。
- 连接行 `1:1d(2+1)2n` 表达「RES#1 的某位点 → RES#2 的某位点」，括号内为位置算术。
- **不写**：编号规则、取代基命名的完整文法、模糊连接的写法——这些在 `GlycoCT.pdf` 里，
  本环境不可解析，若需要请直接读 PDF（仓库根目录）。

### 3.3 与 WURCS 的互转

见 §5.4（官方 CLI 命令）。已知限制：`GlycoCT → GlycoCT` 不支持；`GlycoCT` 仅作 import。

---

## 4. WURCS 2.0

### 4.1 顶层格式（逐字）

来源：<https://github.com/glycoinfo/WURCS/wiki/WURCS-notations>

```
`WURCS=` `<Version>` `/` `<Unit Count>` `/` `<UniqueRES List>` `/` `<RES Sequence>` `/` `<LIN List>`
```

| 段 | 定义（逐字要点） |
|---|---|
| Version | "`<Version>`: `2.0` (current version)" |
| Unit Count | "`<UniqueRES Count>`,`<RES Count>`,`<LIN Count>`" |
| Uncertain LIN Count | "`<LIN Count>` `+`"；"plus `+` indicates that there may potentially be more than LIN Count linkages" |
| UniqueRES | "`[` `<ResidueCode>` `]`" |
| ResidueCode | "`<BackboneCode>` `_` `<MOD #1>` `_` … " |
| BackboneCode | "`<SkeletonCode>` `-` `<Anomeric Information>`" |
| MOD | "`<LIP #1>` `-` … `-` `<LIP #n>` `<MAP>`" |
| LIP | "`<Position>` `<Direction>` `<Star Index>`"（Position 可为 `?` 表示未知位置） |

### 4.2 SkeletonCode 与 CarbonDescriptor（逐字表，节选官方 Table 1）

来源：<https://github.com/glycoinfo/WURCS/wiki/WURCS-components>

| Fischer 投影官能团 | CarbonDescriptor | 主链位置 |
|---|:---:|---|
| Aldehyde | `o` | Terminal |
| Hydroxymethyl | `h` | Terminal |
| Carboxyl | `A` | Terminal |
| Methyl | `m` | Terminal |
| Ketone | `O` | Non-terminal |
| Hydroxy carbon（左） | `1` | Non-terminal |
| Hydroxy carbon（右） | `2` | Non-terminal |
| Methylene（deoxy） | `d` | Non-terminal |
| Hemiacetal / Hemiketal（异头中心） | `a` | Terminal / Non-terminal |
| Aldehyde 或 Hemiacetal | `u` | Terminal |
| Ketone 或 Hemiketal | `U` | Non-terminal |

- 长度语义："The length of a SkeletonCode is the number of carbons in the backbone (e.g. a backbone with six
  CarbonDescriptors means a hexose)."
- 例："aldehydo-D-glucose is represented using SkeletonCode as `o2122h`"；开链醛糖可写 `o<x>h`。
- 通配：`x`/`X` = 未知；`<`…`>` = 未知重复次数，且 "Currently, only one CarbonDescriptor can be in the `<` and `>`"。

### 4.3 异头信息（逐字）

- "If one of the backbone carbons is an anomeric center, Anomeric Information must be added to the SkeletonCode
  following a hyphen `-`."；无（或不确定有）异头中心时省略。
- 位置：醛糖多为 `1`，2-酮糖为 `2`，未知用 `?`。
- 符号：α = `a`，β = `b`（相对立体描述）；`u`/`d` 为**绝对**立体描述（Haworth 上/下）。

### 4.4 真实串的读法（用官方样例核对）

`G00051MO` 的 WURCS（GlyGen API 与 GlyTouCan CLI 页两处一致）：

```
WURCS=2.0/3,3,2/[a2122h-1b_1-5_2*NCC/3=O][a1221m-1a_1-5][a2112h-1b_1-5]/1-2-3/a3-b1_a4-c1
```

逐段读：

- `3,3,2` → 3 个 UniqueRES、3 个 RES、2 个连接。
- 三个 UniqueRES：`[a2122h-1b_1-5_2*NCC/3=O]`（带 N-乙酰修饰的己糖，即 HexNAc）、`[a1221m-1a_1-5]`
  （`m` 端基 = 甲基/脱氧类，末端为 `m` 的 6 碳糖即 Fuc 类）、`[a2112h-1b_1-5]`（Hex）。
- `/1-2-3/` → 三个残基依次为 UniqueRES #1、#2、#3。
- `a3-b1_a4-c1` → 两条连接：a 的 3 位到 b 的 1 位；a 的 4 位到 c 的 1 位。
- 与 GlyGen 返回的 IUPAC 对照：`beta-D-Galp-(1->4)[alpha-L-Fucp-(1->3)]-beta-D-GlcpNAc-(1-`。

> 这一对照只用于**读懂格式**，不作为「自动推断结构」的算法；组成与连接的最后判定仍按
> `SKILL.md` §8 人工核查。

---

## 5. 官方检索与转换命令

### 5.1 SPARQL：取全部 WURCS 序列（逐字）

endpoint：`https://ts.glytoucan.org/sparql`（来源：`sparql-queries` 页）

```
PREFIX glycan: <http://purl.jp/bio/12/glyco/glycan#>
PREFIX glytoucan:  <http://www.glytoucan.org/glyco/owl/glytoucan#>

SELECT DISTINCT ?Saccharide ?PrimaryId ?Sequence
FROM <http://rdf.glytoucan.org/core>
FROM <http://rdf.glytoucan.org/sequence/wurcs>
WHERE {
    ?Saccharide glytoucan:has_primary_id ?PrimaryId .
    ?Saccharide glycan:has_glycosequence ?GlycoSequence .
    ?GlycoSequence glycan:has_sequence ?Sequence .
    ?GlycoSequence glycan:in_carbohydrate_format glycan:carbohydrate_format_wurcs.
}
ORDER BY ?PrimaryId
limit 100
```

### 5.2 SPARQL：取全部 GlycoCT 序列（逐字）

同上 endpoint，图名与格式常量换成：

```
FROM <http://rdf.glytoucan.org/sequence/glycoct>
...
?GlycoSequence glycan:in_carbohydrate_format glycan:carbohydrate_format_glycoct.
```

### 5.3 SPARQL：外部库 ID → GlyTouCan accession（逐字）

endpoint：`https://ts.glycosmos.org/sparql`

```
PREFIX dcterms: <http://purl.org/dc/terms/>
PREFIX glycan: <http://purl.jp/bio/12/glyco/glycan#>
PREFIX glytoucan: <http://www.glytoucan.org/glyco/owl/glytoucan#>

SELECT DISTINCT ?accNum  ?external_id
FROM <http://rdf.glytoucan.org/core>
FROM <http://rdf.glytoucan.org/partner/glycome-db>
WHERE{
  ?saccharide glytoucan:has_primary_id ?accNum .
  ?saccharide glycan:has_resource_entry ?entry .
  ?entry a glycan:Resource_entry .
  ?entry glycan:in_glycan_database glycan:Database_glycomedb .

  VALUES ?external_id {"10923"}
  ?entry dcterms:identifier ?external_id .
}
```

> 换成别的合作库时，需把 `.../partner/glycome-db` 与 `glycan:Database_glycomedb` 一并替换；
> 官方示例只给了 glycome-db 这一例，其它库的常量名**未取到**，不要猜。

### 5.4 编码互换（官方 CLI，逐字）

```
java -jar ./target/GlycanFormatConverter-cli.jar -i WURCS -e IUPAC-Extended -seq 'WURCS=2.0/5,9,8/[a2122h-1x_1-5][a2112h-1b_1-5][a2122h-1b_1-5_2*NCC/3=O][a1221m-1a_1-5][Aad21122h-2a_2-6_5*NCC/3=O]/1-2-3-2-4-5-3-2-5/a4-b1_b3-c1_b6-g1_c4-d1_d2-e1_d6-f2_g4-h1_h6-i2'
```

```
java -jar ./target/GlycanFormatConverter-cli.jar -i IUPAC-Extended -e WURCS -seq "α-D-Neup5Ac-(2→6)[α-L-Fucp-(1→2)]-β-D-Galp-(1→4)-β-D-GlcpNAc-(1→3)[α-D-Neup5Ac-(2→6)-β-D-Galp-(1→4)-β-D-GlcpNAc-(1→6)]-β-D-Galp-(1→4)-?-D-Glcp-(1→" | grep WURCS=2.0 | grep -v DEBUG
```

注意（官方 Notes 精神）：WURCS 串内含逗号与方括号，**shell 里必须用单引号**；含 `α`/`→` 的 IUPAC 串
必须用双引号。

### 5.5 单糖/取代基质量与诊断离子（官方脚本）

```
python -f C(7)H(7)N(1)O(2) -r N~15N
python diagnostic-ion-checker.py -mgf mgf_containing_folder -marker 204.087,138.055
```

（file 路径：`mass_calc/chem2mass.py`、`scripts/diagnostic-ion-checker.py`，
仓库 <https://github.com/pFindStudio/pGlyco3>）

---

## 6. 数据库入口与各自「能查什么」

| 入口 | URL | 官方可核实能力 | 不能指望它做什么 |
|---|---|---|---|
| GlyTouCan | <https://glytoucan.org/> | 结构 accession 登记；SPARQL 批量取 WURCS/GlycoCT；模糊连接会被登记为 ambiguous | 不支持苷元/糖复合物；无「糖肽」条目 |
| GlyTouCan code 站 | <http://code.glytoucan.org/> | 手册、FAQ、RDF/SPARQL 示例、API 功能清单、CLI（已 DEPRECATED） | 主站文档页（`/Documentation`）是 SPA，抓不到正文 |
| GlyCosmos | <https://glycosmos.org/>；SPARQL `https://ts.glycosmos.org/sparql` | 元数据（物种等）与跨库整合查询；官方示例给出该 endpoint | 门户页本身是 SPA；`api.glycosmos.org` 只暴露 Wiki 外壳 |
| GlyGen | <https://www.glygen.org/>；API `https://api.glygen.org/` | 糖与糖复合物数据整合；`/glycan/detail/{ACC}/` 实测返回 wurcs/glycoct/iupac/mass/species | 站点为 SPA；端点无文字文档 |
| GlycoNAVI | <https://glyconavi.org/> | WURCS 工具索引里的糖科学门户（含 GlycanFormatConverter Web） | `Tools/tool/gfc.php` 返回 308，正文未取到 |
| CSDB | <http://csdb.glycoscience.ru/> | 天然糖链结构、分类、文献、NMR 手工整理库 | 非质谱数据源 |
| GlycoStore | <https://glycostore.org/> | 保留性质库：`HPLC`、`UPLC_2-AB`、`UPLC_Procainamide`、`CE`、`RP`、`PGC` 单位；含 `GlycoCT Structure`、`MIRAGE LC` | About/Help 页有反爬；GU 换算工具未提供 |
| CFG Glycan Array | <https://www.functionalglycomics.org/glycan-array> | 糖芯片实验归档：`ID`/`Request`/`Sample`/`Category`/`Glycan Array`/`Conclusive` | 命名法页面已 404；不是结构库 |

---

## 7. 术语一致性检查（写完必查）

| 检查项 | 正确写法 | 常见错法 |
|---|---|---|
| GlyTouCan accession | `G00051MO`（G+5 位数字+2 位字母） | `G000001`、`G00000XX`（把随机后缀当序号） |
| WURCS 前缀 | `WURCS=2.0/...` | `WURCS2.0`、省略 `=2.0` |
| GlycoCT 段名 | `RES` / `LIN`（大写） | `Res`/`Lin`、把 `LIN` 写成 `LINK` |
| 单糖缩写 | `HexNAc`、`Hex`、`Fuc`、`NeuAc`、`NeuGc` | `GlcNAc` 当通用组成（只在确定是 GlcNAc 时才用） |
| 电荷 | `z`（电荷数）与 `m/z` 分开写 | 把 `m/z 2+` 写成「带两个氢」 |
| FDR | 分别写 `GlycanFDR` / `PeptideFDR` / `TotalFDR` | 写「FDR 1%」而不说是哪个维度 |
| 芯片版本 | `PA_v52`、`GLYCAN_v3`、`BACT_v1` | `v52`、`PA52` |

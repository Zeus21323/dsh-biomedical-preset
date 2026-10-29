# 脂质命名与检索速查

全部内容取自官方页面；每条都标注来源。凡官方页面在抓取时被截断、未取到的行，明确标注"未取到"，不作补写。

---

## 1. LIPID MAPS 八类别

来源：<https://www.lipidmaps.org/resources/education/classification>

| 缩写 | 类别 | 定义要点（官方原文摘要） |
|---|---|---|
| FA | Fatty acyls 脂肪酸酰类 | "synthesized by chain elongation of an acetyl-CoA primer with malonyl-CoA (or methylmalonyl-CoA) groups"；含脂肪酸与共轭物、脂肪酸酯（含 acyl-CoA、acyl-ACP、acylcarnitine）、脂肪醇/醛、脂肪酰胺（含 anandamide）、烃类 |
| GL | Glycerolipids 甘油脂类 | "composed mainly of mono-, di- and tri-substituted glycerols"；含甘油糖脂（MGDG/DGDG）、seminolipid |
| GP | Glycerophospholipids 甘油磷脂类 | 按 sn-3（真核/真细菌）或 sn-1（古菌）头基分亚类；含 PC/PE/PI/PS、cardiolipin（第三个甘油被酰化，伪对称） |
| SP | Sphingolipids 鞘脂类 | 以 sphingoid base 为骨架；亚类：sphingoid bases 及其衍生物（1-phosphate）、ceramides（N-acyl）、phosphosphingolipids（SM）、glycosphingolipids（中性/酸性 gangliosides/碱性/两性） |
| ST | Sterol lipids 甾醇脂类 | 胆固醇及其衍生物；C18 雌激素、C19 雄激素、C21 孕激素/糖皮质激素/盐皮质激素；secosteroids（维生素 D）；胆汁酸及其结合物 |
| PR | Prenol Lipids 异戊烯醇脂类 | 由 IPP/DMAPP 经 MVA 途径合成；>40 碳称 polyterpenes；含 carotenoids、quinones/hydroquinones（维生素 E、K、ubiquinone）、dolichols/bactoprenols |
| SL | Saccharolipids 糖脂类 | 脂肪酸直接连糖骨架；典型为 Lipid A 的酰化葡糖胺前体（Kdo2-Lipid A） |
| PK | Polyketides 聚酮类 | 乙酰/丙酰亚基聚合；erythromycin、tetracycline、avermectin、epothilone 等 |

### 1.1 亚类编号（官方编号，例：`GP01`）

来源：<https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html>（"Lipid subclass" 列，**逐字**）

| 编号 | 亚类名 |
|---|---|
| FA01 | Fatty acids and Conjugates |
| FA07 | Fatty esters |
| FA08 | Fatty amides |
| GL00 | Other Glycerolipids |
| GL01 | Monoradylglycerols |
| GL02 | Diradylglycerols |
| GL03 | Triradylglycerols |
| GL04 | Glycosylmonoradylglycerols |
| GL05 | Glycosyldiradylglycerols |
| GP00 | Other Glycerophospholipids |
| GP01 | Glycerophosphocholines |
| GP02 | Glycerophosphoethanolamines |
| GP03 | Glycerophosphoserines |
| GP04 | Glycerophosphoglycerols |
| GP06 | Glycerophosphoinositols |
| GP10 | Glycerophosphates |
| GP12 | Glycerophosphoglycerophosphoglycerols |
| GP15 | Glycerophosphoinositolglycans |
| GP20 | Oxidized glycerophospholipids |
| PR01 | Isoprenoids |
| PR02 | Quinones and hydroquinones |
| SL01 | Acylaminosugars |
| SP06 | Acidic glycosphingolipids |

> `SP01`–`SP05`、`ST01`+ 的编号在抓取时被截断，**未取到**；需要时以官方表为准。

---

## 2. 结构信息八级层级

来源：<https://www.lipidmaps.org/lipid_nomenclature/rules/hierarchy>（逐字）

1. **Species level** — "Sum composition, i.e., sum of carbon atoms, DBE and number of additional oxygen atoms, e.g. FA 18:1;O. Assumptions by "biological intelligence" need to be stated. Of note, for Sterols the ABCD ring system is assumed and not expressed as DBE."
2. **Molecular species level** — "annotates Lipid species with identified fatty acyl/alkyl residues, e.g. TG 16:0_18:1_18:1"
3. ***sn*-Position level** — "annotates GL and GP molecular species: Fatty acyl/alkyl constituents at the glycerol backbone are indicated by a slash, e.g. TG 16:0/18:1/18:1"
4. **DB/DBE-position level** — "annotates species having constituents with Defined position of double bond(s)/double bond equivalent(s), e.g. FA 18:2(9,12);O"
5. **Phosphate-position level** — "e.g. for phosphatidylinositolphosphates PIP[3'] or PIP2[4',5']"
6. **Structure defined level** — "Molecular species with constituents and functional groups, the latter include Triple bonds (Y), e.g. FA 18:2;OH or FA 18:0;Y"
7. **Full structure level** — "Molecular species with constituents and functional groups including positions, e.g. FA 18:2(9Z,11E);13OH or FA 18:0;9Y"
8. **Complete structure level** — "Molecular species with constituents and functional groups including positions and stereochemistry (acc. to LMSD), e.g. FA 18:2(9Z,11E);13OH[S] (= common name 13S-HODE)"

### 2.1 分隔符速查（这是最常被写错的地方）

| 写法 | 层级 | 含义 |
|---|---|---|
| `PC 32:0` / `PC(32:0)` | Species | 总碳 32、总双键 0；两条链怎么分不知道 |
| `PC 16:0_18:0` | Molecular species | 链组成 16:0 与 18:0；**谁在 sn-1 不知道** |
| `PC(16:0/18:0)` | *sn*-Position | sn-1 = 16:0，sn-2 = 18:0 |
| `PC(16:0/18:1(9Z))` | DB-position | 且 18:1 的双键在 9 位、顺式 |
| `PC(O-16:0/18:1)` | 烷基醚 | `O-` = 烷基醚键 |
| `PC(P-16:0/18:1)` | 缩醛磷脂 | `P-` = (1Z)-烯基醚 |
| `Cer(d18:1/C16:0)` | 鞘脂 sn/链 | `d` = 1,3-二羟基长链碱；`t` = 1,3,4-三羟基 |

来源：2 节层级页 + <https://www.lipidmaps.org/lipid_nomenclature> 第 11–13 条与第 10 条。

---

## 3. 加合物

### 3.1 官方缩写表

来源：<https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html>（"Major adduct abbreviation / Meaning"，逐字）

| 缩写 | Meaning |
|---|---|
| `[M+H]+` | Proton adduct |
| `[M+Na]+` | Sodium adduct |
| `[M+NH4]+` | Ammonium adduct |
| `[M-H]-` | Proton loss |
| `[M+FA-H]-` / `[M+HCOO]-` | Formate adduct |
| `[M+Hac-H]-` / `[M+CH3COO]-` | Acetate adduct |

### 3.2 LIPID MAPS moverz 的 ion-type 取值（逐字）

来源：<https://www.lipidmaps.org/resources/rest>

- **Positive**：`M+H`、`M+2H`、`M+3H`、`M+4H`、`M+NH4`、`M+Ag`、`M+Na`、`M+2Na`、`M+K`、`M+2K`、`M+Li`、`M+2Li`
- **Negative**：`M-H`、`M-CH3`、`M-2H`、`M-3H`、`M-4H`、`M.Cl`、`M.OAc`
- **Neutral**：`Neutral`

### 3.3 类别 → 首选加合物（官方表节选，完整表见原页）

来源：<https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html>

| 类别 | 缩写 | ESI(+) form 1 | form 2 | ESI(-) form 1 |
|---|---|---|---|---|
| Free fatty acid | FA | — | — | `[M-H]-` |
| Oxidized fatty acid | OxFA | — | — | `[M-H]-` |
| N-acyl ethanolamines | NAE | `[M+H]+` | — | — |
| Acylcarnitine | CAR | `[M]+` | — | — |
| FAHFA | FAHFA | — | — | `[M-H]-` |
| Diacylglycerol | DG | `[M+NH4]+` | — | — |
| Triacylglycerol | TG | `[M+NH4]+` | `[M+Na]+` | — |
| Ether-linked TG | EtherTG | `[M+NH4]+` | `[M+Na]+` | — |
| Phosphatidylcholine | PC | `[M+H]+` | `[M+Na]+` | `[M+CH3COO]-` |
| Ether-linked PC | EtherPC | `[M+H]+` | — | `[M+CH3COO]-` |
| Lysophosphatidylcholine | LPC | `[M+H]+` | `[M+Na]+` | `[M+CH3COO]-` |
| Ether-linked LPC | EtherLPC | `[M+H]+` | — | `[M+CH3COO]-` |
| Phosphatidylethanolamine | PE | `[M+H]+` | `[M+Na]+` | `[M-H]-` |
| Ether-linked PE | EtherPE | `[M+H]+` | — | `[M-H]-` |
| Lysophosphatidylethanolamine | LPE | `[M+H]+` | — | `[M-H]-` |
| Phosphatidylserine | PS | `[M+H]+` | `[M+Na]+` | `[M-H]-` |
| Lysophosphatidylserine | LPS | — | — | `[M-H]-` |
| Phosphatidylglycerol | PG | `[M+NH4]+` | — | `[M-H]-` |
| Lysophosphatidylglycerol | LPG | — | — | `[M-H]-` |
| Phosphatidylinositol | PI | `[M+NH4]+` | `[M+Na]+` | `[M-H]-` |
| Lysophosphatidylinositol | LPI | — | — | `[M-H]-` |
| Phosphatidic acid | PA | — | — | `[M-H]-` |
| Lysophosphatidic acid | LPA | — | — | `[M-H]-` |
| Cardiolipin | CL | `[M+NH4]+` | — | `[M-H]-` |
| Lysocardiolipin | MLCL | — | — | `[M-H]-` |
| Oxidized PC | OxPC | — | — | `[M+CH3COO]-` |
| Oxidized PE | OxPE | — | — | `[M-H]-` |
| Oxidized PG / PI / PS | OxPG / OxPI / OxPS | — | — | `[M-H]-` |
| MGDG / DGDG | MGDG / DGDG | `[M+NH4]+` | — | `[M+CH3COO]-` |
| SQDG | SQDG | `[M+NH4]+` | — | `[M-H]-` |
| Ganglioside GM3 | GM3 | `[M+NH4]+` | — | `[M-H]-` |
| Ganglioside GM1/GD1a/GD1b/GQ1b/GT1b | — | `[M+H]+` | — | `[M-H]-` |
| Ganglioside GD3 | GD3 | — | — | `[M-H]-` |
| Coenzyme Q | CoQ | `[M+H]+` | — | — |
| Vitamin E | Tocopherol | — | — | `[M+CH3COO]-` |
| Lipid A | LipidA | — | — | — |

> **Cer / SM / Sa1P / So1P 等鞘脂行的加合物列在抓取时被截断，未取到**——请以官方原页为准，勿照抄本表。

---

## 4. 四套命名的对照与互转

| 体系 | 官方来源 | 形态示例 | 转换入口 |
|---|---|---|---|
| LIPID MAPS shorthand | <https://www.lipidmaps.org/lipid_nomenclature> | `PC(16:0/18:1(9Z))`、`TG(52:1)`、`PC(O-34:2)` | RefMet 工具（见下） |
| LIPID MAPS / LMSD 存取号 | <https://www.lipidmaps.org/databases/lmsd/overview> | `LMGP01010005`、`LMFA01010001`、`LMSP...`、`LMST...` | REST `lm_id` 查询 |
| RefMet 标准化名 | <https://www.lipidmaps.org/resources/tools/lipid_std_form>（m/z 版 `/lipid_std_mz_form`） | 官方示例：`4Z,7Z,10Z,13Z,16Z,19Z-docosahexaenoic acid` / `Cervonic acid` / `Docosahexaenoic acid` / `C22:6n-3,6,9,12,15,18` → 全部归一为 **`DHA`** | 官方说明："This tool uses RefMet (Fahy & Subramaniam Nat. Methods 2020)" |
| SwissLipids | <https://www.swisslipids.org/> | `SWISSLIPID:000056420` 形式的类别/species/isomeric subspecies 三级实体 | SPARQL（第 5.2 节） |
| MS-DIAL 两类写法 | <https://systemsomicslab.github.io/compms/msdial/lipidnomenclature.html> | **chain summed**：`PC 38:4`、`TG 56:8`；**chain separated**：`PC 18:0_20:4`、`TG 16:0_18:2_22:6` | 见 4.1 互转警告 |
| lipidr 内部/解析 | <https://www.lipidr.org/reference/annotate_lipids.html> | 接受 `'class xx:x/yy:y'` 或 `'class zz:z'`；输出 `clean_name`（如 `PE 34:1`→`PE 34:1`，`Cer d18:0/C22:0`→`Cer 18:0/22:0`）、`class_stub`、`total_cl`、`total_cs`、`Class` | `annotate_lipids()`、`update_molecule_names()` |

### 4.1 互转时的三个坑（都有官方依据）

1. **MS-DIAL 的 `_` 不等于 LIPID MAPS 的 `/`。**
   MS-DIAL 官方把 `PC 18:0_20:4` 放在 "chain separated" 列、`PC 38:4` 放在 "chain summed" 列；而 LIPID MAPS 的层级页明确 `/` 表示 **sn 位置已知**、`_` 表示分子种（位置未知）。两者不要混写成 `PC(18:0_20:4)` 再声称 sn 位置。
2. **lipidr 官方文档只认 `'class xx:x/yy:y'` 与 `'class zz:z'` 两种模式。**
   MS-DIAL 风格的下划线名是否被解析，**官方文档未作说明**，不可假定。落地时必须跑一遍并检查返回的 `not_matched` / `ambig` 列，必要时用 `update_molecule_names()` 改名（三函数均在 <https://www.lipidr.org/reference/index.html> 索引内）。
3. **`lyso`/`LPC` 与 `PC` 的记法差异。**
   LIPID MAPS 系统名不用 "lyso"（只作同义词）；lipidr 用 `LPE`/`LPC` 作 `class_stub`；MS-DIAL 用 `LPC` 且单列 `EtherLPC`。跨库合并时以 `class_stub`/缩写为准，不要用全名做键。

---

## 5. 数据库检索入口（可直接复制）

### 5.1 LIPID MAPS

| 目的 | 入口 |
|---|---|
| 按 LM_ID 取字段 | `https://www.lipidmaps.org/rest/compound/lm_id/{LM_ID}/all` |
| 按 PubChem CID | `https://www.lipidmaps.org/rest/compound/pubchem_cid/{CID}/classification` |
| 按 InChIKey | `https://www.lipidmaps.org/rest/compound/inchi_key/{INCHIKEY}/physchem` |
| 按分子式（可多记录） | `https://www.lipidmaps.org/rest/compound/formula/{FORMULA}/all` |
| 按缩写（sn 已知，可带双键位置） | `https://www.lipidmaps.org/rest/compound/abbrev/{ABBREV}/all/txt`，例 `PC(16:0/20:4(5Z,8Z,11Z,14Z))` |
| 按链组成（位置未知） | `https://www.lipidmaps.org/rest/compound/abbrev_chains/{ABBREV}/all/txt`，例 `PC(16:0_18:0)` |
| 按 m/z + 加合物 + 容差 | `https://www.lipidmaps.org/rest/moverz/LIPIDS/{MZ}/{ION}/{TOL}/{FORMAT}`，例 `.../635.52/M+H/0.5/txt` |
| 按类别批量下载表 | `https://www.lipidmaps.org/rest/compound/lm_id/{LM_CATEGORY}/all/download`，例 `LMGP`（甘油磷脂）、`LMFA03`（类花生酸）、`LM`（全部） |
| 前体离子批量检索（网页） | <https://lipidmaps.org/bulk_search> |
| 精确质量/加合物计算 | `https://www.lipidmaps.org/tools/structuredrawing/masscalc.php`（页面链接形态 `/tools/structuredrawing/masscalc.php`） |
| 由缩写画结构 | `https://www.lipidmaps.org/rest/compound/abbrev/{ABBREV}/structure` |
| 分类树浏览 | <https://www.lipidmaps.org/databases/lmsd/browse> |
| 分类更新（版本留痕） | <https://www.lipidmaps.org/databases/lmsd/classification_updates> |

全部来自 <https://www.lipidmaps.org/resources/rest> 与 <https://www.lipidmaps.org/resources/tools/ms>。

### 5.2 SwissLipids

端点：`https://sparql.swisslipids.org/sparql/`

常用模式（官方示例的用途描述，逐字）：

| 目的 | 官方示例 |
|---|---|
| 类别与标签 | `/examples/SwissLipids/1.html` "Select the SwissLipids categories and their labels." |
| species → isomeric subspecies | `/examples/SwissLipids/7.html` "For a given list of lipid Species, return a list of the corresponding Isomeric subspecies" |
| LIPID MAPS → SwissLipids | `/examples/SwissLipids/9.html` |
| HMDB → SwissLipids | `/examples/SwissLipids/11.html` |
| ChEBI → SwissLipids | `/examples/SwissLipids/13.html` |
| LIPID MAPS → SwissLipids + ChEBI | `/examples/SwissLipids/14.html` |
| LipidX → SwissLipids | `/examples/SwissLipids/15.html` |
| 按 sn1 脂肪酸组分筛脂质 | `/examples/SwissLipids/35.html` "Lipids by fatty acid component (hexadecanoate) at position sn1" |
| 受人类酶作用的脂质 | `/examples/SwissLipids/34.html` |
| 跨库串联（SwissLipids→ChEBI→MolMeDB） | `/examples/SwissLipids/39.html` |

索引页：<https://sib-swiss.github.io/sparql-examples/examples/SwissLipids/>

### 5.3 参考谱图 / 保留时间 / CCS

| 资源 | 入口 | 来源 |
|---|---|---|
| MS-DIAL MSP 谱库（含脂质 in-silico） | `https://systemsomicslab.github.io/compms/msdial/main.html#MSP` | MS-DIAL 官方主页 |
| 脂质理论 MS/MS（LipidBlast fork 模板） | 同上（`.lbm2`、`.xlsx`、`LipidBlast DBs fork *.zip`） | 同上 |
| LC-MS 保留时间检索 | <https://www.metabolomicsworkbench.org/data/search_rt_form.php> | LIPID MAPS MS 工具页 / MS-DIAL 主页 |
| CCS 参考库 | AllCCS <http://allccs.zhulab.cn/>；PNNL <https://metabolomics.pnnl.gov/ccs/> | MS-DIAL 主页 |
| 氧化脂质 | RIKEN oxidized phospholipids MSP（`MSMS-Neg-RikenOxPLs.msp`） | MS-DIAL 主页 |

### 5.4 本包 MCP（实体核对，非注释器）

| 目的 | 工具 | 参数 |
|---|---|---|
| 名字/InChIKey → PubChem CID | `chemistry_pubchem_search` | `query`、`namespace`（`name`/`smiles`/`inchikey`）、`max_results` |
| CID → 分子式/分子量/IsomericSMILES/IUPACName | `chemistry_pubchem_properties` | `cid` |
| 脂质类药物/介质 → ChEMBL ID、SMILES、研发阶段 | `chembl_compound_search` | `name`、`max_results` |

用法见 SKILL.md 第 7 节；**局限**：无加合物计算、无谱图、无 CCS；`MolecularWeight` 是平均分子量，不可当精确质量用。

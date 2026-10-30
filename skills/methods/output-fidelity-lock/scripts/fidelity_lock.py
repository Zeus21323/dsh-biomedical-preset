#!/usr/bin/env python3
"""术语与数据输出保真锁定：提取绑定事实清单、翻译前保护与回填、模板渲染与交付前校验。

子命令：
  extract  从已登记的来源文本投影（文本、Markdown、CSV/TSV、JSON）提取"实体—字段—值—定位"事实，写出 manifest.json
  protect  把文本中的不变量替换为保护标记，供翻译或改写；记录每个保护标记的位置和绑定
  restore  把保护标记回填为原文，并核对保护标记的数量、顺序和实体—值绑定
  render   把 Markdown 模板中的 {{table:...}} / {{rows:...}} / {{value:...}} / {{file:...}} 插槽用源文件原样填充
  verify   按绑定关系对比清单与候选稿：值丢失、值改动、绑定到错误实体、精度改动、凭空新增、来源实体丢失；
           表格输出可与源表逐格对比。形式差异（大小写、连字符、希腊字母、氨基酸记法）只作警告。

只依赖标准库，只处理可解码文本；PDF/DOCX/XLSX 必须先由代理生成带定位信息的文本投影再登记。
所有输入只读；输出写到调用方指定的路径，已存在的输出默认不覆盖。
退出码：0 通过；1 发现必须处理的问题；2 参数或输入错误；3 无错误但存在不可校验范围。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_PATTERNS = SCRIPT_DIR.parent / "references" / "不变量模式.json"
PLACEHOLDER_RE = re.compile(r"⟦INV(\d{4,})⟧")
TABULAR_SUFFIXES = {".csv", ".tsv", ".txt", ".tab"}
MAX_SOURCE_BYTES = 200 * 1024 * 1024
ENTITY_KINDS = {"identifier", "name", "sequence", "path"}
VALUE_KINDS = {"number", "date"}
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。；;!?！？\n])|(?<=[^\d]\.)\s+(?=[A-Z\u3400-\u9fff])")
NUMBER_TOKEN_RE = re.compile(
    r"^(?P<cmp>[<>≤≥]\s?=?\s?)?(?P<sign>[-−+])?(?P<mant>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)"
    r"(?:\s?(?:[×x]\s?10\s?[\^]?\s?(?P<exp1>[-−⁻+⁺]?[⁰¹²³⁴⁵⁶⁷⁸⁹\d]+)|[eE](?P<exp2>[-−+]?\d+)))?\s?(?P<pct>%)?$"
)
CHINESE_NUMERAL_RE = re.compile(r"(?<![\u3400-\u9fff])[零一二两三四五六七八九十百千万]{1,8}(?![\u3400-\u9fff]*[分之])")
ENGLISH_NUMERAL_RE = re.compile(
    r"\b(?:(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    r"seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million)"
    r"(?:[\s-](?:and[\s-])?)?){1,6}\b",
    re.IGNORECASE,
)
CHINESE_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CHINESE_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
ENGLISH_DIGITS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
ENGLISH_MULTIPLIERS = {"hundred": 100, "thousand": 1000, "million": 1_000_000}


# ---------------------------------------------------------------------------
# 模式加载
# ---------------------------------------------------------------------------


@dataclass
class Category:
    id: str
    name_cn: str
    kind: str
    regex: re.Pattern
    novel_check: bool
    versioned: bool
    post_filter: str | None = None
    require_digit: bool = False
    data_like_only: bool = False


@dataclass
class Patterns:
    categories: list[Category]
    stoplist: set[str]
    greek_map: dict[str, str]
    amino_acid_map: dict[str, str]
    field_labels: dict[str, str]
    english_stopwords: set[str]
    identifier_columns: set[str]
    numeric_columns: set[str]


def load_patterns(path: Path) -> Patterns:
    data = json.loads(path.read_text(encoding="utf-8"))
    categories = [
        Category(
            id=item["id"], name_cn=item["name_cn"], kind=item["kind"], regex=re.compile(item["pattern"]),
            novel_check=bool(item.get("novel_check", False)), versioned=bool(item.get("versioned", False)),
            post_filter=item.get("post_filter"), require_digit=bool(item.get("require_digit", False)),
            data_like_only=bool(item.get("data_like_only", False)),
        )
        for item in data["categories"]
    ]
    labels: dict[str, str] = {}
    for canonical, aliases in data.get("field_labels", {}).items():
        if isinstance(aliases, list):
            for alias in aliases:
                labels[re.sub(r"[\s_.\-]", "", alias.lower())] = canonical
    hints = data.get("table_column_hints", {})
    return Patterns(
        categories=categories,
        stoplist={s.upper() for s in data.get("gene_symbol_stoplist", [])},
        greek_map=data.get("greek_map", {}),
        amino_acid_map=data.get("amino_acid_map", {}),
        field_labels=labels,
        english_stopwords={w.upper() for w in data.get("english_stopwords", [])},
        identifier_columns={c.lower() for c in hints.get("identifier_columns", [])},
        numeric_columns={c.lower() for c in hints.get("numeric_columns", [])},
    )


# ---------------------------------------------------------------------------
# 不变量识别
# ---------------------------------------------------------------------------


@dataclass
class Hit:
    value: str
    category: str
    kind: str
    start: int
    end: int


def data_like_number(token: str) -> bool:
    """只把“看起来是数据”的数字当作不变量：小数、科学计数、阈值、百分比、带符号或两位以上整数。"""
    stripped = token.strip()
    if any(ch in stripped for ch in ".,eE×x^%<>≤≥"):
        return True
    if stripped.startswith(("-", "−", "+")):
        return True
    return len(re.sub(r"\D", "", stripped)) >= 2


def keep_gene_symbol(token: str, patterns: Patterns) -> bool:
    parts = re.split(r"(?:::|[-–/])", token)
    core = re.sub(r"[αβγδεκλ]|alpha|beta|gamma|delta|epsilon|kappa|lambda", "", parts[0]).upper()
    if core in patterns.stoplist or any(part.upper() in patterns.stoplist for part in parts):
        return False
    if re.search(r"\d", token):
        return True
    return 3 <= len(core) <= 8


def keep_fusion(token: str, patterns: Patterns) -> bool:
    parts = re.split(r"(?:::|[-–/])", token)
    return len(parts) == 2 and all(keep_gene_symbol(p, patterns) and re.search(r"\d|[A-Z]{3,}", p) for p in parts)


def find_hits(text: str, patterns: Patterns) -> list[Hit]:
    occupied: list[tuple[int, int]] = []
    hits: list[Hit] = []

    # 先标记所有 citation 区间（方括号里的纯数字）
    citation_re = re.compile(r"\[\d+(?:-\d+)?(?:\s*,\s*\d+)*\]")
    for match in citation_re.finditer(text):
        occupied.append((match.start(), match.end()))

    def overlaps(start: int, end: int) -> bool:
        return any(start < b and end > a for a, b in occupied)

    for category in patterns.categories:
        for match in category.regex.finditer(text):
            token = match.group(0).strip()
            if not token:
                continue
            start = match.start() + (len(match.group(0)) - len(match.group(0).lstrip()))
            end = start + len(token)
            if overlaps(start, end):
                continue
            if category.post_filter == "gene-symbol" and not keep_gene_symbol(token, patterns):
                continue
            if category.post_filter == "fusion" and not keep_fusion(token, patterns):
                continue
            if category.post_filter == "capitalized" and (token.upper() in patterns.stoplist
                                                          or token.upper() in patterns.english_stopwords):
                continue
            if category.require_digit and not re.search(r"\d", token):
                continue
            if category.kind in ENTITY_KINDS and token.upper() in patterns.english_stopwords:
                continue
            if category.data_like_only and not data_like_number(token):
                continue
            hits.append(Hit(token, category.id, category.kind, start, end))
            occupied.append((start, end))
    hits.sort(key=lambda h: h.start)
    return hits


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------


def normalize_superscript(s: str) -> str:
    """将 Unicode 上标数字和符号转为 ASCII。"""
    return s.translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+"))


def parse_number(token: str) -> float | None:
    normalized = normalize_superscript(token.strip())
    match = NUMBER_TOKEN_RE.match(normalized)
    if not match:
        return None
    try:
        value = float(match.group("mant").replace(",", ""))
    except ValueError:
        return None
    if match.group("sign") in ("-", "−"):
        value = -value
    exp = match.group("exp1") or match.group("exp2")
    if exp:
        value *= 10 ** int(exp.replace("−", "-").replace("⁻", "-").replace("⁺", "+"))
    return value


def number_key(token: str) -> str | None:
    """数值等价键：数值、比较符和百分号都参与，保证 <0.05 与 0.05、5% 与 5 不等价。"""
    normalized = normalize_superscript(token.strip())
    match = NUMBER_TOKEN_RE.match(normalized)
    value = parse_number(token)
    if match is None or value is None or not math.isfinite(value):
        return None
    prefix = (match.group("cmp") or "").replace(" ", "")
    suffix = match.group("pct") or ""
    return f"{prefix}{format(value, '.12g')}{suffix}"


def plain_integer_key(token: str) -> str | None:
    """独立纯整数（无小数、指数、符号、比较符、百分号、千分位）的等价键，允许与中英文数字词互换。"""
    stripped = token.strip()
    if re.fullmatch(r"\d+", stripped):
        return format(int(stripped), "d")
    return None


def chinese_numeral_to_int(text: str) -> int | None:
    total, section, number = 0, 0, 0
    if not text or any(ch not in CHINESE_DIGITS and ch not in CHINESE_UNITS for ch in text):
        return None
    if all(ch in CHINESE_DIGITS for ch in text):
        return int("".join(str(CHINESE_DIGITS[ch]) for ch in text))
    for ch in text:
        if ch in CHINESE_DIGITS:
            number = CHINESE_DIGITS[ch]
        else:
            unit = CHINESE_UNITS[ch]
            if unit == 10000:
                total += (section + number) * unit
                section, number = 0, 0
            else:
                section += (number if number else 1) * unit
                number = 0
    return total + section + number


def english_numeral_to_int(text: str) -> int | None:
    words = [w for w in re.split(r"[\s-]+", text.lower().strip()) if w and w != "and"]
    if not words:
        return None
    total, current = 0, 0
    for word in words:
        if word in ENGLISH_DIGITS:
            current += ENGLISH_DIGITS[word]
        elif word in ENGLISH_MULTIPLIERS:
            if current == 0:
                current = 1
            if word == "hundred":
                current *= 100
            else:
                total += current * ENGLISH_MULTIPLIERS[word]
                current = 0
        else:
            return None
    return total + current


def strip_version(token: str) -> str:
    return re.sub(r"\.\d+$", "", token)


def normalize_entity(token: str, patterns: Patterns) -> str:
    text = token
    if re.match(r"p\.\(?", text):
        for three, one in patterns.amino_acid_map.items():
            text = text.replace(three, one)
    for greek, latin in sorted(patterns.greek_map.items(), key=lambda kv: -len(kv[0])):
        text = text.replace(greek, latin)
    text = re.sub(r"^PMID:?\s?", "PMID", text)
    text = text.replace("::", "-").replace("–", "-").replace("_", "-")
    text = re.sub(r"[\s\-/()]", "", text)
    return strip_version(text).upper()


def canonical_field(label: str, patterns: Patterns) -> str:
    """从值附近的文字里找字段标签：从后往前找已知别名（含中文子串和英文双词），否则取最后一个实词。"""
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9.\-]*|[\u3400-\u9fff]+", label)
    tokens = [t.strip(".-") for t in tokens if t.strip(".-")]
    aliases = sorted(patterns.field_labels.items(), key=lambda kv: -len(kv[0]))
    for index in range(len(tokens) - 1, -1, -1):
        token = tokens[index]
        cleaned = re.sub(r"[\s_.\-]", "", token.lower())
        if cleaned in patterns.field_labels:
            return patterns.field_labels[cleaned]
        if re.search(r"[\u3400-\u9fff]", cleaned):
            for alias, canonical in aliases:
                if re.search(r"[\u3400-\u9fff]", alias) and alias in cleaned:
                    return canonical
        else:
            for alias, canonical in aliases:
                if len(alias) >= 3 and cleaned.endswith(alias):
                    return canonical
            if index > 0:
                bigram = re.sub(r"[\s_.\-]", "", (tokens[index - 1] + tokens[index]).lower())
                if bigram in patterns.field_labels:
                    return patterns.field_labels[bigram]
    for token in reversed(tokens):
        cleaned = re.sub(r"[\s_.\-]", "", token.lower())
        if cleaned and cleaned.upper() not in patterns.english_stopwords:
            return cleaned[-24:]
    return ""


def edit_distance_leq(a: str, b: str, limit: int) -> bool:
    if abs(len(a) - len(b)) > limit:
        return False
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb)))
        if min(current) > limit:
            return False
        previous = current
    return previous[-1] <= limit


# ---------------------------------------------------------------------------
# 输入读取
# ---------------------------------------------------------------------------


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    if path.stat().st_size > MAX_SOURCE_BYTES:
        raise SystemExit(f"输入超过 {MAX_SOURCE_BYTES // (1024 * 1024)} MB 保护上限，请先拆分：{path}")
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法按 UTF-8 或 GB18030 解码（PDF/DOCX/XLSX 需先生成文本投影）：{path}")


def sniff_delimiter(path: Path, text: str) -> str | None:
    if path.suffix.lower() == ".csv":
        return ","
    if path.suffix.lower() in {".tsv", ".tab"}:
        return "\t"
    lines = text[:4096].splitlines()
    if lines and "\t" in lines[0]:
        return "\t"
    if lines and lines[0].count(",") >= 2:
        return ","
    return None


def read_table(path: Path, text: str) -> tuple[list[str], list[list[str]]] | None:
    delimiter = sniff_delimiter(path, text)
    if delimiter is None:
        return None
    rows = [row for row in csv.reader(text.splitlines(), delimiter=delimiter) if row]
    if len(rows) < 2 or Counter(len(row) for row in rows).most_common(1)[0][0] < 2:
        return None
    return rows[0], rows[1:]


# ---------------------------------------------------------------------------
# 事实提取：实体—字段—值—定位
# ---------------------------------------------------------------------------


@dataclass
class Fact:
    entity: str            # 原文实体，"" 表示句中没有实体的独立值
    entity_key: str
    entity_category: str
    field: str             # 规范化字段标签，可能为空
    value: str             # 原文值
    value_key: str         # 等价键
    value_category: str
    kind: str              # number / date
    locus: dict


@dataclass
class Entity:
    value: str
    key: str
    category: str
    kind: str
    locus: dict
    alias_of: str = ""     # 表格同一行的其他标识符列指向主键实体


def sentences_of(text: str) -> list[tuple[int, str]]:
    result = []
    cursor = 0
    for piece in SENTENCE_SPLIT_RE.split(text):
        if piece is None:
            continue
        if piece.strip():
            result.append((cursor, piece))
        cursor += len(piece)
    return result


def extract_tuples(text: str, label: str, patterns: Patterns) -> tuple[list[Fact], list[Entity], list[tuple[int, int]]]:
    """提取紧凑模式：Gene（FC, FDR）、Gene 组 n=36 等中文字段标签绑定。"""
    # 1. Gene(FC=val1, FDR=val2) 或 Gene（val1, val2）
    tuple_re = re.compile(
        r"([A-Za-z][A-Za-z0-9_.-]+)(?:自身|基因|蛋白|mRNA)?\s*[（(]\s*"
        r"(?:(?i:FC)\s*[=:：]\s*)?([0-9.,]+(?:\s?[×x]\s?10\s?[\^]?\s?[⁻⁺\-+]?[⁰¹²³⁴⁵⁶⁷⁸⁹\d]+|[eE][+\-−⁻⁺]?\d+)?)\s*[,，;；]\s*"
        r"(?:(?i:FDR)\s*[=:：]\s*)?([0-9.,<>≤≥]+(?:\s?[×x]\s?10\s?[\^]?\s?[⁻⁺\-+]?[⁰¹²³⁴⁵⁶⁷⁸⁹\d]+|[eE][+\-−⁻⁺]?\d+)?)\s*[）)]"
    )
    # 2. Gene 组 n=36（中文字段标签）
    labeled_field_re = re.compile(
        r"([A-Za-z][A-Za-z0-9_.-]+)\s+([一-鿿]{1,4})\s+([A-Za-z]+)\s*[=:：]\s*"
        r"([0-9.,]+(?:\s?[×x]\s?10\s?[\^]?\s?[⁻⁺\-+]?[⁰¹²³⁴⁵⁶⁷⁸⁹\d]+|[eE][+\-−⁻⁺]?\d+)?)"
    )
    facts: list[Fact] = []
    entities: list[Entity] = []
    spans: list[tuple[int, int]] = []
    seen_entities = set()

    # Extract FC/FDR tuples
    for match in tuple_re.finditer(text):
        gene, fc_raw, fdr_raw = match.group(1), match.group(2), match.group(3)
        fc_key = number_key(fc_raw)
        fdr_key = number_key(fdr_raw)
        if fc_key is None or fdr_key is None:
            continue
        if gene.upper() in patterns.stoplist or gene.upper() in patterns.english_stopwords:
            continue
        spans.append((match.start(), match.end()))
        gene_norm = normalize_entity(gene, patterns)
        if gene_norm not in seen_entities:
            entities.append(Entity(gene, gene_norm, "tuple-gene", "identifier",
                                   {"file": label, "line": line_of(text, match.start())}))
            seen_entities.add(gene_norm)
        facts.append(Fact(
            entity=gene, entity_key=gene_norm, entity_category="tuple-gene",
            field="fc", value=fc_raw, value_key=fc_key, value_category="tuple-number", kind="number",
            locus={"file": label, "line": line_of(text, match.start())}
        ))
        facts.append(Fact(
            entity=gene, entity_key=gene_norm, entity_category="tuple-gene",
            field="fdr", value=fdr_raw, value_key=fdr_key, value_category="tuple-number", kind="number",
            locus={"file": label, "line": line_of(text, match.start())}
        ))

    # Extract labeled field patterns: Gene 组 n=36
    for match in labeled_field_re.finditer(text):
        gene, cn_label, en_field, value_raw = match.group(1), match.group(2), match.group(3), match.group(4)
        value_key = number_key(value_raw)
        if value_key is None:
            continue
        if gene.upper() in patterns.stoplist or gene.upper() in patterns.english_stopwords:
            continue
        spans.append((match.start(), match.end()))
        gene_norm = normalize_entity(gene, patterns)
        if gene_norm not in seen_entities:
            entities.append(Entity(gene, gene_norm, "labeled-field-gene", "identifier",
                                   {"file": label, "line": line_of(text, match.start())}))
            seen_entities.add(gene_norm)
        field_name = f"{cn_label}{en_field.lower()}"
        facts.append(Fact(
            entity=gene, entity_key=gene_norm, entity_category="labeled-field-gene",
            field=field_name, value=value_raw, value_key=value_key, value_category="labeled-field-number",
            kind="number", locus={"file": label, "line": line_of(text, match.start())}
        ))
    return facts, entities, spans


def numeral_word_hits(text: str, occupied: list[Hit], known_ints: set[str]) -> list[Hit]:
    """把中英文整数词识别为数值命中；只接受来源里确实存在的纯整数，避免把普通量词当作数据。"""
    hits: list[Hit] = []
    taken = [(h.start, h.end) for h in occupied]
    for regex, convert in ((ENGLISH_NUMERAL_RE, english_numeral_to_int), (CHINESE_NUMERAL_RE, chinese_numeral_to_int)):
        for match in regex.finditer(text):
            word = match.group(0).strip(" -")
            if not word:
                continue
            value = convert(word)
            if value is None or value <= 0 or format(value, "d") not in known_ints:
                continue
            start = match.start() + (len(match.group(0)) - len(match.group(0).lstrip(" -")))
            end = start + len(word)
            if any(start < b and end > a for a, b in taken):
                continue
            hits.append(Hit(format(value, "d"), "numeral-word", "number", start, end))
            taken.append((start, end))
    return hits


def is_threshold_context(text: str, val_start: int, sentence_start: int) -> bool:
    """判断数值是否处于筛选阈值上下文中（如"筛选出 FDR < 0.05 的基因"），不应绑定到具体实体。"""
    before_val = text[sentence_start:val_start].lower()
    # 筛选/过滤关键词出现在数值前面
    threshold_keywords = ["筛选", "过滤", "满足", "符合", "阈值", "threshold", "filter", "criteria", "cutoff"]
    return any(kw in before_val[-50:] for kw in threshold_keywords)


def facts_from_text(text: str, label: str, patterns: Patterns,
                    known_ints: set[str] | None = None) -> tuple[list[Fact], list[Entity], list[Hit]]:
    tuple_facts, tuple_entities, tuple_spans = extract_tuples(text, label, patterns)
    all_hits = find_hits(text, patterns)
    if known_ints:
        all_hits = sorted(all_hits + numeral_word_hits(text, all_hits, known_ints), key=lambda h: h.start)
    # 紧凑元组内的值已由 extract_tuples 绑定，通用按句绑定不再处理这些区间
    hits = [h for h in all_hits if not any(a <= h.start < b for a, b in tuple_spans) or h.kind in ENTITY_KINDS]
    facts: list[Fact] = list(tuple_facts)
    entities: list[Entity] = list(tuple_entities)
    for offset, sentence in sentences_of(text):
        end = offset + len(sentence)
        local = [h for h in hits if offset <= h.start < end]
        ents = [h for h in local if h.kind in ENTITY_KINDS]
        vals = [h for h in local if h.kind in VALUE_KINDS]
        for ent in ents:
            entities.append(Entity(ent.value, normalize_entity(ent.value, patterns), ent.category, ent.kind,
                                   {"file": label, "line": line_of(text, ent.start)}))
        for val in vals:
            # 阈值上下文中的数值保持独立，不绑定到实体
            if val.kind == "number" and is_threshold_context(text, val.start, offset):
                key = number_key(val.value)
                if key is None:
                    continue
                facts.append(Fact(
                    entity="", entity_key="", entity_category="",
                    field="", value=val.value, value_key=key, value_category=val.category, kind=val.kind,
                    locus={"file": label, "line": line_of(text, val.start)},
                ))
                continue

            preceding = [e for e in ents if e.end <= val.start]
            anchor = preceding[-1] if preceding else (ents[0] if ents else None)
            previous_end = max([h.end for h in local if h.end <= val.start], default=offset)
            label_text = text[previous_end:val.start]
            field_name = canonical_field(label_text, patterns)
            if not field_name and anchor is not None:
                before_anchor = max([h.end for h in local if h.end <= anchor.start], default=offset)
                field_name = canonical_field(text[before_anchor:anchor.start], patterns)
            key = number_key(val.value) if val.kind == "number" else re.sub(r"[\s年月日]", "-", val.value).strip("-")
            if key is None:
                continue
            facts.append(Fact(
                entity=anchor.value if anchor else "",
                entity_key=normalize_entity(anchor.value, patterns) if anchor else "",
                entity_category=anchor.category if anchor else "",
                field=field_name,
                value=val.value, value_key=key, value_category=val.category, kind=val.kind,
                locus={"file": label, "line": line_of(text, val.start)},
            ))
    return facts, entities, hits


def facts_from_table(header: list[str], rows: list[list[str]], label: str, patterns: Patterns) -> tuple[list[Fact], list[Entity], dict]:
    lowered = [col.strip().lower() for col in header]
    key_col = next((i for i, col in enumerate(lowered) if col in patterns.identifier_columns), 0)
    alias_cols = [i for i, col in enumerate(lowered) if col in patterns.identifier_columns and i != key_col]
    num_cols = [i for i, col in enumerate(lowered) if col in patterns.numeric_columns]
    if not num_cols:
        num_cols = [i for i in range(len(header)) if i != key_col and
                    sum(1 for row in rows[:50] if i < len(row) and parse_number(row[i]) is not None) > len(rows[:50]) / 2]
    facts: list[Fact] = []
    entities: list[Entity] = []
    for row_index, row in enumerate(rows, 2):
        if key_col >= len(row) or not row[key_col].strip():
            continue
        entity = row[key_col].strip()
        primary_key = normalize_entity(entity, patterns)
        entities.append(Entity(entity, primary_key, "table-key", "identifier",
                               {"file": label, "line": row_index, "column": header[key_col]}))
        for col in alias_cols:
            if col < len(row) and row[col].strip():
                alias = row[col].strip()
                entities.append(Entity(alias, normalize_entity(alias, patterns), "table-alias", "identifier",
                                       {"file": label, "line": row_index, "column": header[col]}, alias_of=primary_key))
        for col in num_cols:
            if col >= len(row) or not row[col].strip():
                continue
            raw = row[col].strip()
            key = number_key(raw)
            if key is None:
                key = raw.upper()  # NA、NaN、Inf 等按字面比较
            facts.append(Fact(entity, normalize_entity(entity, patterns), "table-key",
                              canonical_field(header[col], patterns), raw, key, "table-number", "number",
                              {"file": label, "line": row_index, "column": header[col]}))
    summary = {
        "file": label, "n_rows": len(rows), "n_columns": len(header), "header": header,
        "key_column": header[key_col], "numeric_columns": [header[i] for i in num_cols],
        "key_values_sha256": hashlib.sha256("\n".join(r[key_col] if key_col < len(r) else "" for r in rows).encode()).hexdigest(),
    }
    return facts, entities, summary


def cmd_extract(args: argparse.Namespace) -> int:
    patterns = load_patterns(Path(args.patterns))
    output = Path(args.output)
    if output.exists() and not args.overwrite:
        print(f"清单已存在，未覆盖：{output}（如需覆盖请加 --overwrite）", file=sys.stderr)
        return 2
    facts: list[Fact] = []
    entities: list[Entity] = []
    sources: list[dict] = []
    tables: list[dict] = []
    if args.text:
        f, e, _ = facts_from_text(args.text, "<inline>", patterns)
        facts += f
        entities += e
        sources.append({"file": "<inline>", "sha256": hashlib.sha256(args.text.encode()).hexdigest(),
                        "bytes": len(args.text.encode("utf-8")), "projection": "inline"})
    for raw in args.inputs:
        path = Path(raw)
        if not path.is_file():
            print(f"输入不存在或不是文件：{path}", file=sys.stderr)
            return 2
        text = read_text(path)
        label = path.name if args.basename_only else str(path)
        sources.append({"file": label, "sha256": sha256_of(path), "bytes": path.stat().st_size,
                        "projection": "text-projection" if args.projection_of else "original-text",
                        "projection_of": args.projection_of or None})
        table = read_table(path, text) if path.suffix.lower() in TABULAR_SUFFIXES else None
        if table is not None:
            tf, te, summary = facts_from_table(table[0], table[1], label, patterns)
            facts += tf
            entities += te
            tables.append(summary)
        else:
            f, e, _ = facts_from_text(text, label, patterns)
            facts += f
            entities += e
    if not facts and not entities:
        print("来源中没有识别到任何实体或数值；请确认文本投影是否完整。", file=sys.stderr)
    manifest = {
        "schema": "fidelity-manifest/2",
        "patterns": Path(args.patterns).name,
        "sources": sources,
        "tables": tables,
        "unverifiable": list(args.unverifiable or []),
        "entities": [asdict(e) for e in entities],
        "facts": [asdict(f) for f in facts],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    distinct_entities = {e.key for e in entities}
    bound = sum(1 for f in facts if f.entity_key)
    print(f"已写出事实清单：{output}")
    print(f"来源 {len(sources)} 个，表格 {len(tables)} 张，实体 {len(distinct_entities)} 个，"
          f"值 {len(facts)} 个（其中 {bound} 个绑定到实体，{len(facts) - bound} 个独立）。")
    if manifest["unverifiable"]:
        print(f"登记的不可校验范围：{len(manifest['unverifiable'])} 项；交付时必须明示。")
    return 0


# ---------------------------------------------------------------------------
# protect / restore
# ---------------------------------------------------------------------------


def cmd_protect(args: argparse.Namespace) -> int:
    patterns = load_patterns(Path(args.patterns))
    source = Path(args.input)
    text = read_text(source)
    output, mapping_path = Path(args.output), Path(args.mapping)
    for target in (output, mapping_path):
        if target.exists() and not args.overwrite:
            print(f"目标已存在，未覆盖：{target}", file=sys.stderr)
            return 2
    hits = find_hits(text, patterns)
    if args.skip_kinds:
        skip = set(args.skip_kinds.split(","))
        hits = [hit for hit in hits if hit.kind not in skip]
    mapping: dict[str, dict] = {}
    value_to_key: dict[str, str] = {}
    pieces: list[str] = []
    cursor = 0
    sequence: list[str] = []
    for hit in hits:
        key = value_to_key.get(hit.value)
        if key is None:
            key = f"⟦INV{len(mapping) + 1:04d}⟧"
            value_to_key[hit.value] = key
            mapping[key] = {"value": hit.value, "category": hit.category, "kind": hit.kind, "count": 0}
        mapping[key]["count"] += 1
        sequence.append(key)
        pieces.append(text[cursor:hit.start])
        pieces.append(key)
        cursor = hit.end
    pieces.append(text[cursor:])
    protected = "".join(pieces)
    bindings = placeholder_bindings(protected, mapping)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(protected, encoding="utf-8")
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(json.dumps({
        "schema": "fidelity-placeholders/2", "source": source.name, "source_sha256": sha256_of(source),
        "placeholders": mapping, "sequence": sequence, "bindings": bindings,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已保护 {len(hits)} 处、{len(mapping)} 个不同不变量 → {output}")
    print(f"映射文件：{mapping_path}。翻译或改写时保护标记必须原样保留且不得互换位置，完成后运行 restore 回填。")
    return 0


def placeholder_bindings(protected: str, mapping: dict[str, dict]) -> list[dict]:
    """每个值保护标记按句绑定到最近的前一个实体保护标记；用于回填时核对位置没有互换。"""
    bindings = []
    for offset, sentence in sentences_of(protected):
        occurrences = [(m.start() + offset, m.group(0)) for m in PLACEHOLDER_RE.finditer(sentence)]
        ents = [(pos, key) for pos, key in occurrences if mapping[key]["kind"] in ENTITY_KINDS]
        for pos, key in occurrences:
            if mapping[key]["kind"] not in VALUE_KINDS:
                continue
            preceding = [k for p, k in ents if p < pos]
            anchor = preceding[-1] if preceding else (ents[0][1] if ents else None)
            bindings.append({"value": key, "entity": anchor})
    return bindings


def cmd_restore(args: argparse.Namespace) -> int:
    text = read_text(Path(args.input))
    mapping_doc = json.loads(Path(args.mapping).read_text(encoding="utf-8"))
    mapping = mapping_doc["placeholders"]
    output = Path(args.output)
    if output.exists() and not args.overwrite:
        print(f"目标已存在，未覆盖：{output}", file=sys.stderr)
        return 2
    problems: list[str] = []
    warnings: list[str] = []
    seen = Counter(m.group(0) for m in PLACEHOLDER_RE.finditer(text))
    for key, entry in mapping.items():
        if seen.get(key, 0) == 0:
            problems.append(f"保护标记丢失：{key} 应回填 {entry['value']!r}（原文出现 {entry['count']} 次）")
        elif seen[key] != entry["count"]:
            problems.append(f"保护标记次数变化：{key}（{entry['value']!r}）原 {entry['count']} 次，现 {seen[key]} 次")
    for key in seen:
        if key not in mapping:
            problems.append(f"出现映射中不存在的保护标记：{key}")
    for item in re.findall(r"⟦(?!INV\d{4,}⟧)[^⟧]{0,12}⟧?|(?<!⟦)INV\d{4,}(?!⟧)", text)[:20]:
        problems.append(f"保护标记疑似被破坏：{item!r}")
    expected = Counter((b["value"], b["entity"]) for b in mapping_doc.get("bindings", []))
    actual = Counter((b["value"], b["entity"]) for b in placeholder_bindings(text, mapping)) if all(
        k in mapping for k in seen) else Counter()
    for (value_key, entity_key), count in expected.items():
        if actual.get((value_key, entity_key), 0) < count:
            got = [e for v, e in actual if v == value_key]
            value = mapping[value_key]["value"]
            expected_entity = mapping[entity_key]["value"] if entity_key else "（独立值）"
            got_entity = ", ".join(mapping[g]["value"] if g else "（独立值）" for g in got) or "（未出现）"
            problems.append(f"绑定改变：值 {value!r} 原属 {expected_entity!r}，现在跟随 {got_entity}")
    if not problems and mapping_doc.get("sequence") and [m.group(0) for m in PLACEHOLDER_RE.finditer(text)] != mapping_doc["sequence"]:
        warnings.append("保护标记整体顺序与原文不同（语序调整可接受，绑定已核对一致）")
    restored = PLACEHOLDER_RE.sub(lambda m: mapping.get(m.group(0), {}).get("value", m.group(0)), text)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(restored, encoding="utf-8")
    print(f"已回填 {sum(seen.values())} 处保护标记 → {output}")
    for warning in warnings:
        print(f"  [warning] {warning}")
    if problems:
        print("回填检查未通过：")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("回填检查通过：保护标记数量与实体—值绑定均与原文一致。")
    return 0


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------

SLOT_RE = re.compile(r"\{\{\s*(table|value|file|rows)\s*:\s*([^}]+?)\s*\}\}")


def markdown_table(header: list[str], rows: list[list[str]]) -> str:
    def cell(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")

    lines = ["| " + " | ".join(cell(c) for c in header) + " |", "| " + " | ".join("---" for _ in header) + " |"]
    for row in rows:
        padded = row + [""] * (len(header) - len(row))
        lines.append("| " + " | ".join(cell(v) for v in padded[: len(header)]) + " |")
    return "\n".join(lines)


def resolve_slot(kind: str, spec: str, base: Path, log: list[str]) -> str:
    parts = [part.strip() for part in spec.split(":")]
    path = base / parts[0]
    if not path.is_file():
        raise ValueError(f"插槽引用的文件不存在：{parts[0]}")
    text = read_text(path)
    if kind == "file":
        log.append(f"file {parts[0]}：{len(text.splitlines())} 行原样嵌入")
        return text.rstrip("\n")
    table = read_table(path, text)
    if table is None:
        raise ValueError(f"插槽引用的文件不是可解析表格：{parts[0]}")
    header, rows = table
    if kind == "table":
        limit = int(parts[1]) if len(parts) > 1 and parts[1] else len(rows)
        columns = parts[2].split(",") if len(parts) > 2 and parts[2] else None
        selected = rows[:limit]
        if columns:
            indexes = []
            for column in columns:
                if column.strip() not in header:
                    raise ValueError(f"表 {parts[0]} 没有列 {column.strip()!r}")
                indexes.append(header.index(column.strip()))
            header = [header[i] for i in indexes]
            selected = [[row[i] if i < len(row) else "" for i in indexes] for row in selected]
        log.append(f"table {parts[0]}：{len(selected)}/{len(rows)} 行，列 {len(header)}")
        return markdown_table(header, selected)
    if kind == "rows":
        if len(parts) < 3:
            raise ValueError("rows 插槽格式为 {{rows:文件:列名:值1,值2}}")
        column, wanted = parts[1], [v.strip() for v in parts[2].split(",")]
        if column not in header:
            raise ValueError(f"表 {parts[0]} 没有列 {column!r}")
        index = header.index(column)
        selected = [row for row in rows if index < len(row) and row[index].strip() in wanted]
        missing = [v for v in wanted if not any(index < len(r) and r[index].strip() == v for r in rows)]
        if missing:
            raise ValueError(f"表 {parts[0]} 的列 {column} 中找不到：{', '.join(missing)}")
        log.append(f"rows {parts[0]}：按 {column} 选出 {len(selected)} 行")
        return markdown_table(header, selected)
    if kind == "value":
        if len(parts) != 3:
            raise ValueError("value 插槽格式为 {{value:文件:键列=键值:目标列}} 或 {{value:文件:行号:目标列}}")
        locator, target = parts[1], parts[2]
        if target not in header:
            raise ValueError(f"表 {parts[0]} 没有列 {target!r}")
        target_index = header.index(target)
        if "=" in locator:
            key_col, key_val = locator.split("=", 1)
            if key_col not in header:
                raise ValueError(f"表 {parts[0]} 没有列 {key_col!r}")
            key_index = header.index(key_col)
            matches = [row for row in rows if key_index < len(row) and row[key_index].strip() == key_val.strip()]
            if len(matches) != 1:
                raise ValueError(f"表 {parts[0]} 中 {key_col}={key_val} 匹配 {len(matches)} 行，必须唯一")
            row = matches[0]
        else:
            row_number = int(locator)
            if not 1 <= row_number <= len(rows):
                raise ValueError(f"表 {parts[0]} 行号 {row_number} 越界（共 {len(rows)} 行数据）")
            row = rows[row_number - 1]
        value = row[target_index] if target_index < len(row) else ""
        log.append(f"value {parts[0]}[{locator}].{target} = {value!r}")
        return value
    raise ValueError(f"未知插槽类型：{kind}")


def cmd_render(args: argparse.Namespace) -> int:
    template = Path(args.template)
    text = read_text(template)
    base = Path(args.base) if args.base else template.parent
    output = Path(args.output)
    if output.exists() and not args.overwrite:
        print(f"目标已存在，未覆盖：{output}", file=sys.stderr)
        return 2
    log: list[str] = []
    errors: list[str] = []

    def replace(match: re.Match) -> str:
        try:
            return resolve_slot(match.group(1), match.group(2), base, log)
        except (ValueError, OSError) as exc:
            errors.append(f"第 {line_of(text, match.start())} 行 {match.group(0)}：{exc}")
            return match.group(0)

    rendered = SLOT_RE.sub(replace, text)
    if errors:
        print("渲染失败，未写出文件：")
        for error in errors:
            print(f"  - {error}")
        return 1
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"已渲染 {len(log)} 个插槽 → {output}")
    for entry in log:
        print(f"  - {entry}")
    return 0


# ---------------------------------------------------------------------------
# verify：按绑定关系对比
# ---------------------------------------------------------------------------


@dataclass
class Finding:
    level: str  # error / warning / info
    kind: str
    entity: str
    field: str
    expected: str
    got: str
    detail: str
    line: int | None = None


def rounding_match(source: float, candidate: float) -> bool:
    if source == candidate or source == 0:
        return False
    for digits in range(0, 8):
        if round(source, digits) == candidate and round(source, digits) != source:
            return True
    for sig in range(1, 7):
        rounded = float(format(source, f".{sig}g"))
        if rounded == candidate and rounded != source:
            return True
    return False


def numeral_word_keys(text: str) -> set[str]:
    keys: set[str] = set()
    for match in CHINESE_NUMERAL_RE.finditer(text):
        value = chinese_numeral_to_int(match.group(0))
        if value is not None:
            keys.add(format(value, "d"))
    for match in ENGLISH_NUMERAL_RE.finditer(text):
        value = english_numeral_to_int(match.group(0))
        if value is not None and value > 0:
            keys.add(format(value, "d"))
    return keys


def verify_text(candidate: str, manifest: dict, patterns: Patterns, mode: str, allow_novel: set[str],
                require_all: bool, form_as_error: bool) -> list[Finding]:
    findings: list[Finding] = []
    seen: set[tuple] = set()
    category_by_id = {c.id: c for c in patterns.categories}
    translate = mode == "translate"
    missing_level = "error" if translate or require_all else "warning"
    form_level = "error" if form_as_error else "warning"

    def report(level: str, kind: str, entity: str, field: str, expected: str, got: str, detail: str,
               line: int | None = None) -> None:
        signature = (kind, normalize_entity(entity, patterns) if entity else "", field, got or expected)
        if signature in seen:
            return
        seen.add(signature)
        findings.append(Finding(level, kind, entity, field, expected, got, detail, line))

    source_facts = [Fact(**f) for f in manifest["facts"]]
    source_entities = [Entity(**e) for e in manifest["entities"]]
    alias_map = {e.key: e.alias_of for e in source_entities if e.alias_of}
    source_entity_keys = {e.key: e for e in source_entities if not e.alias_of}
    for e in source_entities:
        source_entity_keys.setdefault(e.key, e)

    def resolve(key: str) -> str:
        return alias_map.get(key, key)

    bound: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))   # entity → field → values
    entity_values: dict[str, set[str]] = defaultdict(set)                            # entity → values
    value_entities: dict[str, set[str]] = defaultdict(set)                           # value → entities
    value_raw: dict[str, str] = {}
    numeric_by_entity: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for f in source_facts:
        bound[f.entity_key][f.field].add(f.value_key)
        entity_values[f.entity_key].add(f.value_key)
        value_entities[f.value_key].add(f.entity_key)
        value_raw.setdefault(f.value_key, f.value)
        if f.kind == "number" and parse_number(f.value) is not None:
            numeric_by_entity[f.entity_key].append((f.value, parse_number(f.value)))
    all_source_values = set(value_entities)
    plain_ints = {plain_integer_key(f.value) for f in source_facts if plain_integer_key(f.value)}

    cand_facts, cand_entities, cand_hits = facts_from_text(candidate, "<candidate>", patterns, known_ints=plain_ints)
    for f in cand_facts:
        f.entity_key = resolve(f.entity_key)
    cand_entity_keys = {resolve(e.key): e for e in cand_entities}
    cand_values = {f.value_key for f in cand_facts}
    cand_entity_values: dict[str, set[str]] = defaultdict(set)
    for f in cand_facts:
        cand_entity_values[f.entity_key].add(f.value_key)

    # 1. 候选稿中的每个值：绑定是否正确、是否被改动、是否凭空新增
    settled: set[tuple[str, str]] = set()
    for f in cand_facts:
        line = f.locus.get("line")
        entity_known = f.entity_key in source_entity_keys
        if f.entity_key and entity_known:
            if f.value_key in entity_values[f.entity_key]:
                continue
            if f.field and f.field in bound[f.entity_key] and bound[f.entity_key][f.field]:
                expected = sorted(bound[f.entity_key][f.field])
                settled.add((f.entity_key, f.field))
                if f.value_key in all_source_values:
                    owners = sorted(value_entities[f.value_key] - {f.entity_key})
                    owner_names = ", ".join(source_entity_keys[o].value if o in source_entity_keys else "（独立值）" for o in owners)
                    report("error", "数值绑定到错误实体", f.entity, f.field, value_raw[expected[0]], f.value,
                           f"{f.entity} 的 {f.field} 在来源为 {value_raw[expected[0]]!r}；{f.value!r} 在来源属于 {owner_names or '其他位置'}", line)
                else:
                    src_num = [(raw, num) for raw, num in numeric_by_entity[f.entity_key]]
                    cand_num = parse_number(f.value)
                    rounded = next((raw for raw, num in src_num if cand_num is not None and rounding_match(num, cand_num)), None)
                    if rounded:
                        report("error", "精度被改动", f.entity, f.field, rounded, f.value,
                               f"{f.entity} 的 {f.field} 来源为 {rounded!r}，输出被四舍五入或截断", line)
                    else:
                        report("error", "绑定值改变", f.entity, f.field, value_raw[expected[0]], f.value,
                               f"{f.entity} 的 {f.field} 在来源为 {value_raw[expected[0]]!r}", line)
                continue
            if f.value_key in all_source_values:
                owners = sorted(value_entities[f.value_key])
                owner_names = ", ".join(source_entity_keys[o].value if o in source_entity_keys else "（独立值）" for o in owners)
                report("error", "数值绑定到错误实体", f.entity, f.field, "", f.value,
                       f"{f.value!r} 在来源属于 {owner_names}，输出中跟随 {f.entity}", line)
                continue
            cand_num = parse_number(f.value)
            rounded = next((raw for raw, num in numeric_by_entity[f.entity_key] if cand_num is not None and rounding_match(num, cand_num)), None)
            if rounded:
                report("error", "精度被改动", f.entity, f.field, rounded, f.value, f"来源为 {rounded!r}", line)
                continue
            if f.value_key in allow_novel or f.value in allow_novel:
                continue
            report("error" if translate else "warning", "来源中不存在的数值", f.entity, f.field, "", f.value,
                   "该值在来源里找不到；翻译/转写任务中这是错误，分析任务需能指向产生它的文件并用 --allow-novel 登记", line)
            continue
        # 独立值或实体不在来源中
        if f.value_key in all_source_values:
            if f.entity_key and not entity_known:
                owners = sorted(value_entities[f.value_key])
                owner_names = ", ".join(source_entity_keys[o].value if o in source_entity_keys else "（独立值）" for o in owners)
                report("error", "数值绑定到错误实体", f.entity, f.field, "", f.value,
                       f"{f.value!r} 在来源属于 {owner_names}，输出中跟随来源里不存在的 {f.entity}", line)
            continue
        if f.value_key in allow_novel or f.value in allow_novel:
            continue
        cand_num = parse_number(f.value)
        rounded = next((raw for facts in numeric_by_entity.values() for raw, num in facts
                        if cand_num is not None and rounding_match(num, cand_num)), None)
        if rounded:
            report("error", "精度被改动", f.entity, f.field, rounded, f.value, f"来源为 {rounded!r}", line)
            continue
        report("error" if translate else "warning", "来源中不存在的数值", f.entity, f.field, "", f.value,
               "该值在来源里找不到；翻译/转写任务中这是错误，分析任务需能指向产生它的文件并用 --allow-novel 登记", line)

    # 2. 候选稿中的实体：凭空新增或形式改写
    normalized_source = {e.key: e for e in source_entities}
    for e in cand_entities:
        if e.key in alias_map and e.value == normalized_source[e.key].value:
            continue
        if e.key in normalized_source:
            original = normalized_source[e.key].value
            if e.value == original:
                continue
            category = category_by_id.get(e.category)
            if strip_version(e.value) == strip_version(original) and category and category.versioned:
                report("error", "版本号丢失或改动", e.value, "", original, e.value, f"来源为 {original!r}，版本号是编号的一部分", e.locus["line"])
            elif e.value.upper() == original.upper():
                report(form_level, "大小写被改动", e.value, "", original, e.value, f"来源为 {original!r}（物种命名规范依赖大小写）", e.locus["line"])
            elif e.category == "hgvs" and original.startswith("p."):
                report(form_level, "氨基酸记法被改写", e.value, "", original, e.value, f"来源为 {original!r}", e.locus["line"])
            elif any(g in original or g in e.value for g in patterns.greek_map if len(g) == 1):
                report(form_level, "希腊字母被改写", e.value, "", original, e.value, f"来源为 {original!r}", e.locus["line"])
            else:
                report(form_level, "符号或连接符被改动", e.value, "", original, e.value, f"来源为 {original!r}", e.locus["line"])
            continue
        if e.value in allow_novel:
            continue
        near = [s.value for s in source_entities if len(e.key) >= 6 and edit_distance_leq(e.key, s.key, 1)]
        if near:
            report("error", "疑似被改动的标识符", e.value, "", near[0], e.value, f"与来源 {near[0]!r} 仅差一个字符", e.locus["line"])
            continue
        category = category_by_id.get(e.category)
        if category and category.novel_check:
            report("error" if translate else "warning", "来源中不存在的标识符", e.value, "", "", e.value,
                   f"类别 {category.name_cn}；翻译/转写任务不得引入来源里没有的编号", e.locus["line"])
        elif translate and e.category in {"gene-symbol", "gene-symbol-mixed", "fusion-gene"}:
            report("warning", "来源中不存在的基因符号", e.value, "", "", e.value, "可能是译名或普通词，请核对", e.locus["line"])

    # 3. 来源 → 候选稿：数据是否消失
    for entity_key, values in entity_values.items():
        entity_present = (not entity_key) or entity_key in cand_entity_keys
        entity_name = source_entity_keys[entity_key].value if entity_key in source_entity_keys else "（独立值）"
        if entity_key and not entity_present:
            level = "error" if translate else ("error" if require_all else "info")
            report(level, "来源实体丢失", entity_name, "", entity_name, "",
                   f"{entity_name} 及其 {len(values)} 个绑定值未出现在候选稿中")
            continue
        for value_key in sorted(values):
            if value_key in cand_entity_values.get(entity_key, set()):
                continue
            fields_of_value = [fld for fld, vals in bound[entity_key].items() if value_key in vals]
            if any((entity_key, fld) in settled for fld in fields_of_value):
                continue
            if value_key in cand_values and not entity_key:
                continue
            fields = [fld for fld, vals in bound[entity_key].items() if value_key in vals]
            if value_key in cand_values:
                report("error", "绑定数据丢失", entity_name, fields[0] if fields else "", value_raw[value_key], "",
                       f"{entity_name} 的 {fields[0] if fields else '值'} {value_raw[value_key]!r} 在候选稿中出现但没有跟随该实体")
            else:
                report(missing_level, "来源数据丢失", entity_name, fields[0] if fields else "", value_raw[value_key], "",
                       f"{entity_name} 的 {fields[0] if fields else '值'} {value_raw[value_key]!r} 未出现在候选稿中")

    # 4. 覆盖底线：候选稿没有任何来源数据
    reused_values = cand_values & all_source_values
    reused_entities = set(cand_entity_keys) & set(source_entity_keys)
    if (all_source_values or source_entity_keys) and not reused_values and not reused_entities:
        report("error", "候选稿未包含任何来源数据", "", "", "", "",
               f"来源有 {len(all_source_values)} 个值、{len(source_entity_keys)} 个实体，候选稿一个都没有复用")
    return findings


def verify_table(source_path: Path, output_path: Path, key_column: str | None) -> list[Finding]:
    findings: list[Finding] = []
    source = read_table(source_path, read_text(source_path))
    target = read_table(output_path, read_text(output_path))
    if source is None or target is None:
        findings.append(Finding("error", "表格无法解析", output_path.name, "", "", "", "源表或输出表不是可解析的 CSV/TSV"))
        return findings
    s_header, s_rows = source
    t_header, t_rows = target
    if s_header != t_header:
        missing = [c for c in s_header if c not in t_header]
        added = [c for c in t_header if c not in s_header]
        detail = "；".join(filter(None, [f"缺少列 {missing}" if missing else "", f"新增列 {added}" if added else "",
                                        "列顺序被改变" if not missing and not added else ""]))
        findings.append(Finding("error", "表头改变", output_path.name, "", str(s_header), str(t_header), detail))
    if len(s_rows) != len(t_rows):
        findings.append(Finding("error", "行数改变", output_path.name, "", str(len(s_rows)), str(len(t_rows)), f"源 {len(s_rows)} 行，输出 {len(t_rows)} 行"))
    common = [c for c in s_header if c in t_header]
    s_index = {c: s_header.index(c) for c in common}
    t_index = {c: t_header.index(c) for c in common}
    key = key_column or (s_header[0] if s_header else None)
    if key and key in s_index and key in t_index:
        s_by_key = {row[s_index[key]]: row for row in s_rows if s_index[key] < len(row)}
        t_by_key = {row[t_index[key]]: row for row in t_rows if t_index[key] < len(row)}
        if len(s_by_key) != len(s_rows):
            findings.append(Finding("info", "键列不唯一", key, "", "", "", "按行序而不是键对比"))
            pairs = list(zip(s_rows, t_rows))
        else:
            lost = [k for k in s_by_key if k not in t_by_key]
            extra = [k for k in t_by_key if k not in s_by_key]
            if lost:
                findings.append(Finding("error", "记录丢失", key, "", str(lost[:5]), "", f"{len(lost)} 条"))
            if extra:
                findings.append(Finding("error", "凭空新增记录", key, "", "", str(extra[:5]), f"{len(extra)} 条"))
            order_source = [k for k in s_by_key if k in t_by_key]
            order_target = [k for k in t_by_key if k in s_by_key]
            if order_source != order_target:
                findings.append(Finding("warning", "行顺序改变", key, "", "", "", "共有记录的顺序与源表不同"))
            pairs = [(s_by_key[k], t_by_key[k]) for k in order_source]
    else:
        pairs = list(zip(s_rows, t_rows))
    changed: Counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    filled_na: Counter = Counter()
    for s_row, t_row in pairs:
        for column in common:
            s_val = s_row[s_index[column]] if s_index[column] < len(s_row) else ""
            t_val = t_row[t_index[column]] if t_index[column] < len(t_row) else ""
            if s_val == t_val:
                continue
            if s_val.strip().upper() in {"", "NA", "NAN", "NULL", "NONE", "."} and t_val.strip():
                filled_na[column] += 1
            changed[column] += 1
            if len(examples[column]) < 3:
                examples[column].append(f"{s_val!r}→{t_val!r}")
    for column, count in changed.items():
        findings.append(Finding("error", "单元格被改动", column, column, "", "", f"{count} 处，例如 {'; '.join(examples[column])}"))
    for column, count in filled_na.items():
        findings.append(Finding("error", "缺失值被填补", column, column, "NA", "", f"{count} 处原本为空或 NA"))
    if not findings:
        findings.append(Finding("info", "表格逐格一致", output_path.name, "", "", "", f"{len(pairs)} 行 × {len(common)} 列完全相同"))
    return findings


def cmd_verify(args: argparse.Namespace) -> int:
    patterns = load_patterns(Path(args.patterns))
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    if manifest.get("schema") != "fidelity-manifest/2":
        print("清单不是 fidelity-manifest/2，请用当前版本的 extract 重新生成", file=sys.stderr)
        return 2
    if args.mode == "translate" and args.allow_novel:
        print("翻译/转写模式不允许 --allow-novel：译文不得引入来源里没有的数据", file=sys.stderr)
        return 2
    allow_novel: set[str] = set()
    if args.allow_novel:
        allow_path = Path(args.allow_novel)
        raw_items = read_text(allow_path).splitlines() if allow_path.is_file() else args.allow_novel.split(",")
        for item in raw_items:
            item = item.strip()
            if item:
                allow_novel.add(item)
                key = number_key(item)
                if key:
                    allow_novel.add(key)
    all_findings: dict[str, list[Finding]] = {}
    for raw in args.outputs:
        path = Path(raw)
        if not path.is_file():
            print(f"输出文件不存在：{path}", file=sys.stderr)
            return 2
        all_findings[str(path)] = verify_text(read_text(path), manifest, patterns, args.mode, allow_novel,
                                              args.require_all, args.form_as_error)
    if args.table_source:
        if len(args.outputs) != 1:
            print("--table-source 只能与单个输出表一起使用", file=sys.stderr)
            return 2
        all_findings[str(Path(args.outputs[0]))].extend(verify_table(Path(args.table_source), Path(args.outputs[0]), args.key_column))

    errors = sum(1 for fs in all_findings.values() for f in fs if f.level == "error")
    warnings = sum(1 for fs in all_findings.values() for f in fs if f.level == "warning")
    unverifiable = manifest.get("unverifiable", [])
    status = "fail" if errors else ("unverifiable" if unverifiable else "pass")
    summary = {
        "schema": "fidelity-verify/2", "mode": args.mode, "status": status,
        "manifest": Path(args.manifest).name, "sources": manifest.get("sources", []),
        "outputs": [{"file": p, "sha256": sha256_of(Path(p))} for p in all_findings],
        "unverifiable": unverifiable, "errors": errors, "warnings": warnings,
        "findings": {path: [asdict(f) for f in fs] for path, fs in all_findings.items()},
    }
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"模式 {args.mode}；校验 {len(all_findings)} 个输出；来源实体 {len({e['key'] for e in manifest['entities']})} 个、值 {len(manifest['facts'])} 个。")
    for path, findings in all_findings.items():
        shown = [f for f in findings if f.level != "info" or args.verbose]
        if not shown:
            print(f"  {path}: 未发现问题")
            continue
        print(f"  {path}:")
        for f in sorted(shown, key=lambda f: ({"error": 0, "warning": 1, "info": 2}[f.level], f.line or 0)):
            where = f" 第 {f.line} 行" if f.line else ""
            head = f"{f.entity}.{f.field}" if f.entity and f.field else (f.entity or "")
            subject = f"{head} = {f.got}" if f.field and f.got else (head or f.got or f.expected)
            print(f"    [{f.level}] {f.kind}{where}：{subject} — {f.detail}")
    if unverifiable:
        print("不可校验范围（交付时必须明示，不得声称全部通过）：")
        for item in unverifiable:
            print(f"  - {item}")
    if errors:
        print(f"结论：未通过，{errors} 个错误、{warnings} 个警告。修正后重新校验，不得跳过。")
        return 1
    if unverifiable:
        print(f"结论：已校验范围内无错误（{warnings} 个警告），但存在不可校验范围。")
        return 3
    if warnings:
        print(f"结论：通过但有 {warnings} 个警告，需逐条确认并在交付说明中解释。")
        return 0
    print("结论：通过。")
    return 0


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--patterns", default=str(DEFAULT_PATTERNS), help="不变量模式文件，默认使用 references/不变量模式.json")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("extract", help="从来源提取绑定事实清单")
    p.add_argument("inputs", nargs="*", help="来源文件：文本、Markdown、CSV/TSV、JSON，或 PDF/DOCX 的文本投影")
    p.add_argument("--text", help="直接给出的文本（例如用户消息中的内容）")
    p.add_argument("--output", required=True, help="manifest.json 输出路径")
    p.add_argument("--projection-of", help="输入是某个二进制文件的文本投影时，记录原文件名")
    p.add_argument("--unverifiable", action="append", help="登记无法投影或无法核对的范围，可重复，例如“第3页表2无法读取”")
    p.add_argument("--basename-only", action="store_true", help="清单中只记录文件名，不记录路径")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("protect", help="用保护标记替换文本中的不变量")
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True, help="受保护文本")
    p.add_argument("--mapping", required=True, help="保护标记映射 JSON")
    p.add_argument("--skip-kinds", help="不保护的类别，逗号分隔，例如 path,reference")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_protect)

    p = sub.add_parser("restore", help="把保护标记回填为原文并核对数量、顺序与绑定")
    p.add_argument("--input", required=True, help="翻译或改写后的受保护文本")
    p.add_argument("--mapping", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_restore)

    p = sub.add_parser("render", help="用源文件原样填充 Markdown 模板插槽")
    p.add_argument("--template", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--base", help="插槽中相对路径的基准目录，默认模板所在目录")
    p.add_argument("--overwrite", action="store_true")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("verify", help="按绑定关系对比清单与候选稿")
    p.add_argument("outputs", nargs="+", help="候选稿文件（最终产物重新读取后的文本），任意文本格式")
    p.add_argument("--manifest", required=True)
    p.add_argument("--mode", choices=["translate", "analysis"], default="translate",
                   help="translate：翻译/转写/改写，来源数据必须全部保留且不得新增；analysis：允许登记过的新结果")
    p.add_argument("--report", help="校验结果 JSON 输出路径")
    p.add_argument("--allow-novel", help="analysis 模式下允许出现的新值：逗号分隔，或每行一个值的文件")
    p.add_argument("--require-all", action="store_true", help="analysis 模式下来源数据缺失也按错误处理")
    p.add_argument("--form-as-error", action="store_true", help="把大小写、连接符、希腊字母、氨基酸记法差异升级为错误")
    p.add_argument("--table-source", help="输出为表格时，与之逐格对比的源表")
    p.add_argument("--key-column", help="表格对比使用的键列，默认第一列")
    p.add_argument("--verbose", action="store_true", help="同时显示 info 级别条目")
    p.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not Path(args.patterns).is_file():
        print(f"模式文件不存在：{args.patterns}", file=sys.stderr)
        return 2
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

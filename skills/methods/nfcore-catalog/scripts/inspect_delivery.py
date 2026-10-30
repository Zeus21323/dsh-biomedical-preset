#!/usr/bin/env python3
"""只读抽查科研交付目录：识别文件格式，保留实验类型与研究设计的未知状态。"""
from __future__ import annotations

import argparse
from collections import Counter
from itertools import islice
import json
import os
from pathlib import Path
import re
import stat
import sys
import zlib


HEADER_BYTES = 65536
MAX_ENTRIES = 4000
MAX_DEPTH = 6


def detect_format(raw: bytes) -> tuple[str, str]:
    """A recognizable prefix is evidence of format, not a whole-file validation."""
    signatures = [
        (b'BAM\x01', 'BAM'), (b'CRAM', 'CRAM'), (b'BCF\x02', 'BCF'),
        (b'II*\x00', 'TIFF'), (b'MM\x00*', 'TIFF'),
        (b'II+\x00', 'BigTIFF'), (b'MM\x00+', 'BigTIFF'),
        (b'IDAT', 'IDAT'), (b'%PDF-', 'PDF'),
        (b'PK\x03\x04', 'ZIP-container'),
    ]
    for signature, label in signatures:
        if raw.startswith(signature):
            return label, '文件签名'
    if raw[128:132] == b'DICM':
        return 'DICOM', '含标准前导的文件签名'
    if raw[344:348] in {b'n+1\x00', b'ni1\x00'} or raw[4:8] in {b'n+2\x00', b'ni2\x00'}:
        return 'NIfTI', '文件头魔数'
    if any(raw[offset:offset + 8] == b'\x89HDF\r\n\x1a\n' for offset in [0, 512, 1024, 2048, 4096, 8192, 16384, 32768]):
        return 'HDF5-container', '容器签名；未检查内部数据结构'
    if raw[257:262] == b'ustar':
        return 'TAR-container', '归档头；未解包'
    if not raw:
        return 'unknown', '空文件或没有可读取的前缀'
    text = raw.decode('utf-8-sig', errors='replace')
    lines = text.splitlines()
    if text.startswith('%%MatrixMarket matrix'):
        return 'MatrixMarket', '矩阵格式声明；未校验维度与全部记录'
    if text.startswith('##fileformat=VCF'):
        return 'VCF', 'VCF 头声明'
    if re.match(r'@(HD|SQ|RG|PG|CO)\t', text):
        return 'SAM', 'SAM 头记录'
    if len(lines) >= 4 and lines[0].startswith('@') and lines[2].startswith('+'):
        seq, qual = lines[1], lines[3]
        if seq and len(seq) == len(qual) and re.fullmatch('[A-Za-z.*=-]+', seq) and all(33 <= ord(c) <= 126 for c in qual):
            return 'FASTQ', '抽查首条四行记录；未确认实验类型、配对或全部记录'
    if len(lines) >= 2 and lines[0].startswith('>') and re.fullmatch('[A-Za-z.*=-]+', lines[1]):
        return 'FASTA', '序列文本前缀；未判定 DNA 或蛋白'
    for tag, label in [('mzML', 'mzML'), ('indexedmzML', 'mzML'), ('mzXML', 'mzXML'), ('Header', 'RCC-candidate')]:
        if re.search(r'<(?:\w+:)?' + tag + r'(?:\s|>)', text):
            # Header alone is not sufficiently specific for RCC.
            if label == 'RCC-candidate' and '<Sample_Attributes>' not in text:
                continue
            return label, '有限文本中的 XML 标签；还需核验结构'
    if re.search(r'<!doctype\s+html|<html(?:\s|>)', text, re.I):
        return 'HTML', '报告容器；未运行脚本或读取其结论'
    if '\x00' not in text and '\ufffd' not in text:
        if lines and ('\t' in lines[0] or ',' in lines[0]):
            return 'delimited-text-candidate', '分隔符线索；未判定数值、单位或研究设计'
        return 'text', '可解码文本；内容尚待按任务检查'
    return 'unknown', '有限前缀无法识别；应使用对应格式工具继续检查'


def inspect_file(path: Path, relative: str) -> dict:
    result = {'path': relative}
    try:
        mode = path.lstat().st_mode
        if not stat.S_ISREG(mode):
            return {**result, 'status': 'skipped', 'reason': '不读取符号链接或特殊文件'}
        # O_NOFOLLOW also avoids following a symlink substituted after lstat.
        descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        with os.fdopen(descriptor, 'rb') as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                return {**result, 'status': 'skipped', 'reason': '对象已变为特殊文件'}
            raw = handle.read(HEADER_BYTES)
        result.update(bytes=info.st_size, suffix_hint=''.join(path.suffixes[-2:]))
        if raw.startswith(b'\x1f\x8b'):
            result['compression'] = 'gzip-prefix-only'
            raw = zlib.decompressobj(31).decompress(raw, HEADER_BYTES)
        label, evidence = detect_format(raw)
        result.update(status='observed', file_format=label, evidence=evidence)
    except (OSError, ValueError, zlib.error) as exc:
        result.update(status='error', reason=type(exc).__name__, action='检查文件完整性与读取权限；未判定数据类型')
    return result


def scan_delivery(root: Path, max_files: int = 200) -> dict:
    if not 1 <= max_files <= 2000:
        raise ValueError('max-files 必须在 1 到 2000 之间')
    root = root.absolute()
    if root.is_symlink():
        raise ValueError('请提供实际交付路径，不遍历符号链接')
    mode = root.stat().st_mode
    observations = []
    issues = []
    truncated = False
    if stat.S_ISREG(mode):
        observations.append(inspect_file(root, root.name))
    elif stat.S_ISDIR(mode):
        pending = [(root, 0)]
        visited = 0
        while pending and len(observations) < max_files and visited < MAX_ENTRIES:
            directory, depth = pending.pop()
            try:
                with os.scandir(directory) as iterator:
                    remaining = MAX_ENTRIES - visited
                    children = list(islice(iterator, remaining + 1))
                if len(children) > remaining:
                    truncated = True
                    children = children[:remaining]
                visited += len(children)
                for entry in sorted(children, key=lambda item: item.name):
                    path = Path(entry.path)
                    relative = path.relative_to(root).as_posix()
                    if entry.is_symlink():
                        issues.append({'path': relative, 'reason': '跳过符号链接'})
                    elif entry.is_dir(follow_symlinks=False):
                        if depth < MAX_DEPTH:
                            pending.append((path, depth + 1))
                        else:
                            truncated = True
                            issues.append({'path': relative, 'reason': '达到目录深度上限'})
                    elif entry.is_file(follow_symlinks=False):
                        if len(observations) == max_files:
                            truncated = True
                        else:
                            observations.append(inspect_file(path, relative))
                    else:
                        issues.append({'path': relative, 'reason': '跳过特殊文件'})
            except OSError as exc:
                issues.append({'path': directory.relative_to(root).as_posix(), 'reason': type(exc).__name__})
        truncated = truncated or bool(pending)
    else:
        raise ValueError('只接受普通文件或目录')
    observations.sort(key=lambda item: item['path'])
    counts = Counter(item['file_format'] for item in observations if item['status'] == 'observed')
    hints = []
    by_parent = {}
    for item in observations:
        path = Path(item['path'])
        by_parent.setdefault(path.parent, set()).add(path.name.removesuffix('.gz'))
    for parent, names in sorted(by_parent.items()):
        if 'matrix.mtx' in names and 'barcodes.tsv' in names and names.intersection({'genes.tsv', 'features.tsv'}):
            hints.append({'path': parent.as_posix(), 'hint': '矩阵与条码/特征文件共存；核实单细胞或空间来源及矩阵内容，不证明特定平台'})
    return {
        'schema_version': 1, 'files_inspected': len(observations), 'truncated': truncated,
        'format_counts': dict(counts), 'files': observations, 'layout_hints': hints, 'issues': issues,
        'assay': None, 'organism': None, 'sample_relationships': None,
        'research_question': None, 'recommended_pipeline': None, 'analysis_ready': False,
        'next_action': '结合交付报告、实验说明与实际格式元数据核实实验及处理阶段，再匹配研究问题；不能从文件格式直接选流程',
        'limits': '最多读取每个文件的有限前缀；不检查全部记录、配对、压缩完整性或研究设计，不输出数据行，不运行分析',
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--path', type=Path, required=True)
    parser.add_argument('--max-files', type=int, default=200)
    args = parser.parse_args(argv)
    try:
        result = scan_delivery(args.path, args.max_files)
    except (OSError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""离线搜索或精确定位本包记录的 nf-core Skill，不安装或执行分析。"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

CATALOG = Path(__file__).resolve().parents[1] / 'references' / '流程目录.json'


def load_catalog(path: Path = CATALOG) -> dict:
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or not isinstance(data.get('pipelines'), list):
        raise ValueError('无法识别的目录格式')
    if data.get('pipeline_count') != len(data['pipelines']):
        raise ValueError('目录计数不一致')
    return data


def normalized_name(value: str) -> str:
    value = value.strip().casefold().removeprefix('$')
    for prefix in ['nf-core/', 'nf-core-', 'nfcore-']:
        if value.startswith(prefix):
            return value.removeprefix(prefix)
    return value


def resolve(entries: list[dict], name: str) -> dict:
    name = normalized_name(name)
    matches = [entry for entry in entries if normalized_name(entry['pipeline_id']) == name]
    if len(matches) != 1:
        raise ValueError('没有唯一匹配的流程；使用 search 查找，不自动替换名称或版本')
    return matches[0]


def search(entries: list[dict], query: str = '', domain: str = '', active_only: bool = False) -> list[dict]:
    query = query.strip().casefold()
    tokens = [token for token in re.split(r'\s+', query) if token]
    results = []
    for entry in entries:
        if active_only and entry['archived']:
            continue
        if domain and domain.casefold() not in entry['domain'].casefold():
            continue
        haystack = ' '.join(str(entry.get(key, '')) for key in [
            'pipeline_id', 'skill_id', 'display_name', 'scientific_title',
            'domain', 'description', 'secondary_search_terms'
        ]).casefold()
        exact = normalized_name(query) == normalized_name(entry['pipeline_id']) if query else False
        if exact or all(token in haystack for token in tokens):
            results.append((not exact, entry))
    results.sort(key=lambda pair: (pair[0], pair[1]['domain'], pair[1]['pipeline_id']))
    return [entry for _, entry in results]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    search_parser = commands.add_parser('search', help='按名称、领域和任务词搜索；默认保留归档条目')
    search_parser.add_argument('query', nargs='?', default='')
    search_parser.add_argument('--domain', default='')
    search_parser.add_argument('--active-only', action='store_true', help='仅排除归档项，不表示已正式发布或可运行')
    search_parser.add_argument('--limit', type=int, default=10)
    show_parser = commands.add_parser('show', help='按官方名或稳定 Skill ID 精确定位')
    show_parser.add_argument('name')
    args = parser.parse_args(argv)
    try:
        entries = load_catalog()['pipelines']
        if args.command == 'show':
            result = resolve(entries, args.name)
        else:
            if args.limit < 1:
                raise ValueError('limit 必须大于零')
            found = search(entries, args.query, args.domain, args.active_only)
            result = {'total_matches': len(found), 'returned': min(len(found), args.limit),
                      'pipelines': found[:args.limit]}
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())

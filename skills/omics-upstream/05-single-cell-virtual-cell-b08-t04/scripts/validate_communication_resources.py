#!/usr/bin/env python3
"""验证固定版本通讯资源的文件完整性和声明结构；原生适配器另验算法语义。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import csv
import json
import re
import sqlite3
import zipfile
from pathlib import Path
from urllib.parse import urlparse
from communication_contract import digest, local_path, registry, write_json


def validate_request(config):
    resources={r['name']:r for r in registry()['resources']}
    if config.get('schema_version')!=1 or config.get('resource') not in resources:
        raise ValueError('需要已登记的九类资源之一及schema_version=1')
    for key in ('version','species','identifier_system','interaction_types','license','source_provenance','complex_semantics'):
        if not config.get(key):raise ValueError(f'资源缺少{key}，不可用默认值猜测')
    if not isinstance(config['species'],list) or not all(isinstance(s,str) and s.strip() for s in config['species']):
        raise ValueError('species须为明确物种列表')
    files=config.get('files')
    if not isinstance(files,list) or not files:raise ValueError('资源没有固定文件清单')
    names=set()
    for item in files:
        name=item.get('name','')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*',name) or name in names:
            raise ValueError('资源文件名需唯一安全basename')
        names.add(name)
        if not re.fullmatch('[a-f0-9]{64}',item.get('sha256','')):raise ValueError('每个下载需先固定完整sha256')
        parsed=urlparse(item.get('url',''))
        if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError('资源下载只接受无内嵌凭据的HTTPS地址')
        if item.get('format') not in ('tsv','csv','json','zip','sqlite','rds','rdata','binary'):
            raise ValueError('必须明确资源文件格式')
        if item['format'] in ('csv','tsv') and not item.get('required_columns'):
            raise ValueError('表格资源需要原生必需列；不按扩展名猜结构')
    return resources[config['resource']]


def inspect_file(path, item):
    if digest(path)!=item['sha256']:raise ValueError(f'资源摘要不符: {path.name}')
    if path.stat().st_size==0:raise ValueError('资源是空文件')
    result=dict(name=path.name,sha256=item['sha256'],bytes=path.stat().st_size,format=item['format'])
    if item['format'] in ('tsv','csv'):
        with path.open(encoding=item.get('encoding','utf-8-sig'),newline='') as stream:
            reader=csv.DictReader(stream,delimiter='\t' if item['format']=='tsv' else ',')
            if len(reader.fieldnames or [])<2 or not set(item['required_columns'])<=set(reader.fieldnames or []):raise ValueError('资源表头变化或缺列；不能把HTTP200错误文本当资源表')
            count=0
            for row in reader:
                if None in row or any(v is None for v in row.values()):raise ValueError('资源行列数不一致')
                count+=1
        if count==0:raise ValueError('资源表没有数据行')
        result.update(rows=count,columns=reader.fieldnames,validation='native_table_structure')
    elif item['format']=='json':
        value=json.loads(path.read_text())
        if not isinstance(value,(dict,list)) or not value:raise ValueError('JSON资源不是非空对象/数组')
        result['validation']='json_structure'
    elif item['format']=='zip':
        with zipfile.ZipFile(path) as archive:
            members=archive.namelist()
            if not members or len(set(members))!=len(members):raise ValueError('ZIP为空或含重复成员')
            for n in members:
                p=Path(n)
                if p.is_absolute() or '..' in p.parts or '\\' in n:raise ValueError('ZIP成员路径不安全')
            if not set(item.get('required_members',[]))<=set(members):raise ValueError('ZIP缺少声明的原生资源文件')
            # No extraction. Hash identifies the exact compressed artifact;
            # native readers perform semantic checks before inference.
            result.update(members=members,validation='zip_directory_and_archive_hash')
    elif item['format']=='sqlite':
        with sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True) as db:
            check=db.execute('PRAGMA quick_check').fetchone()[0]
            tables=[r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        if check!='ok' or not tables or not set(item.get('required_tables',[]))<=set(tables):raise ValueError('SQLite资源结构无效')
        result.update(tables=tables,validation='sqlite_integrity_and_tables')
    else:
        result['validation']='hash_only_native_reader_required'
    return result


def validate_manifest(path):
    path=Path(path).resolve();config=json.loads(path.read_text());catalog=validate_request(config)
    checks=[inspect_file(local_path(path.parent,i['name']),i) for i in config['files']]
    return dict(schema_version=1,resource=config['resource'],version=config['version'],manifest_sha256=digest(path),catalog_source=catalog['source'],files=checks,
                status='artifact_integrity_verified',semantic_validation='由对应固定版本原生适配器核验物种、分子身份、复合物成员和映射损失；文件校验不等于生物学资源适用性通过')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--manifest',required=True);args=p.parse_args()
    print(json.dumps(validate_manifest(args.manifest),ensure_ascii=False,indent=2))

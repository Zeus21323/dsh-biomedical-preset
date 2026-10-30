#!/usr/bin/env python3
"""按已核实清单下载通讯资源至Git外，固定摘要，拒绝覆盖，不猜测最新数据库。"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
from urllib.request import Request,urlopen
from communication_contract import new_output,write_json
from validate_communication_resources import validate_request,validate_manifest


def fetch(config_path,output):
    config=json.loads(Path(config_path).read_text());validate_request(config)
    out=new_output(output);write_json(out/'resource_manifest.json',config)
    state=dict(status='running',started_at=datetime.now(timezone.utc).isoformat(),files=[])
    try:
        for item in config['files']:
            partial=out/(item['name']+'.partial');limit=item.get('max_bytes',4*1024**3)
            if type(limit) is not int or limit<=0:raise ValueError('max_bytes必须为正整数')
            with urlopen(Request(item['url'],headers={'User-Agent':'Biomed-communication-resource/1'}),timeout=60) as response:
                if not response.url.startswith('https://'):raise ValueError('下载重定向降级到非HTTPS')
                size=0
                with partial.open('xb') as stream:
                    while block:=response.read(1024*1024):
                        size+=len(block)
                        if size>limit:raise ValueError('资源超过声明大小上限')
                        stream.write(block)
                state['files'].append(dict(name=item['name'],resolved_url=response.url,bytes=size))
            from communication_contract import digest
            if digest(partial)!=item['sha256']:raise ValueError(f"{item['name']}摘要与固定版本不符；保留partial供排查，不作为可用资源")
            partial.rename(out/item['name'])
        report=validate_manifest(out/'resource_manifest.json');write_json(out/'resource_validation.json',report)
        state['status']='artifact_integrity_verified'
    except Exception as error:
        state.update(status='failed',error=str(error));raise
    finally:
        state['finished_at']=datetime.now(timezone.utc).isoformat();write_json(out/'download_state.json',state)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',required=True);p.add_argument('--out',required=True);a=p.parse_args();fetch(a.config,a.out)

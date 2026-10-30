#!/usr/bin/env python3
"""校验证据长表并生成本地HTML；不计算因果分数或自动作结论。"""
import argparse
import csv
import html
from pathlib import Path
import sys

FIELDS=["target","question","outcome","tissue","exposure","unit","evidence_type","result","direction","direction_target","source","source_group","limitation"]

def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--input",type=Path,required=True);a.add_argument("--out",type=Path,required=True)
    x=a.parse_args()
    with x.input.open(encoding="utf-8-sig",newline="") as f:
        r=csv.DictReader(f,delimiter="\t")
        if not set(FIELDS)<=set(r.fieldnames or []): raise ValueError("证据表缺字段")
        fields=list(r.fieldnames)
        if len(fields)!=len(set(fields)) or any(not k.strip() for k in fields): raise ValueError("表头空或重复")
        rows=list(r)
    if not rows: raise ValueError("证据表为空")
    for row in rows:
        if None in row or any(v is None for v in row.values()): raise ValueError("证据表列数不一致")
        if any(not (row.get(k) or "").strip() for k in FIELDS): raise ValueError("证据字段不得为空")
        if row["result"] not in ("support","conflict","inconclusive","not_available"): raise ValueError("非法result")
        if row["direction"] not in ("increase","decrease","unclear","not_applicable"): raise ValueError("非法direction")
    out=x.out.resolve()
    if out.exists(): raise ValueError("输出已存在")
    for parent in Path(__file__).resolve().parents:
        if (parent/".git").exists() or (parent/".speedskills").exists():
            if out==parent or parent in out.parents: raise ValueError("结果不能写入仓库")
            break
    out.mkdir(parents=True,exist_ok=False)
    with (out/"evidence.tsv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields,delimiter="\t");w.writeheader();w.writerows(rows)
    header="<tr>"+"".join("<th>"+html.escape(k)+"</th>" for k in fields)+"</tr>"
    body="".join("<tr>"+"".join("<td>"+html.escape(row[k])+"</td>" for k in fields)+"</tr>" for row in rows)
    document='<!doctype html><html lang="zh"><meta charset="utf-8"><title>靶点证据</title><style>body{font:16px sans-serif;margin:2rem;color:#222}table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:.5rem;text-align:left;overflow-wrap:anywhere}th{background:#eef3f7}</style><h1>靶点证据矩阵</h1><p>仅整理输入证据；支持、冲突、不足、缺失分别保留。不自动评分，不代表因果验证。</p><table>'+header+body+"</table></html>"
    (out/"report.html").write_text(document,encoding="utf-8")
    print("已保存证据与本地HTML；请按操作指南制作真实数值图并撰写解读")

if __name__=="__main__":
    try: main()
    except (OSError,ValueError,KeyError) as e: print("错误："+str(e),file=sys.stderr);sys.exit(2)

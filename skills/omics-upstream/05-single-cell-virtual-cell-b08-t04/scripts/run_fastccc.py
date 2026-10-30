#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["fastccc==1.0.1", "numpy==2.3.5", "matplotlib==3.11.1", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""Native FastCCC analytical null distribution per biological sample."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from communication_contract import new_output,write_json,add_table,digest,truth
from communication_inputs import read_expression,require_version
from communication_identities import SCHEMA,cpdb_entities,directed_fields


def run(config,output):
    import pandas as pd
    from fastccc.core import statistical_analysis_method
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    version=require_version("fastccc","1.0.1")
    data,keys,provenance=read_expression(cfg,config.parent)
    if cfg["expression_scale"]!="log_normalized":raise ValueError("FastCCC 适配器需要明确 log_normalized 输入")
    db=(config.parent/cfg["database"]).resolve()
    required=("interaction_table.csv","multidata_table.csv","gene_table.csv","protein_table.csv","complex_composition_table.csv","complex_table.csv")
    if not cfg.get("database_version") or any(not (db/p).is_file() for p in required):raise ValueError("需原生 CellPhoneDB 展开表目录及数据库版本")
    out=new_output(output);write_json(out/"run_config.json",cfg)
    identities=cpdb_entities(db)
    rows=[];ambiguous=set();roundoff=0
    for si,sample in enumerate(sorted(data.obs[keys["sample"]].unique())):
        subset=data[data.obs[keys["sample"]]==sample].copy();meta=subset.obs.iloc[0]
        sizes=subset.obs[keys["cell_type"]].value_counts();subset=subset[subset.obs[keys["cell_type"]].isin(sizes[sizes>=cfg.get("min_cells",10)].index)].copy()
        if subset.obs[keys["cell_type"]].nunique()<2:raise ValueError("低细胞数过滤后不足两个细胞群")
        if subset.obs[keys["cell_type"]].str.contains("|",regex=False).any():raise ValueError("标签含分隔符 |")
        folder=out/f"native_{si+1:03d}";folder.mkdir()
        scores,pvalues,eligible=statistical_analysis_method(database_file_path=str(db),celltype_file_path=None,
            counts_file_path=subset,meta_key=keys["cell_type"],convert_type=cfg.get("counts_data","hgnc_symbol"),
            single_unit_summary=cfg.get("single_unit_summary","Mean"),complex_aggregation="Minimum",
            LR_combination=cfg.get("LR_combination","Arithmetic"),min_percentile=cfg.get("expression_fraction",.1),save_path=str(folder))
        for name,frame in (("scores",scores),("pvalues",pvalues),("eligibility",eligible)):
            frame.to_csv(folder/(name+".tsv"),sep="\t")
        for interaction in scores.columns:
            identity=identities[interaction];fields=directed_fields(identity);ra=identity['a']['receptor']
            if fields is None:ambiguous.add(str(interaction));continue
            for pair in scores.index:
                source,target=pair.split("|");test=bool(eligible.loc[pair,interaction]);score=float(scores.loc[pair,interaction]);p=float(pvalues.loc[pair,interaction])
                if not -1e-12 <= p <= 1+1e-12:raise ValueError("原生解析 P 超出浮点舍入容差，停止统计解释")
                if p<0 or p>1:
                    roundoff+=1;p=min(1.,max(0.,p))
                rows.append(dict(sample=str(sample),donor=str(meta[keys["donor"]]),condition=str(meta[keys["condition"]]),
                    source=target if ra else source,target=source if ra else target,**fields,interaction=str(interaction),score=score if test else None,
                    p_value=p if test else None,tested=test,supported=test and score>0 and p<cfg.get("alpha",.05)))
    provenance.update(database_version=cfg["database_version"],database_files={p:digest(db/p) for p in required},
        database_sha256={p:digest(db/p) for p in required},molecule_identity_schema=SCHEMA,
        parameters=cfg,ambiguous_direction=sorted(ambiguous),test_unit="within_sample_expression_null_distribution",
        probability_roundoff=dict(tolerance=1e-12,clipped=roundoff,original_values="native directories/pvalues.tsv"))
    bundle=dict(schema_version=2,dataset=cfg["dataset"],method="FastCCC",method_version=version,implementation="native",provenance=provenance,tables=[],top_lr=cfg.get("top_lr",24))
    add_table(bundle,out,"lr_edges","lr_edges",rows,"FastCCC 原生解析分布检验与相互作用强度；非供体条件差异 P。方向不唯一者保留原生表，不放入有向图。",
              value_kind="native_score",axis_label="FastCCC strength",direction="higher",additive=False)
    write_json(out/"bundle.json",bundle)
    from render_result_bundle import run as render
    return render(out/"bundle.json",out/"figures")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))

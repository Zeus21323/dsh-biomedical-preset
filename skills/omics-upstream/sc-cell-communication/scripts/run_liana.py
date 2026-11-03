#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["liana==1.10.0", "numpy==2.2.6", "matplotlib==3.10.6", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""Run LIANA+ rank aggregation or explicit framework scores per biological sample."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from communication_contract import new_output, write_json, add_table, digest
from communication_inputs import require_version, read_expression
from communication_identities import SCHEMA,gene_identity


def run(config, output):
    import liana as li
    import pandas as pd
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    version=require_version("liana", "1.10.0")
    data,keys,provenance=read_expression(cfg,config.parent)
    if cfg["expression_scale"]!="log_normalized":raise ValueError("此 LIANA 适配器需要明确 log_normalized 输入")
    member=cfg.get("member","rank_aggregate")
    methods={"rank_aggregate":("magnitude_rank","specificity_rank", "lower"),
             "cellphonedb":("lr_means","cellphone_pvals","higher"),
             "natmi":("expr_prod","spec_weight","higher"),
             "connectome":("expr_prod","scaled_weight","higher"),
             "singlecellsignalr":("lrscore",None,"higher"),
             "cellchat":("lr_probs","cellchat_pvals","higher"),
             "geometric_mean":("lr_gmeans","gmean_pvals","higher")}
    if member not in methods:raise ValueError("未核验的 LIANA member，不得冒充原生全功能实现")
    if cfg.get("species")!="human" and not cfg.get("resource_file"):
        raise ValueError("非人类需提供已核验物种的 LR resource_file，不自动大小写转换")
    out=new_output(output)
    write_json(out/"run_config.json",cfg)
    resource=pd.read_csv(config.parent/cfg["resource_file"],sep="\t") if cfg.get("resource_file") else li.rs.select_resource(cfg.get("resource_name","consensus"))
    if not {"ligand","receptor"}<=set(resource.columns):raise ValueError("资源必须有 ligand/receptor，复合物保持原生格式")
    resource.to_csv(out/"resource.tsv",sep="\t",index=False)
    provenance.update(database_sha256=digest(out/"resource.tsv"),member=member,molecule_identity_schema=SCHEMA,parameters={k:cfg.get(k,d) for k,d in
        (("expr_prop",.1),("min_cells",10),("n_perms",1000),("seed",1))})
    provenance['rank_universe']='Native retained/testable LR candidates only; untested resource candidates appended after scoring, never included in rank denominators'
    bundle=dict(schema_version=2,dataset=cfg["dataset"],method="LIANA+ "+member,method_version=version,
                implementation="framework_reimplementation" if member!="rank_aggregate" else "native_framework_consensus",
                provenance=provenance,tables=[],research_question=cfg.get("research_question"),top_lr=cfg.get("top_lr",24))
    score_key,specificity,direction=methods[member]
    all_rows=[]
    for si,sample in enumerate(sorted(data.obs[keys["sample"]].unique())):
        subset=data[data.obs[keys["sample"]]==sample].copy()
        metadata=subset.obs.iloc[0]
        if subset.obs[keys["cell_type"]].nunique()<2:raise ValueError(f"{sample} 不足两个细胞群")
        result=getattr(li.mt,member)(subset,groupby=keys["cell_type"],resource=resource,use_raw=False,
            expr_prop=cfg.get("expr_prop",.1),min_cells=cfg.get("min_cells",10),n_perms=cfg.get("n_perms",1000),
            seed=cfg.get("seed",1),inplace=False,return_all_lrs=False,verbose=True)
        result.to_csv(out/f"native_{si+1:03d}.tsv",sep="\t",index=False)
        if score_key not in result:raise ValueError(f"原生结果缺少预期列 {score_key}: {list(result)}")
        # With return_all_lrs=True, native consensus includes ineligible worst-score
        # rows in rank denominators. Run the native retained-candidate path, then
        # append untested candidates without changing any native score or rank.
        columns=['source','target','ligand_complex','receptor_complex']
        if result.duplicated(columns).any():raise ValueError('LIANA 原生分子候选重复')
        native_rows={tuple(r[k] for k in columns):r for r in result.to_dict('records')}
        sizes=subset.obs[keys['cell_type']].value_counts()
        groups=sorted(sizes[sizes>=cfg.get('min_cells',10)].index)
        import itertools
        for (source,target),(ligand,receptor) in itertools.product(itertools.product(groups,repeat=2),
                resource[['ligand','receptor']].drop_duplicates().itertuples(index=False,name=None)):
            key=(source,target,ligand,receptor)
            row=native_rows.get(key,dict(zip(columns,key)))
            tested=key in native_rows and pd.notna(row.get(score_key))
            stat=row.get(specificity) if specificity else None
            # Consensus ranks are ranks, never calibrated P values.
            if member=="rank_aggregate":supported=tested and stat is not None and stat<=cfg.get("rank_cutoff",.05)
            elif specificity and specificity.endswith("pvals"):supported=tested and stat is not None and stat<cfg.get("alpha",.05)
            else:supported=False  # A score alone has no calibrated native support threshold.
            item=dict(sample=str(sample),donor=str(metadata[keys["donor"]]),condition=str(metadata[keys["condition"]]),
                source=str(row["source"]),target=str(row["target"]),ligand=str(row["ligand_complex"]),
                receptor=str(row["receptor_complex"]),score=float(row[score_key]) if tested else None,
                ligand_identity=gene_identity(row["ligand_complex"].split("_")),receptor_identity=gene_identity(row["receptor_complex"].split("_")),
                tested=tested,supported=supported,eligibility_reason='native_retained' if tested else 'not_retained_by_native_expression_or_resource_filters')
            if specificity and specificity.endswith("pvals"):item["p_value"]=float(stat) if tested else None
            all_rows.append(item)
    add_table(bundle,out,"lr_edges","lr_edges",all_rows,
        f"LIANA+ {member}: {score_key}; 原始分数，{direction} 为优先；specificity={specificity}。共识排名不是 P 值；无原生支持检验的评分不标支持边。",
        axis_label=score_key,direction=direction,value_kind="rank" if member=="rank_aggregate" else "native_score",additive=False)
    write_json(out/"bundle.json",bundle)
    from render_result_bundle import run as render
    return render(out/"bundle.json",out/"figures")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))

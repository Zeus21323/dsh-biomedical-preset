#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.14"
# dependencies = ["cellphonedb==5.0.1", "anndata==0.13.3.post0", "numpy==2.2.6", "matplotlib==3.10.6", "pycirclize==1.10.1", "pypdf==6.1.1"]
# ///
"""CellPhoneDB v5 native per-sample statistical analysis, preserving undirected ambiguity."""
import argparse
import json
from pathlib import Path
import sys
sys.dont_write_bytecode=True
from communication_contract import new_output,write_json,add_table,digest,truth
from communication_inputs import read_expression,require_version
from communication_identities import SCHEMA,cpdb_entities,directed_fields,cpdb_eligibility


def run(config,output):
    import pandas as pd
    from cellphonedb.src.core.methods import cpdb_statistical_analysis_method as native
    config=Path(config).resolve();cfg=json.loads(config.read_text())
    version=require_version("cellphonedb","5.0.1")
    data,keys,provenance=read_expression(cfg,config.parent)
    if cfg["species"]!="human":raise ValueError("此适配器只接受 human；不自动转换物种基因符号")
    db=(config.parent/cfg["database"]).resolve()
    if not db.is_file() or not cfg.get("database_version"):raise ValueError("需要原生 database zip 和版本声明")
    identities=cpdb_entities(db)
    out=new_output(output);write_json(out/"run_config.json",cfg)
    rows=[];ambiguity=[]
    for si,sample in enumerate(sorted(data.obs[keys["sample"]].unique())):
        subset=data[data.obs[keys["sample"]]==sample].copy()
        sizes=subset.obs[keys["cell_type"]].value_counts()
        subset=subset[subset.obs[keys["cell_type"]].isin(sizes[sizes>=cfg.get("min_cells",10)].index)].copy()
        if subset.obs[keys["cell_type"]].nunique()<2:raise ValueError(f"{sample} 过滤后不足两个细胞群")
        if subset.obs[keys["cell_type"]].str.contains("|",regex=False).any():raise ValueError("细胞标签包含原生分隔符 |")
        folder=out/f"native_{si+1:03d}";folder.mkdir()
        meta=pd.DataFrame({"Cell":subset.obs_names,"cell_type":subset.obs[keys["cell_type"]].to_numpy()})
        meta.to_csv(folder/"meta.tsv",sep="\t",index=False)
        extra={}
        for key in ("microenvs_file_path","active_tfs_file_path"):
            if cfg.get(key):
                path=(config.parent/cfg[key]).resolve()
                extra[key]=str(path);provenance[key+"_sha256"]=digest(path)
        result=native.call(cpdb_file_path=str(db),meta_file_path=str(folder/"meta.tsv"),counts_file_path=subset,
            counts_data=cfg.get("counts_data","hgnc_symbol"),output_path=str(folder),iterations=cfg.get("iterations",1000),
            threshold=cfg.get("expression_fraction",.1),threads=1,debug_seed=cfg.get("seed",1),result_precision=12,
            pvalue=cfg.get("alpha",.05),separator="|",score_interactions=cfg.get("score_interactions",False),debug=True,**extra)
        for key,frame in result.items():
            if isinstance(frame,pd.DataFrame):frame.to_csv(folder/(key+".tsv"),sep="\t",index=False)
        means=result["means"];pvalues=result["pvalues"].set_index("id_cp_interaction")
        # This file was created by the native invocation immediately above.
        import pickle
        with (folder/"debug_intermediate.pkl").open("rb") as handle:
            eligible=cpdb_eligibility(pickle.load(handle))
        eligible.to_csv(folder/"eligibility.tsv",sep="\t")
        metadata=subset.obs.iloc[0]
        pair_cols=[c for c in means if "|" in c]
        for item in means.to_dict("records"):
            identity=identities[item["id_cp_interaction"]];fields=directed_fields(identity)
            ra=identity["a"]["receptor"]
            if fields is None:
                ambiguity.append(dict(sample=sample,interaction=item["id_cp_interaction"],reason="双方均为受体或均非受体；不强制指定 ligand→receptor"))
                continue
            for pair in pair_cols:
                a,b=pair.split("|");p=float(pvalues.loc[item["id_cp_interaction"],pair]);score=float(item[pair])
                test=bool(eligible.loc[item["id_cp_interaction"],pair])
                rows.append(dict(sample=str(sample),donor=str(metadata[keys["donor"]]),condition=str(metadata[keys["condition"]]),
                    source=b if ra else a,target=a if ra else b,**fields,
                    interaction=str(item["id_cp_interaction"]),score=score if test else None,p_value=p if test else None,tested=test,
                    supported=test and p<cfg.get("alpha",.05)))
    provenance.update(database_sha256=digest(db),database_version=cfg["database_version"],parameters=cfg,
        test_unit="cell_label_permutation_within_sample",ambiguous_direction=ambiguity,molecule_identity_schema=SCHEMA,
        eligibility_definition="Native unrounded real_percent_analysis > 0 and real_mean_analysis > 0; each subunit detection fraction strictly greater than threshold")
    bundle=dict(schema_version=2,dataset=cfg["dataset"],method="CellPhoneDB",method_version=version,
        implementation="native",provenance=provenance,tables=[],top_lr=cfg.get("top_lr",24))
    add_table(bundle,out,"lr_edges","lr_edges",rows,
        "CellPhoneDB v5 mean；P 为样本内细胞标签置换。唯一受体方向用于有向图；未满足原生表达门槛者不当作已检验，原始均值/P保留在 native；非蛋白配体标注 proxy。",
        value_kind="native_score",direction="higher",axis_label="CellPhoneDB mean",additive=False)
    write_json(out/"bundle.json",bundle)
    from render_result_bundle import run as render
    return render(out/"bundle.json",out/"figures")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--config",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();sys.exit(run(a.config,a.out))

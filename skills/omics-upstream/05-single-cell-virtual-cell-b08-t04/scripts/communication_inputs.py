"""Explicit AnnData layer/sample checks shared by Python inference adapters."""
import importlib.metadata
from pathlib import Path
import numpy as np
from communication_contract import digest


def require_version(package, expected):
    version = importlib.metadata.version(package)
    if version != expected:
        raise ValueError(f"{package} 版本 {version} 与执行契约 {expected} 不符")
    return version


def read_expression(cfg, base):
    import anndata as ad
    path = Path(cfg["input"])
    path = (Path(base) / path).resolve()
    if cfg.get("species") not in ("human", "mouse"):
        raise ValueError("须明确 human/mouse；其他物种需先核验对应方法与资源")
    if cfg.get("expression_scale") not in ("log_normalized", "normalized", "counts"):
        raise ValueError("须明确表达层语义 expression_scale")
    if "layer" not in cfg:
        raise ValueError("须明确 layer=X 或实际层名，不自动读取 raw/整合表达")
    data = ad.read_h5ad(path)
    if not data.obs_names.is_unique or not data.var_names.is_unique:
        raise ValueError("细胞和基因 ID 必须唯一")
    keys = {k:cfg.get(k+"_key",k) for k in ("sample", "donor", "condition", "cell_type")}
    for key in keys.values():
        if key not in data.obs or data.obs[key].isna().any() or data.obs[key].astype(str).str.strip().eq("").any():
            raise ValueError(f"缺失或空 metadata: {key}")
        data.obs[key] = data.obs[key].astype(str)
    for sample, meta in data.obs.groupby(keys["sample"], observed=True):
        if any(meta[keys[k]].nunique()!=1 for k in ("donor","condition")):
            raise ValueError(f"样本 {sample} 不唯一对应供体/条件")
    layer = cfg["layer"]
    if layer != "X":
        if layer not in data.layers: raise ValueError("配置表达层不存在")
        data.X = data.layers[layer].copy()
    values = data.X.data if hasattr(data.X,"tocsr") else np.asarray(data.X)
    if not np.isfinite(values).all() or (values < 0).any():
        raise ValueError("表达必须有限非负，不能使用带负值的整合层")
    if cfg["expression_scale"] == "counts" and not np.allclose(values,np.round(values),atol=1e-7):
        raise ValueError("counts 层包含非整数值")
    if cfg.get("samples"):
        requested=cfg["samples"]
        if not set(requested)<=set(data.obs[keys["sample"]]):raise ValueError("指定样本不存在")
        data=data[data.obs[keys["sample"]].isin(requested)].copy()
    return data, keys, dict(input_sha256=digest(path), layer=layer, expression_scale=cfg["expression_scale"],
                            species=cfg["species"], sample_columns=keys)

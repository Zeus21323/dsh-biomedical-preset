"""
scvi-tools 内核辅助函数。加载本技能时，宿主会将以下函数自动载入 Python 内核：

 h5ad_safe_obs

模块顶层只包含定义（函数和字面量常量），并且只使用标准库，因此能够通过
sidecar AST 检查，也能在 ``python3 -I -S`` 骨架检查中加载；numpy/pandas
仅在函数体内延迟导入。
"""


def h5ad_safe_obs(df):
    """返回 `df` 的副本，并转换索引和类字符串列，使 anndata 能够调用
    `.write_h5ad()`，且不会出现
    ``IORegistryError: No method registered for writing
    <class 'pandas.arrays.ArrowStringArray'>`` (anndata #2377).

    anndata 0.11.x 的 HDF5 写入器没有为 pyarrow 支持的字符串列注册写入方法
    （dtype 为 ``string[pyarrow]`` / ``large_string[pyarrow]`` / 字典编码）；
    ``anndata.settings.allow_write_nullable_strings`` 只控制 Python 支持的
    ``pd.arrays.StringArray``，并不覆盖 Arrow。

    仅使用 ``.astype(str)`` 并不够：对于 pyarrow 支持的 Index/Series，
    它会返回另一个 Arrow 支持的数组。通过
    ``np.asarray(..., dtype=object)`` 往返转换，强制生成普通 object 数组，
    然后再转换为 ``Categorical``。空值会得到保留（NA 在分类变量中仍为 NA，
    而不会变成字面字符串 ``"<NA>"``/``"nan"``）。

    典型用法::

        adata.obs = h5ad_safe_obs(adata.obs)
        adata.var = h5ad_safe_obs(adata.var)
        adata.write_h5ad("out.h5ad")
    """
    import numpy as np
    import pandas as pd

    out = df.copy()
    out.index = pd.Index(
        np.asarray(out.index, dtype=object).astype(str), name=out.index.name
    )
    for c in out.columns:
        dt = str(out[c].dtype)
        # 子串 "string" 可以覆盖 string / string[python] / string[pyarrow] /
        # large_string[pyarrow] / dictionary<values=string,...>[pyarrow]，
        # 同时不会误选 int64[pyarrow]、double[pyarrow]、bool[pyarrow]、
        # timestamp[...][pyarrow] 等类型。
        if dt == "object" or "string" in dt:
            mask = out[c].notna()
            vals = np.asarray(out[c].astype(object).where(mask, None), dtype=object)
            vals[mask.to_numpy()] = np.asarray(out[c][mask].astype(str), dtype=object)
            out[c] = pd.Categorical(vals)
    return out

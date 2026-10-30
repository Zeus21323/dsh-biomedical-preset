"""Explicit data adequacy checks; these do not replace FlowSig graph inference."""


def variance_eligibility(values, labels, names, floor=1e-4, min_variable_cells=10):
    import numpy as np
    values=np.asarray(values,dtype=float);labels=np.asarray(labels)
    if values.ndim!=2 or values.shape!=(len(labels),len(names)) or not np.isfinite(values).all():
        raise ValueError('Flow变量必须有限且与条件、变量ID对齐')
    if not 0<floor<1 or not isinstance(min_variable_cells,int) or min_variable_cells<10:
        raise ValueError('相对标准差下限须在(0,1)，每条件至少10个可辨识变异细胞')
    pooled=values.std(0);eligible=pooled>0;records=[]
    for condition in sorted(set(labels)):
        subset=values[labels==condition];sd=subset.std(0)
        ratio=np.divide(sd,pooled,out=np.zeros_like(sd),where=pooled>0)
        n_variable=np.sum(np.abs(subset-np.median(subset,axis=0))>floor*pooled,axis=0)
        accepted=(ratio>=floor)&(n_variable>=min_variable_cells);eligible &= accepted
        records.extend(dict(variable=v,condition=str(condition),relative_sd=float(q),n_variable_cells=int(n),condition_testable=bool(ok))
                       for v,q,n,ok in zip(names,ratio,n_variable,accepted))
    return eligible,records


def shared_scale(values):
    import numpy as np
    values=np.asarray(values,dtype=float);scale=values.std(axis=0)
    if not np.isfinite(values).all() or not np.isfinite(scale).all() or (scale<=0).any():
        raise ValueError('全局flow变量方差无效')
    return values/scale,scale

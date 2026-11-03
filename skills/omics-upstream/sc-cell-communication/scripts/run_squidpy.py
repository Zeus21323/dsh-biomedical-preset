#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12,<3.13"
# dependencies = ["squidpy==1.8.3", "numpy==2.1.3", "anndata==0.13.3.post0"]
# ///
"""Native Squidpy LR permutation and spatial neighbourhood enrichment, kept separate."""
import argparse
import json
from pathlib import Path
import pickle
import sys
import warnings

sys.dont_write_bytecode = True
from communication_contract import add_table, digest, new_output, write_json
from communication_inputs import read_expression, require_version
from communication_identities import SCHEMA, gene_identity


def run(config, output):
    import numpy as np
    import pandas as pd
    import squidpy as sq
    from statsmodels.stats.multitest import multipletests

    require_version('squidpy', '1.8.3')
    cp = Path(config).resolve()
    cfg = json.loads(cp.read_text())
    data, keys, provenance = read_expression(cfg, cp.parent)
    upper_genes = [str(g).upper() for g in data.var_names]
    if len(set(upper_genes)) != len(upper_genes):
        raise ValueError('原生Squidpy会大写基因名；输入存在大写后冲突，拒绝静默删除基因')
    gene_names = dict(zip(upper_genes, map(str, data.var_names)))
    if cfg['expression_scale'] not in ('normalized', 'log_normalized') or not cfg.get('normalization_definition'):
        raise ValueError('LR检验需要注明归一化定义的非负表达，不能猜测counts的转换')
    branches = cfg.get('branches', ['lr', 'neighborhood'])
    if not branches or not set(branches) <= {'lr', 'neighborhood'}:
        raise ValueError('branches只能包含lr/neighborhood')
    permutations = int(cfg.get('n_perms', 1000))
    threshold = float(cfg.get('detection_threshold', .1))
    alpha = float(cfg.get('fdr', .05))
    if permutations < 100 or not 0 < threshold <= 1 or not 0 < alpha < 1:
        raise ValueError('置换数至少100，检测比例与FDR阈值须有效')
    resource = None
    if 'lr' in branches:
        for key in ('resource_file', 'resource_version', 'resource_provenance', 'resource_species'):
            if not cfg.get(key):
                raise ValueError('需要固定来源的显式LR资源：' + key)
        if cfg['resource_species'] != cfg['species']:
            raise ValueError('资源物种与表达物种不一致')
        resource_path = (cp.parent / cfg['resource_file']).resolve()
        resource = pd.read_csv(resource_path, sep='\t', dtype=str)
        if not {'source', 'target'} <= set(resource) or resource[['source', 'target']].isna().any().any():
            raise ValueError('资源需要非空source/target基因符号')
        # Native min policy can pick one measured component of an incomplete
        # complex. This adapter deliberately requires explicit single-gene pairs.
        if resource[['source', 'target']].apply(lambda s: s.str.contains('_', regex=False)).any().any():
            raise ValueError('当前分支仅接受单基因LR；不能以不完整复合物最小亚基冒充完整复合物')
        resource = resource.drop_duplicates(['source', 'target'])
        provenance['database_sha256'] = digest(resource_path)
    spatial = {}
    if 'neighborhood' in branches:
        unit = cfg.get('coordinate_unit')
        if unit not in ('um', 'pixel', 'native') or not cfg.get('coordinate_provenance'):
            raise ValueError('需要真实坐标单位及来源')
        if unit == 'native' and not cfg.get('physical_scale_unavailable'):
            raise ValueError('未知物理比例须显式记录，不能解释为微米传播距离')
        spatial_key = cfg.get('spatial_key', 'spatial')
        xy = np.asarray(data.obsm.get(spatial_key))
        if xy.shape != (data.n_obs, 2) or not np.isfinite(xy).all():
            raise ValueError('需要与实际细胞一一对应的有限二维组织坐标')
        spatial = {k: cfg[k] for k in ('coordinate_unit', 'coordinate_provenance', 'physical_scale_unavailable', 'y_down') if k in cfg}
    out = new_output(output)
    write_json(out / 'run_config.json', cfg)
    bundle = dict(schema_version=2, dataset=cfg['dataset'], method='Squidpy', method_version='1.8.3', implementation='native',
                  provenance={**provenance, 'parameters': cfg, 'molecule_identity_schema': SCHEMA,
                              'test_unit': '单样本细胞标签置换；LR不使用坐标，邻域Z基于真实空间图；均不是供体条件检验',
                              'lr_p_definition': '保留原生严格右尾b/n置换P；可为0，不能解释为精确零概率；额外BH覆盖每样本全部有限LR×细胞对P'}, tables=[])
    all_lr = []
    native_hashes = {}
    for si, sample in enumerate(sorted(data.obs[keys['sample']].unique()), 1):
        sub = data[data.obs[keys['sample']] == sample].copy()
        sizes = sub.obs[keys['cell_type']].value_counts()
        sub = sub[sub.obs[keys['cell_type']].isin(sizes[sizes >= cfg.get('min_cells', 10)].index)].copy()
        sub.obs[keys['cell_type']] = sub.obs[keys['cell_type']].astype('category').cat.remove_unused_categories()
        labels = list(sub.obs[keys['cell_type']].cat.categories)
        if len(labels) < 2:
            raise ValueError('样本内合格细胞群不足2')
        native = dict(cells=list(sub.obs_names), metadata=sub.obs.copy())
        if 'lr' in branches:
            result = sq.gr.ligrec(sub, keys['cell_type'], interactions=resource.copy(), use_raw=False, copy=True,
                                 threshold=threshold, n_perms=permutations, seed=cfg.get('seed', 1),
                                 corr_method=None, n_jobs=1, numba_parallel=False, show_progress_bar=False)
            native['ligrec'] = result
            means = result['means'].sparse.to_dense()
            pvalues = result['pvalues'].sparse.to_dense()
            pp = pvalues.to_numpy(); qq = np.full_like(pp, np.nan)
            finite = np.isfinite(pp)
            if finite.any():
                qq[finite] = multipletests(pp[finite], method='fdr_bh')[1]
            for i, (ligand, receptor) in enumerate(means.index):
                native_ligand, native_receptor = ligand, receptor
                ligand, receptor = gene_names[ligand], gene_names[receptor]
                for j, (source, target) in enumerate(means.columns):
                    tested = bool(finite[i, j])
                    all_lr.append(dict(sample=str(sample), donor=str(sub.obs.iloc[0][keys['donor']]),
                        condition=str(sub.obs.iloc[0][keys['condition']]), source=str(source), target=str(target),
                        ligand=ligand, receptor=receptor, ligand_identity=gene_identity([ligand]), receptor_identity=gene_identity([receptor]),
                        native_ligand=native_ligand, native_receptor=native_receptor,
                        score=float(means.iloc[i, j]) if tested else None,
                        p_value=float(pp[i, j]) if tested else None, q_value=float(qq[i, j]) if tested else None,
                        tested=tested, supported=bool(tested and qq[i, j] < alpha)))
        if 'neighborhood' in branches:
            # Radius graph is undirected and has no implied ligand orientation.
            # Delaunay is available for uncalibrated examples; never invent μm.
            if cfg.get('neighborhood_graph', 'delaunay') == 'radius':
                radius = float(cfg['radius'])
                if radius <= 0:
                    raise ValueError('邻域半径必须为正，单位与原始坐标一致')
                sq.gr.spatial_neighbors_radius(sub, spatial_key=spatial_key, radius=radius)
            elif cfg.get('neighborhood_graph', 'delaunay') == 'delaunay':
                sq.gr.spatial_neighbors_delaunay(sub, spatial_key=spatial_key)
            else:
                raise ValueError('neighborhood_graph须为radius/delaunay')
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter('always')
                nhood = sq.gr.nhood_enrichment(sub, keys['cell_type'], n_perms=permutations,
                    seed=cfg.get('seed', 1), n_jobs=1, numba_parallel=False, show_progress_bar=False, copy=True)
            native['neighborhood'] = nhood
            native['connectivities'] = sub.obsp['spatial_connectivities']
            native['coordinates'] = np.asarray(sub.obsm[spatial_key])
            native['warnings'] = [str(w.message) for w in caught]
            for name, matrix, definition, kind in (
                ('zscore', nhood.zscore, '原生邻域标签置换Z=(观测邻接计数−置换均值)/置换标准差；非有限Z保留缺失，不转成P值或LR强度', 'signed_score'),
                ('counts', nhood.counts, '原生空间图中细胞类别的邻接条目计数；对称两向存储，不解释为有向LR通讯数', 'count')):
                rows = [dict(row=str(a), column=str(b), value=float(matrix[i, j]) if np.isfinite(matrix[i, j]) else None)
                        for i, a in enumerate(labels) for j, b in enumerate(labels)]
                add_table(bundle, out, f'neighborhood_{name}_{si}', 'matrix', rows, definition,
                          value_kind=kind, axis_label='Neighbourhood Z' if name == 'zscore' else 'Adjacency entries',
                          figure_role='neighborhood', sample=str(sample), title=f'{sample}: neighbourhood {name}')
            xy = np.asarray(sub.obsm[spatial_key]); graph = sub.obsp['spatial_connectivities'].tocoo()
            counts = np.asarray(sub.obsp['spatial_connectivities'].getnnz(axis=1)).ravel()
            points = [dict(sample=str(sample), cell=str(c), x=float(xy[i, 0]), y=float(xy[i, 1]), value=int(counts[i])) for i, c in enumerate(sub.obs_names)]
            edges = [dict(sample=str(sample), source_cell=str(sub.obs_names[i]), target_cell=str(sub.obs_names[j]), value=float(v))
                     for i, j, v in zip(graph.row, graph.col, graph.data) if i < j]
            add_table(bundle, out, f'positions_{si}', 'spatial_points', points, '实际组织坐标；颜色为原生邻居数，不是通讯活性', axis_label='Neighbour count', **spatial)
            add_table(bundle, out, f'neighborhood_edges_{si}', 'spatial_edges', edges, '实际Delaunay/半径图的一份无向边，非LR推断，不能添加箭头', directed=False, **spatial)
        obj = out / f'native_{si}.pkl'
        with obj.open('wb') as stream:
            pickle.dump(native, stream, protocol=pickle.HIGHEST_PROTOCOL)
        native_hashes[obj.name] = digest(obj)
    if 'lr' in branches:
        add_table(bundle, out, 'lr_edges', 'lr_edges', all_lr,
                  'Squidpy原生两端群平均表达的算术平均；有限原生P为已检验，支持为每样本全部有限候选BH<阈值；此LR检验不使用空间坐标',
                  value_kind='native_score', additive=False, axis_label='Squidpy mean-expression score')
    bundle['provenance']['native_sha256'] = native_hashes
    write_json(out / 'bundle.json', bundle)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    sys.exit(run(args.config, args.out))

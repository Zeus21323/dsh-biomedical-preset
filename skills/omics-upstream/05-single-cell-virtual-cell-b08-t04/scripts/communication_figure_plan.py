"""Figure-family coverage built from evidence, not inferred from file existence alone."""
from collections import defaultdict

# The 22 agreed families are delivery capabilities, not 22 mandatory conclusions.
# Missing results alone do not prove that an analysis is biologically inapplicable.
FAMILIES = (
    ('overview', '总体/焦点/通路网络与自分泌环', ('lr_edges', 'network')),
    ('circos', '细胞/通路弦图与分组多环Circos', ('lr_edges', 'network')),
    ('lr_evidence', 'LR气泡、点图与tileplot', ('lr_edges',)),
    ('matrices', '细胞对、通路与LR矩阵热图', ('matrix', 'lr_edges')),
    ('condition_effects', '条件效应、供体点与差异网络', ('effects', 'effect_summary')),
    ('hierarchy', '发送者/接收者层级与二部网络', ('lr_edges', 'network')),
    ('roles', '发送/接收角色、中心性、数量与贡献', ('lr_edges',)),
    ('cellchat_patterns', 'CellChat原生NMF河流与模式点图', ()),
    ('pathway_sankey', '发送者→通路→接收者桑基图', ('lr_edges',)),
    ('ligand_response', '配体活性与靶基因潜力', ('activities',)),
    ('intracellular', 'LR–TF–target层级与机制Circos', ('molecular_links',)),
    ('factors', '张量/MOFA/NMF载荷、秩与稳定性', ('patterns',)),
    ('enrichment', '有明确定义背景的富集热图与点图', ('enrichment',)),
    ('embedding', 'UMAP与真实计算的细胞/分子潜在空间', ('latent_points','embedding_points')),
    ('spatial_location', '组织定位、空间边、图像与距离', ('spatial_points', 'spatial_edges')),
    ('spatial_hotspots', '局部LR热点与空间程序', ()),
    ('spatial_direction', '空间向量、方向汇总与流线', ('spatial_vectors',)),
    ('neighborhood_response', '邻域富集、视图贡献与target响应', ()),
    ('relay_dynamic', '多跳、真实3D与时间/轨迹', ('time_series',)),
    ('special_molecules', '代谢物/递质网络与分子证据', ('metabolite_edges',)),
    ('functional_clinical', '功能评分与真实临床/药敏关联', ()),
    ('robustness', '方法/资源一致性与敏感性', ()),
)
IDS = {row[0] for row in FAMILIES}
ROLES = {'convergence': 'factors', 'neighborhood': 'neighborhood_response', 'spatial_hotspot': 'spatial_hotspots',
         'intracellular_response': 'intracellular',
         'method_agreement': 'robustness', 'sensitivity': 'robustness', 'embedding': 'embedding',
         'rank_comparison': 'robustness',
         'sender_similarity': 'robustness',
         'spacia_fdr': 'robustness', 'spacia_psrf': 'robustness', 'spacia_mcmc_trace': 'robustness',
         'spacia_signal_effects': 'neighborhood_response', 'spacia_distance_effects': 'neighborhood_response',
         'cellnest_graph_qc': 'robustness', 'cellnest_celltype_roles': 'roles',
         'cellnest_lr_summary': 'lr_evidence', 'cellnest_stability': 'robustness',
         'cellnest_loss': 'robustness', 'cellnest_attention_distribution': 'robustness',
         'cellnest_relay_counts': 'relay_dynamic', 'cellnest_relay_roles': 'relay_dynamic',
         'cellnest_relay_confidence': 'intracellular',
         'renoir_graph_qc': 'robustness', 'renoir_pair_summary': 'ligand_response',
         'renoir_domain_pair_activity': 'neighborhood_response', 'renoir_domain_evidence': 'neighborhood_response',
         'renoir_program_activity': 'neighborhood_response', 'renoir_stability': 'robustness',
         'spaci_lr_scores': 'lr_evidence', 'spaci_training_history': 'robustness',
         'spaci_validation': 'robustness', 'spaci_threshold_sensitivity': 'robustness',
         'spaci_embedding': 'embedding',
         'stmlnet_lrtg_importance': 'intracellular', 'stmlnet_regulator_importance': 'intracellular',
         'stmlnet_model_quality': 'robustness', 'stmlnet_distance_sensitivity': 'robustness',
         'cscp_consensus': 'robustness', 'cscp_restart_agreement': 'robustness', 'cscp_pair_sizes': 'roles',
         'mdic3_celltype_matrix': 'matrices', 'mdic3_roles': 'roles', 'mdic3_cell_matrix': 'matrices', 'mdic3_diagnostics': 'robustness',
         'deepcolor_spatial_abundance': 'spatial_location', 'deepcolor_colocalization_matrix': 'matrices',
         'deepcolor_mapping_qc': 'robustness', 'deepcolor_diagnostics': 'robustness',
         'deepcolor_training': 'robustness', 'deepcolor_pair_eligibility': 'robustness',
         'deepcolor_pair_embedding': 'embedding', 'deepcolor_pair_clusters': 'factors',
         'deepcolor_ligand_coactivity': 'ligand_response', 'deepcolor_ligand_links': 'intracellular',
         'cellagentchat_lr': 'lr_evidence', 'cellagentchat_network': 'hierarchy',
         'cellagentchat_supported': 'matrices', 'cellagentchat_background': 'robustness',
         'cellagentchat_receiving': 'roles', 'cellagentchat_spatial_receiving': 'spatial_location',
         'cellagentchat_diagnostics': 'robustness',
         'remi_network': 'overview', 'remi_roles': 'roles', 'remi_communities': 'robustness',
         'remi_diagnostics': 'robustness',
         'variance_signature': 'neighborhood_response', 'nested_cross_validation': 'robustness',
         'spatial_scale_profile': 'robustness',
         'functional_score': 'functional_clinical', 'clinical_association': 'functional_clinical',
         'interaction_enrichment': 'enrichment', 'ligand_target': 'ligand_response', 'centrality': 'roles', 'cellchat_nmf': 'cellchat_patterns'}


def table_families(spec, rows):
    kind = spec['type']
    if spec.get('figure_role') in ROLES:
        return {ROLES[spec['figure_role']]}
    result = {key for key, _, kinds in FAMILIES if kind in kinds}
    if kind == 'lr_edges' and (not spec.get('additive') or not any(r.get('pathway') for r in rows)):
        result.discard('pathway_sankey')
    return result


def figure_families(spec, identifier):
    """Called when saving the actual figure; tags describe what was drawn."""
    kind = spec['type']
    if spec.get('figure_role') in ROLES:
        return [ROLES[spec['figure_role']]]
    if kind == 'molecular_links':
        return ['intracellular']
    if kind == 'metabolite_edges':
        return ['special_molecules']
    if kind in ('lr_edges', 'network'):
        if '_paper_overview_' in identifier:
            return ['overview', 'lr_evidence', 'matrices', 'roles']
        if '_pathway_sankey_' in identifier:
            return ['pathway_sankey']
        if '_chord' in identifier or '_grouped_circos_' in identifier:
            return ['circos']
        if '_hierarchy' in identifier:
            return ['hierarchy', 'overview']
        if '_bubble_' in identifier:
            return ['lr_evidence']
        if '_count_heatmap_' in identifier:
            return ['matrices']
    return sorted({key for key, _, kinds in FAMILIES if kind in kinds})


def build_plan(bundle, tables):
    observed = defaultdict(list)
    for spec, rows, _ in tables:
        for family in table_families(spec, rows):
            supported_only=family in {'overview','circos','hierarchy','roles','pathway_sankey'} and spec['type']=='lr_edges'
            eligible=any(r['supported'] for r in rows) if supported_only else bool(rows)
            observed[family].append(dict(table=spec['id'], rows=len(rows), sha256=spec['sha256'],eligible=eligible,
                exclusion_reason='没有符合已声明支持规则的LR，不生成有向支持网络或其角色图' if rows and supported_only and not eligible else ''))
    unavailable = bundle.get('figure_inapplicability', {})
    if not set(unavailable) <= IDS or any(not isinstance(v, str) or not v.strip() for v in unavailable.values()):
        raise ValueError('图型不适用声明必须使用真实family ID并给出已核实原因')
    plan = []
    for family, label, _ in FAMILIES:
        sources = observed[family]
        if sources and family in unavailable:
            raise ValueError('已有结果与图型不适用声明矛盾：' + family)
        if sources:
            status = 'planned' if any(s['eligible'] for s in sources) else 'not_applicable'
            reason = '已存在实际结果，自动执行适用绘图' if status == 'planned' else next((s['exclusion_reason'] for s in sources if s['exclusion_reason']), '原生结果为空，保留空表与过滤记录')
        elif family in unavailable:
            status, reason = 'not_applicable', unavailable[family]
        else:
            status, reason = 'not_available', '本结果包未提供该类分析证据；尚不能断定是数据不适用、未执行分析或实现缺口'
        plan.append(dict(family=family, label=label, status=status, reason=reason, sources=sources,
                         figures=[], subtype_coverage='仅下列实际图件，不代表本图族全部子类型均已实现'))
    return plan


def finish_plan(plan, figures):
    for item in plan:
        matched = [f for f in figures if item['family'] in f.get('families', [])]
        item['figures'] = [dict(id=f['id'], status=f['status']) for f in matched]
        if matched:
            if any(f['status'] == 'failed' for f in matched):
                item.update(status='partial' if any(f['status'] == 'generated' for f in matched) else 'failed',
                            reason='至少一个适用图件生成失败；保留其他成功图件')
            elif any(f['status'] == 'generated' for f in matched):
                item.update(status='generated', reason='图件已生成；技术检查和逐图视觉审阅状态另列')
            else:
                item.update(status='not_applicable', reason='该结果内没有满足展示条件的原生候选；逐图原因另列')
        elif item['status'] == 'planned':
            item.update(status='not_rendered', reason='有相关结果但本次未生成该类图件；必须核查候选资格或绘图实现，不能按成功交付')
    return plan

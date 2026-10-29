"""R/Python共用TSV色板；类别按身份映射，拒绝缺失或重复颜色。"""
import csv
import hashlib
from pathlib import Path
import re

PALETTES = Path(__file__).resolve().parents[1] / 'assets/scientific_palettes.tsv'


def table(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f, delimiter='\t')
        fields = reader.fieldnames or []
        rows = list(reader)
    if not rows or len(fields) != len(set(fields)) or any(None in r or None in r.values() for r in rows):
        raise ValueError('配色表为空、重复表头或列数不一致')
    return rows


def hex_color(value):
    if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
        raise ValueError('颜色须为六位HEX色号：' + str(value))
    return value.upper()


def palette(name, kind):
    rows = [r for r in table(PALETTES) if r['palette'] == name]
    if not rows or any(r['kind'] != kind for r in rows):
        raise ValueError('色板不存在或用途不符：' + str(name))
    rows.sort(key=lambda r: int(r['position']))
    positions = [int(r['position']) for r in rows]
    if positions != list(range(1, len(rows)+1)):
        raise ValueError('色板位置须连续唯一')
    return [hex_color(r['color']) for r in rows]


def mapping(categories, name='categorical_clear', explicit=None, registry=None, variable='group'):
    categories = list(categories)
    if not categories or len(categories) != len(set(categories)) or any(not isinstance(c,str) or not c.strip() for c in categories):
        raise ValueError('配色类别须非空且唯一')
    saved = None
    if registry is not None:
        rows = table(registry)
        if not {'variable','category','color'} <= set(rows[0]):
            raise ValueError('颜色映射表须含variable/category/color')
        all_keys = [(r['variable'],r['category']) for r in rows]
        if len(all_keys) != len(set(all_keys)) or any(not a.strip() or not b.strip() for a,b in all_keys):
            raise ValueError('颜色映射身份为空或重复')
        saved = {r['category']:hex_color(r['color']) for r in rows if r['variable']==variable}
    if explicit is not None:
        if not isinstance(explicit,dict): raise ValueError('显式颜色映射须为对象')
        explicit = {c:hex_color(v) for c,v in explicit.items()}
    if saved is not None and explicit is not None:
        if any(c not in saved or saved[c] != v for c,v in explicit.items()):
            raise ValueError('显式颜色与项目映射冲突')
    source = saved if saved is not None else explicit
    if source is None:
        colors = palette(name, 'categorical')
        if len(categories) > len(colors):
            raise ValueError('类别超出色板容量；提供项目映射或按依据分面，不能循环复用颜色')
        source = dict(zip(categories,colors))
    if any(c not in source for c in categories): raise ValueError('颜色映射未覆盖实际类别')
    # Validate the whole supplied variable, including temporarily absent categories.
    if len(set(source.values())) != len(source): raise ValueError('同一变量不同类别不能同色')
    return {c:source[c] for c in categories}


def colormap(signed, name=None):
    from matplotlib.colors import LinearSegmentedColormap
    name = name or ('blue_white_pink' if signed else 'blue_sequential')
    colors = palette(name, 'diverging' if signed else 'sequential')
    return LinearSegmentedColormap.from_list(name,colors,N=257).with_extremes(bad='#BDBDBD')


def record(config, base):
    result = {'palette_sha256':hashlib.sha256(PALETTES.read_bytes()).hexdigest(),
              'candidate_source':'user screenshots; not certified colorblind-safe',
              'mapping_scope':'project' if config.get('color_registry') else 'figure_only'}
    if config.get('color_registry'):
        result['registry_sha256']=hashlib.sha256((base/config['color_registry']).read_bytes()).hexdigest()
    return result


def export_mapping(path, mappings):
    with Path(path).open('x',encoding='utf-8',newline='') as f:
        writer=csv.writer(f,delimiter='\t');writer.writerow(['variable','category','color'])
        for variable,values in mappings.items():
            for category,color in values.items(): writer.writerow([variable,category,color])

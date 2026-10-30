#!/usr/bin/env python3
"""供R或外部绘图出口复用同一三格式尺寸校验；失败返回非零。"""
import argparse
from pathlib import Path
import runpy
import sys


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stem',type=Path,required=True)
    parser.add_argument('--width-mm',type=float,required=True)
    parser.add_argument('--height-mm',type=float,required=True)
    parser.add_argument('--dpi',type=float,required=True)
    parser.add_argument('--record',type=Path,required=True)
    args=parser.parse_args()
    core=runpy.run_path(str(Path(__file__).with_name('figure_delivery.py')))
    try:
        result=core['verify_bundle'](args.stem,args.width_mm,args.height_mm,args.dpi)
        import json
        with args.record.open('x',encoding='utf-8') as f:
            json.dump(result,f,ensure_ascii=False,indent=2)
        print('三格式尺寸与文件检查通过；内容和字体仍需审阅')
        return 0
    except Exception as error:
        print('图件未通过：'+str(error),file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())

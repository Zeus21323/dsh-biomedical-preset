#!/usr/bin/env python3
"""Install the pinned native CellCallEXT with an audited plotting-import compatibility fix.

Only enrichplot::plot_grid -> cowplot::plot_grid and its dependency declaration
change. Native scoring source is untouched. Source, build and audit stay outside Git.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import urllib.request
sys.dont_write_bytecode=True
from communication_contract import new_output,digest,write_json

COMMIT='8ce584ac27ebf2f709a1e1b640f8834dbbac27e6'
ARCHIVE_SHA256='c4b054af0a6b1cdb4da426c666ebac3e3d6f6502726560cf7db44dc7db1a57a7'
NAMESPACE_SHA256='ae824777238895699971346c5ac6613f856feefc17b2c61d0edbfac2213b3d1e'
DESCRIPTION_SHA256='32416e93e2aa59bf642577aa681db2fbd4ab4f95c3bdc32cb95d1081042f57ae'


def prepare(archive,out):
    if digest(archive)!=ARCHIVE_SHA256:raise ValueError('固定上游归档摘要不匹配，停止安装，不能跳过核验')
    with tarfile.open(archive) as tar:
        tar.extractall(out/'source',filter='data')
    definitions=list((out/'source').glob('*/DESCRIPTION'))
    if len(definitions)!=1:raise ValueError('归档结构不符合已核验包')
    root=definitions[0].parent;namespace=root/'NAMESPACE';description=root/'DESCRIPTION'
    if digest(namespace)!=NAMESPACE_SHA256 or digest(description)!=DESCRIPTION_SHA256:raise ValueError('上游补丁上下文不匹配')
    sources={str(p.relative_to(root)):digest(p) for p in (root/'R').glob('*.R')}
    text=namespace.read_text()
    if text.count('importFrom(enrichplot,plot_grid)')!=1:raise ValueError('导入声明不唯一')
    namespace.write_text(text.replace('importFrom(enrichplot,plot_grid)','importFrom(cowplot,plot_grid)'))
    description.write_text(description.read_text().replace('Imports:', 'Imports:\n    cowplot (>= 1.1.0),').rstrip()+
                          '\nConfig/CommunicationAdapter/SourceCommit: '+COMMIT+'\nConfig/CommunicationAdapter/Patch: plot-grid-import-only\n')
    if sources!={str(p.relative_to(root)):digest(p) for p in (root/'R').glob('*.R')}:raise ValueError('兼容补丁不得修改原生R算法源码')
    return root,dict(source_commit=COMMIT,source_archive_sha256=ARCHIVE_SHA256,native_r_sha256=sources,
                     compatibility_patch='NAMESPACE plot_grid import redirected to its actual provider cowplot; dependency declared; no scoring source edits',
                     patched_namespace_sha256=digest(namespace),patched_description_sha256=digest(description))


def run(args):
    out=new_output(args.out);archive=Path(args.archive).resolve() if args.archive else out/'source.tar.gz'
    if not args.archive:
        with urllib.request.urlopen('https://api.github.com/repos/shouguog/cellcallEXT/tarball/'+COMMIT,timeout=120) as response:
            archive.write_bytes(response.read())
    root,manifest=prepare(archive,out)
    library=Path(args.library).resolve()
    for parent in (library,*library.parents):
        if (parent/'.git').exists():raise ValueError('R库必须在Git外')
    library.mkdir(parents=True,exist_ok=True)
    if (library/'cellcallEXT').exists():raise ValueError('拒绝覆盖已有包；指定新的专用R库')
    # Paths travel as arguments to R, never interpolated into R or shell code.
    install=out/'install.R'
    install.write_text('a<-commandArgs(TRUE); install.packages(a[1],lib=a[2],repos=NULL,type="source"); if(!file.exists(file.path(a[2],"cellcallEXT","DESCRIPTION"))) stop("native installation failed")\n')
    with (out/'install.log').open('w') as log:
        result=subprocess.run([args.rscript,str(install),str(root),str(library)],stdout=log,stderr=subprocess.STDOUT,check=False,timeout=1800)
    manifest.update(library=str(library),rscript=args.rscript,returncode=result.returncode,status='installed' if result.returncode==0 else 'failed')
    if result.returncode==0 and digest(library/'cellcallEXT/NAMESPACE')!=manifest['patched_namespace_sha256']:
        manifest['status']='failed';manifest['error']='installed namespace does not match audited patch'
    write_json(out/'installation_manifest.json',manifest)
    return 0 if manifest['status']=='installed' else 2


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive');p.add_argument('--rscript',required=True);p.add_argument('--library',required=True);p.add_argument('--out',required=True)
    sys.exit(run(p.parse_args()))

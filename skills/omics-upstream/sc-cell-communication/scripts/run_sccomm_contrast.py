#!/usr/bin/env python3
"""Execute the unchanged, hash-pinned scComm contrastive program and retain its state."""
from __future__ import annotations
import argparse
import contextlib
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import pickle
import random
import re
import runpy
import sys
sys.dont_write_bytecode = True


def run():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',required=True)
    parser.add_argument('--work',required=True)
    parser.add_argument('--seed',type=int,default=42)
    args=parser.parse_args()
    if not 0<=args.seed<2**32:raise ValueError('seed out of range')
    # The native feature order is derived from a Python set; hash seed must be
    # established before interpreter startup, not assigned after importing it.
    if os.environ.get('PYTHONHASHSEED')!=str(args.seed):
        os.execve(sys.executable,[sys.executable,*sys.argv],{**os.environ,'PYTHONHASHSEED':str(args.seed),'PYTHONDONTWRITEBYTECODE':'1'})
    native=Path(args.native).resolve();work=Path(args.work).resolve()
    if any((p/'.git').exists() for p in (work,*work.parents)):raise ValueError('Real output must remain outside Git')
    if hashlib.sha256(native.read_bytes()).hexdigest()!='3f9915f4c8c40972f96f2979f9c2a397dc2ecf3fc5ff4c646e472838bfee19de':
        raise ValueError('Unverified native scComm contrastive source')
    if (work/'fulldata_prediction.csv').exists():raise ValueError('Refuse to overwrite native predictions')
    import numpy as np
    import pandas as pd
    import torch
    random.seed(args.seed);np.random.seed(args.seed);torch.manual_seed(args.seed)
    frames=[pd.read_csv(work/f'{name}.csv',index_col=0) for name in ('PositiveData','NegativeData','Fulldata')]
    if any(f.empty or not f.index.is_unique or not f.columns.is_unique or not np.isfinite(f.to_numpy()).all() for f in frames):raise ValueError('Invalid native augmentation data')
    if any(set(f.columns)!=set(frames[0].columns) for f in frames):raise ValueError('Native augmentation feature sets differ')
    os.chdir(work);sys.argv=[str(native),*(str(work/f'{name}.csv') for name in ('PositiveData','NegativeData','Fulldata'))]
    with (work/'native_contrast.log').open('x') as log,contextlib.redirect_stdout(log):state=runpy.run_path(str(native),run_name='__main__')
    model=state['encoder'];classifier=state['clf']
    if any(not torch.isfinite(v).all() for v in model.state_dict().values()):raise ValueError('Nonfinite native trained model')
    if not all(np.isfinite(v).all() for v in (classifier.coef_,classifier.intercept_,state['train_features'],state['fulldata_features'])):raise ValueError('Nonfinite native classifier or embedding')
    pred=pd.read_csv(work/'fulldata_prediction.csv')
    if list(pred.CCC_pair.astype(str))!=list(frames[2].index.astype(str)) or not set(pred.prediction).issubset({0,1}):raise ValueError('Native predictions lost row identity')
    torch.save({'state_dict':model.state_dict(),'native_feature_order':state['common_cols'],'native_labels':state['labels'].detach().cpu(),'native_train_features':state['train_features'],'native_full_features':state['fulldata_features']},work/'native_encoder.pt')
    with (work/'native_classifier.pkl').open('xb') as f:pickle.dump(classifier,f)
    history=re.findall(r'Epoch (\d+), Avg SupCon Loss: ([0-9.eE+-]+)',(work/'native_contrast.log').read_text())
    if not history or not all(np.isfinite(float(loss)) for _,loss in history):raise ValueError('Native training has no finite printed loss history')
    with (work/'native_loss_history.csv').open('x',newline='') as f:
        writer=csv.writer(f);writer.writerow(['epoch','loss']);writer.writerows(history)
    record={'seed':args.seed,'native_source_sha256':hashlib.sha256(native.read_bytes()).hexdigest(),'versions':{p:importlib.metadata.version(p) for p in ('numpy','pandas','torch','scikit-learn')},'device':str(state['device']),'native_feature_order':state['common_cols'],'input_sha256':{f'{name}.csv':hashlib.sha256((work/f'{name}.csv').read_bytes()).hexdigest() for name in ('PositiveData','NegativeData','Fulldata')},'limitations':'Native best_model_state is a shallow state_dict reference; preserve the returned model, do not describe it as an independently restored optimum. Classes come from same-data score augmentation, not biological ground truth, P values or external validation.'}
    (work/'contrast_provenance.json').write_text(json.dumps(record,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


if __name__=='__main__':run()

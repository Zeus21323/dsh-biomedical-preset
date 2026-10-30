#!/bin/bash
set -e

echo "[setup] Installing dependencies..."

pip install --quiet --no-cache-dir \
  -i https://pypi.tuna.tsinghua.edu.cn/simple \
  json-repair

echo "[setup] Done."
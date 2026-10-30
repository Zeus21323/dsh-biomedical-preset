#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
work_dir=$(mktemp -d)
trap 'rm -rf "$work_dir"' EXIT

touch "$work_dir/tumor.bam" "$work_dir/reference.cnn"
output=$(bash "$script_dir/run_ampliconsuite.sh" --dry-run \
  SAMPLE "$work_dir/tumor.bam" GRCh38 "$work_dir/reference.cnn" "$work_dir/output")

grep -q 'cnvkit.py' <<<"$output"
grep -q 'AmpliconSuite-pipeline.py' <<<"$output"
if [[ -e $work_dir/output ]]; then
  echo "dry-run 不应创建输出目录" >&2
  exit 1
fi
echo "ok: AmpliconSuite dry-run"

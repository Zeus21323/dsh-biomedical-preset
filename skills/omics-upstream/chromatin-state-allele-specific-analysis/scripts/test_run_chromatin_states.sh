#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
mkdir "$tmp_dir/bams"
touch "$tmp_dir/ChromHMM.jar" "$tmp_dir/chrom.sizes" "$tmp_dir/table.txt"

output=$(bash "$script_dir/run_chromatin_states.sh" \
  --jar "$tmp_dir/ChromHMM.jar" --genome hg38 \
  --chrom-sizes "$tmp_dir/chrom.sizes" --input-dir "$tmp_dir/bams" \
  --cell-mark-file "$tmp_dir/table.txt" --output-dir "$tmp_dir/out" \
  --states 18 --bin-size 200 --dry-run)

grep -q 'BinarizeBam' <<<"$output"
grep -q 'LearnModel' <<<"$output"
grep -q ' 18 ' <<<"$output"
[[ ! -d "$tmp_dir/out" ]]
printf 'ok: ChromHMM dry-run\n'

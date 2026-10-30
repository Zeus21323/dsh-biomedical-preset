#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
touch "$tmp_dir/manifest.csv" "$tmp_dir/metadata.tsv" "$tmp_dir/classifier.qza"

output=$(bash "$script_dir/run_qiime2_amplicon.sh" \
  --manifest "$tmp_dir/manifest.csv" --metadata "$tmp_dir/metadata.tsv" \
  --classifier "$tmp_dir/classifier.qza" --output-dir "$tmp_dir/out" \
  --trim-left-f 17 --trim-left-r 21 --trunc-len-f 240 --trunc-len-r 200 \
  --threads 4 --dry-run)

grep -q 'PairedEndFastqManifestPhred33V2' <<<"$output"
grep -q 'dada2 denoise-paired' <<<"$output"
grep -q -- '--p-trunc-len-f 240' <<<"$output"
grep -q 'feature-classifier classify-sklearn' <<<"$output"
[[ ! -d "$tmp_dir/out" ]]
printf 'ok: QIIME 2 dry-run\n'

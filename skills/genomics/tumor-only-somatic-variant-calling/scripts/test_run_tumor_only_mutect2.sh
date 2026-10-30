#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tmp_dir=$(mktemp -d)
trap 'rm -rf "$tmp_dir"' EXIT
touch "$tmp_dir/ref.fa" "$tmp_dir/tumor.bam" "$tmp_dir/pon.vcf.gz"

output=$(bash "$script_dir/run_tumor_only_mutect2.sh" \
  --reference "$tmp_dir/ref.fa" \
  --tumor-bam "$tmp_dir/tumor.bam" \
  --tumor-sample TUMOR_A \
  --pon "$tmp_dir/pon.vcf.gz" \
  --output-vcf "$tmp_dir/out/result.vcf.gz" \
  --dry-run)

grep -q 'Mutect2' <<<"$output"
grep -q -- '--panel-of-normals' <<<"$output"
grep -q 'FilterMutectCalls' <<<"$output"
[[ ! -e "$tmp_dir/out/result.vcf.gz" ]]
printf 'ok: tumor-only Mutect2 dry-run\n'

#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    '用法：run_chromatin_states.sh --jar ChromHMM.jar --genome hg38' \
    '      --chrom-sizes chrom.sizes --input-dir bam_dir --cell-mark-file table.txt' \
    '      --output-dir output [--states 15] [--bin-size 200] [--dry-run]'
}

jar=''
genome=''
chrom_sizes=''
input_dir=''
cell_mark_file=''
output_dir=''
states=15
bin_size=200
dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jar) jar=${2:-}; shift 2 ;;
    --genome) genome=${2:-}; shift 2 ;;
    --chrom-sizes) chrom_sizes=${2:-}; shift 2 ;;
    --input-dir) input_dir=${2:-}; shift 2 ;;
    --cell-mark-file) cell_mark_file=${2:-}; shift 2 ;;
    --output-dir) output_dir=${2:-}; shift 2 ;;
    --states) states=${2:-}; shift 2 ;;
    --bin-size) bin_size=${2:-}; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf '错误：未知参数 %s\n' "$1" >&2; exit 2 ;;
  esac
done

for required in jar genome chrom_sizes input_dir cell_mark_file output_dir; do
  [[ -n ${!required} ]] || { printf '错误：缺少 %s\n' "$required" >&2; exit 2; }
done
[[ "$states" =~ ^[1-9][0-9]*$ ]] || { printf '错误：--states 必须为正整数\n' >&2; exit 2; }
[[ "$bin_size" =~ ^[1-9][0-9]*$ ]] || { printf '错误：--bin-size 必须为正整数\n' >&2; exit 2; }
[[ -f "$jar" ]] || { printf '错误：找不到 ChromHMM JAR：%s\n' "$jar" >&2; exit 2; }
[[ -f "$chrom_sizes" ]] || { printf '错误：找不到染色体长度文件：%s\n' "$chrom_sizes" >&2; exit 2; }
[[ -f "$cell_mark_file" ]] || { printf '错误：找不到 cell-mark 表：%s\n' "$cell_mark_file" >&2; exit 2; }
[[ -d "$input_dir" ]] || { printf '错误：找不到输入目录：%s\n' "$input_dir" >&2; exit 2; }

binarized_dir="$output_dir/binarized"
model_dir="$output_dir/model"
binarize=(java -Xmx8g -jar "$jar" BinarizeBam -b "$bin_size"
  "$chrom_sizes" "$input_dir" "$cell_mark_file" "$binarized_dir")
learn=(java -Xmx8g -jar "$jar" LearnModel "$binarized_dir" "$model_dir" "$states" "$genome")

print_command() { printf '%q ' "$@"; printf '\n'; }
if [[ $dry_run -eq 1 ]]; then
  print_command "${binarize[@]}"
  print_command "${learn[@]}"
  exit 0
fi

command -v java >/dev/null 2>&1 || { printf '错误：未找到 java\n' >&2; exit 127; }
mkdir -p "$binarized_dir" "$model_dir"
"${binarize[@]}"
"${learn[@]}"

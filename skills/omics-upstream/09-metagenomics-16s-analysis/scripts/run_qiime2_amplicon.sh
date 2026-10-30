#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    '用法：run_qiime2_amplicon.sh --manifest manifest.csv --metadata metadata.tsv' \
    '      --classifier classifier.qza --output-dir output' \
    '      --trim-left-f N --trim-left-r N --trunc-len-f N --trunc-len-r N' \
    '      [--threads N] [--dry-run]'
}

manifest=''; metadata=''; classifier=''; output_dir=''
trim_left_f=''; trim_left_r=''; trunc_len_f=''; trunc_len_r=''
threads=1; dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --manifest) manifest=${2:-}; shift 2 ;;
    --metadata) metadata=${2:-}; shift 2 ;;
    --classifier) classifier=${2:-}; shift 2 ;;
    --output-dir) output_dir=${2:-}; shift 2 ;;
    --trim-left-f) trim_left_f=${2:-}; shift 2 ;;
    --trim-left-r) trim_left_r=${2:-}; shift 2 ;;
    --trunc-len-f) trunc_len_f=${2:-}; shift 2 ;;
    --trunc-len-r) trunc_len_r=${2:-}; shift 2 ;;
    --threads) threads=${2:-}; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf '错误：未知参数 %s\n' "$1" >&2; exit 2 ;;
  esac
done

for required in manifest metadata classifier output_dir trim_left_f trim_left_r trunc_len_f trunc_len_r; do
  [[ -n ${!required} ]] || { printf '错误：缺少 %s\n' "$required" >&2; exit 2; }
done
for number in "$trim_left_f" "$trim_left_r" "$trunc_len_f" "$trunc_len_r" "$threads"; do
  [[ "$number" =~ ^[0-9]+$ ]] || { printf '错误：长度和线程参数必须为非负整数\n' >&2; exit 2; }
done
[[ "$threads" -gt 0 ]] || { printf '错误：--threads 必须大于零\n' >&2; exit 2; }
for input_file in "$manifest" "$metadata" "$classifier"; do
  [[ -f "$input_file" ]] || { printf '错误：输入不存在：%s\n' "$input_file" >&2; exit 2; }
done

demux="$output_dir/demux.qza"
table="$output_dir/table.qza"
representative="$output_dir/representative-sequences.qza"
stats="$output_dir/denoising-stats.qza"
taxonomy="$output_dir/taxonomy.qza"

if [[ $dry_run -eq 0 ]] && ! command -v qiime >/dev/null 2>&1; then
  printf '错误：未找到 qiime 命令\n' >&2
  exit 127
fi
if [[ $dry_run -eq 0 && -e "$output_dir" && -n $(find "$output_dir" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
  printf '错误：输出目录非空，拒绝覆盖：%s\n' "$output_dir" >&2
  exit 2
fi
[[ $dry_run -eq 1 ]] || mkdir -p "$output_dir"

run_command() {
  if [[ $dry_run -eq 1 ]]; then
    printf '%q ' "$@"
    printf '\n'
  else
    "$@"
  fi
}

run_command qiime tools import \
  --type 'SampleData[PairedEndSequencesWithQuality]' \
  --input-path "$manifest" --output-path "$demux" \
  --input-format PairedEndFastqManifestPhred33V2
run_command qiime demux summarize \
  --i-data "$demux" --o-visualization "$output_dir/demux.qzv"
run_command qiime dada2 denoise-paired \
  --i-demultiplexed-seqs "$demux" \
  --p-trim-left-f "$trim_left_f" --p-trim-left-r "$trim_left_r" \
  --p-trunc-len-f "$trunc_len_f" --p-trunc-len-r "$trunc_len_r" \
  --p-n-threads "$threads" --o-table "$table" \
  --o-representative-sequences "$representative" --o-denoising-stats "$stats"
run_command qiime metadata tabulate \
  --m-input-file "$stats" --o-visualization "$output_dir/denoising-stats.qzv"
run_command qiime feature-classifier classify-sklearn \
  --i-classifier "$classifier" --i-reads "$representative" \
  --p-n-jobs "$threads" --o-classification "$taxonomy"
run_command qiime metadata tabulate \
  --m-input-file "$taxonomy" --o-visualization "$output_dir/taxonomy.qzv"
run_command qiime feature-table summarize \
  --i-table "$table" --m-sample-metadata-file "$metadata" \
  --o-visualization "$output_dir/table.qzv"

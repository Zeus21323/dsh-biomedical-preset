#!/usr/bin/env bash
set -euo pipefail

usage() {
  printf '%s\n' \
    '用法：run_tumor_only_mutect2.sh --reference ref.fa --tumor-bam tumor.bam' \
    '      --tumor-sample SAMPLE --output-vcf result.vcf.gz [选项]' \
    '' \
    '选项：' \
    '  --pon FILE                 正常样本面板 VCF' \
    '  --germline-resource FILE   胚系群体频率 VCF' \
    '  --intervals FILE           interval list 或 BED' \
    '  --contamination-table FILE CalculateContamination 输出' \
    '  --java-options TEXT        默认 -Xmx8g' \
    '  --dry-run                  只检查并打印命令' \
    '  -h, --help                 显示帮助'
}

reference=''
tumor_bam=''
tumor_sample=''
output_vcf=''
pon=''
germline_resource=''
intervals=''
contamination_table=''
java_options='-Xmx8g'
dry_run=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --reference) reference=${2:-}; shift 2 ;;
    --tumor-bam) tumor_bam=${2:-}; shift 2 ;;
    --tumor-sample) tumor_sample=${2:-}; shift 2 ;;
    --output-vcf) output_vcf=${2:-}; shift 2 ;;
    --pon) pon=${2:-}; shift 2 ;;
    --germline-resource) germline_resource=${2:-}; shift 2 ;;
    --intervals) intervals=${2:-}; shift 2 ;;
    --contamination-table) contamination_table=${2:-}; shift 2 ;;
    --java-options) java_options=${2:-}; shift 2 ;;
    --dry-run) dry_run=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) printf '错误：未知参数 %s\n' "$1" >&2; usage >&2; exit 2 ;;
  esac
done

for required in reference tumor_bam tumor_sample output_vcf; do
  if [[ -z ${!required} ]]; then
    printf '错误：缺少必需参数 %s\n' "$required" >&2
    exit 2
  fi
done

for input_file in "$reference" "$tumor_bam"; do
  [[ -f "$input_file" ]] || { printf '错误：输入文件不存在：%s\n' "$input_file" >&2; exit 2; }
done
for optional_file in "$pon" "$germline_resource" "$intervals" "$contamination_table"; do
  [[ -z "$optional_file" || -f "$optional_file" ]] || {
    printf '错误：可选输入文件不存在：%s\n' "$optional_file" >&2
    exit 2
  }
done

if [[ "$output_vcf" != *.vcf.gz ]]; then
  printf '错误：--output-vcf 必须以 .vcf.gz 结尾\n' >&2
  exit 2
fi

unfiltered_vcf=${output_vcf%.vcf.gz}.unfiltered.vcf.gz
f1r2_tar=${output_vcf%.vcf.gz}.f1r2.tar.gz
orientation_model=${output_vcf%.vcf.gz}.read-orientation-model.tar.gz

mutect=(gatk --java-options "$java_options" Mutect2
  -R "$reference" -I "$tumor_bam" --tumor-sample "$tumor_sample"
  --f1r2-tar-gz "$f1r2_tar" -O "$unfiltered_vcf")
[[ -n "$pon" ]] && mutect+=(--panel-of-normals "$pon")
[[ -n "$germline_resource" ]] && mutect+=(--germline-resource "$germline_resource")
[[ -n "$intervals" ]] && mutect+=(-L "$intervals")

orientation=(gatk --java-options "$java_options" LearnReadOrientationModel
  -I "$f1r2_tar" -O "$orientation_model")

filter=(gatk --java-options "$java_options" FilterMutectCalls
  -R "$reference" -V "$unfiltered_vcf" --ob-priors "$orientation_model"
  -O "$output_vcf")
[[ -n "$contamination_table" ]] && filter+=(--contamination-table "$contamination_table")

print_command() {
  printf '%q ' "$@"
  printf '\n'
}

if [[ $dry_run -eq 1 ]]; then
  printf '# Mutect2 肿瘤单样本调用\n'
  print_command "${mutect[@]}"
  printf '# 方向偏倚模型\n'
  print_command "${orientation[@]}"
  printf '# 候选过滤\n'
  print_command "${filter[@]}"
  exit 0
fi

command -v gatk >/dev/null 2>&1 || {
  printf '错误：未找到 gatk。请安装兼容版本或先使用 --dry-run。\n' >&2
  exit 127
}
mkdir -p "$(dirname "$output_vcf")"
"${mutect[@]}"
"${orientation[@]}"
"${filter[@]}"

#!/usr/bin/env bash
# AmpliconSuite-pipeline 1.3+ 参考流程；实际运行前先以 --help 核对参数。
set -euo pipefail

usage() {
  cat <<'EOF'
用法：run_ampliconsuite.sh [--dry-run] SAMPLE TUMOR_BAM REFERENCE POOLED_REFERENCE OUTDIR

环境变量：
  THREADS       线程数，默认 8
  SEED_CN       局灶扩增种子最低拷贝数，默认 4.5
  FOCAL_MAX_BP  局灶区段最大长度，默认 10000000

--dry-run 只输出命令，不创建目录或写文件。
EOF
}

print_command() {
  printf '%q ' "$@"
  printf '\n'
}

dry_run=false
if [[ ${1:-} == "--help" || ${1:-} == "-h" ]]; then
  usage
  exit 0
elif [[ ${1:-} == "--dry-run" ]]; then
  dry_run=true
  shift
fi

if [[ $# -ne 5 ]]; then
  usage >&2
  exit 2
fi

sample=$1
tumor_bam=$2
reference=$3
pooled_reference=$4
outdir=$5
threads=${THREADS:-8}
seed_cn=${SEED_CN:-4.5}
focal_max_bp=${FOCAL_MAX_BP:-10000000}
bam_name=$(basename "$tumor_bam" .bam)
cnv_dir="$outdir/cnvkit"
called_cns="$cnv_dir/${bam_name}.call.cns"
seed_bed="$outdir/focal_seeds.bed"

if [[ -d $outdir ]] && [[ -n $(find "$outdir" -mindepth 1 -maxdepth 1 -print -quit) ]]; then
  echo "错误：输出目录非空，拒绝覆盖：$outdir" >&2
  exit 2
fi

if $dry_run; then
  print_command mkdir -p "$cnv_dir"
  print_command cnvkit.py batch "$tumor_bam" --method wgs --reference "$pooled_reference" \
    --output-dir "$cnv_dir" --drop-low-coverage -p "$threads"
  print_command cnvkit.py call "$cnv_dir/${bam_name}.cns" -o "$called_cns"
  printf 'awk -v cn=%q -v maxbp=%q < %q > %q\n' "$seed_cn" "$focal_max_bp" "$called_cns" "$seed_bed"
  print_command AmpliconSuite-pipeline.py -s "$sample" -t "$threads" --bam "$tumor_bam" \
    --ref "$reference" --cnv_bed "$seed_bed" --run_AA --run_AC -o "$outdir"
  exit 0
fi

for input_file in "$tumor_bam" "$pooled_reference"; do
  if [[ ! -f $input_file ]]; then
    echo "错误：输入文件不存在：$input_file" >&2
    exit 2
  fi
done
for command_name in cnvkit.py AmpliconSuite-pipeline.py awk; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "错误：缺少命令：$command_name" >&2
    exit 2
  fi
done

mkdir -p "$cnv_dir"
cnvkit.py batch "$tumor_bam" --method wgs --reference "$pooled_reference" \
  --output-dir "$cnv_dir" --drop-low-coverage -p "$threads"
cnvkit.py call "$cnv_dir/${bam_name}.cns" -o "$called_cns"

awk -v cn="$seed_cn" -v maxbp="$focal_max_bp" \
  'NR>1 && $6 >= cn && ($3-$2) < maxbp {print $1"\t"$2"\t"$3"\t"$6}' \
  "$called_cns" > "$seed_bed"

if [[ ! -s $seed_bed ]]; then
  echo "未找到满足阈值的局灶扩增种子；请先复核CNV、纯度和阈值。" >&2
  exit 2
fi

AmpliconSuite-pipeline.py \
  -s "$sample" -t "$threads" --bam "$tumor_bam" --ref "$reference" \
  --cnv_bed "$seed_bed" --run_AA --run_AC -o "$outdir"

echo "完成。请联合断点图、循环文件和分类结果审核，不能仅凭拷贝数判定ecDNA。"

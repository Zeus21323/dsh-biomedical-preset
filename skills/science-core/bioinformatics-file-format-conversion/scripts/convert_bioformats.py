#!/usr/bin/env python3
"""Convert selected bioinformatics formats without overwriting source data."""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


FORMATS = {"fastq", "fasta", "sam", "bam", "cram", "biom", "tsv", "json", "wide-tsv", "long-tsv"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def command_version(tool: str) -> str:
    executable = shutil.which(tool)
    if executable is None:
        raise RuntimeError(f"required executable not found on PATH: {tool}")
    for flag in ("--version", "version"):
        result = subprocess.run([executable, flag], capture_output=True, text=True, check=False)
        if result.returncode == 0:
            return (result.stdout or result.stderr).strip().splitlines()[0]
    return executable


def run(command: list[str]) -> None:
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stderr}")


def open_text(path: Path):
    return gzip.open(path, "rt", encoding="utf-8", errors="replace") if path.name.endswith(".gz") else path.open("r", encoding="utf-8", errors="replace")


def count_records(path: Path, fmt: str) -> int | None:
    if fmt == "fastq":
        with open_text(path) as handle:
            lines = sum(1 for _ in handle)
        if lines % 4:
            raise RuntimeError("FASTQ line count is not divisible by four")
        return lines // 4
    if fmt == "fasta":
        with open_text(path) as handle:
            return sum(1 for line in handle if line.startswith(">"))
    if fmt in {"tsv", "wide-tsv", "long-tsv", "json"}:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            return max(sum(1 for _ in handle) - 1, 0)
    return None


def convert_wide_to_long(src: Path, dst: Path, id_column: str) -> None:
    with src.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        if not reader.fieldnames or id_column not in reader.fieldnames:
            raise RuntimeError(f"wide table is missing ID column: {id_column}")
        sample_columns = [name for name in reader.fieldnames if name != id_column]
        if not sample_columns:
            raise RuntimeError("wide table has no sample columns")
        with dst.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=["feature_id", "sample_id", "value"], delimiter="\t")
            writer.writeheader()
            for row in reader:
                for sample in sample_columns:
                    writer.writerow({"feature_id": row[id_column], "sample_id": sample, "value": row[sample]})


def convert_long_to_wide(src: Path, dst: Path, feature_column: str, sample_column: str, value_column: str) -> None:
    values: dict[str, dict[str, str]] = {}
    samples: list[str] = []
    with src.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source, delimiter="\t")
        required = {feature_column, sample_column, value_column}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise RuntimeError(f"long table is missing columns: {sorted(required)}")
        for row in reader:
            feature, sample = row[feature_column], row[sample_column]
            if sample not in samples:
                samples.append(sample)
            if sample in values.setdefault(feature, {}):
                raise RuntimeError(f"duplicate feature/sample pair: {feature}/{sample}")
            values[feature][sample] = row[value_column]
    with dst.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=[feature_column, *samples], delimiter="\t")
        writer.writeheader()
        for feature, row_values in values.items():
            writer.writerow({feature_column: feature, **row_values})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--input-format", required=True, choices=sorted(FORMATS))
    parser.add_argument("--output-format", required=True, choices=sorted(FORMATS))
    parser.add_argument("--reference", type=Path, help="Required for CRAM input or output")
    parser.add_argument("--r2", type=Path, help="Second FASTQ output for paired BAM/CRAM conversion")
    parser.add_argument("--threads", type=int, default=1)
    parser.add_argument("--id-column", default="feature_id")
    parser.add_argument("--sample-column", default="sample_id")
    parser.add_argument("--value-column", default="value")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input file does not exist: {args.input}")
    if args.output.exists() and not args.overwrite:
        parser.error(f"output exists; use --overwrite only after checking the target: {args.output}")
    if args.r2 and args.r2.exists() and not args.overwrite:
        parser.error(f"R2 output exists: {args.r2}")
    if args.threads < 1:
        parser.error("--threads must be positive")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    tools: dict[str, str] = {}
    command_description = ""
    pair = (args.input_format, args.output_format)

    if pair == ("fastq", "fasta"):
        tools["seqkit"] = command_version("seqkit")
        command = ["seqkit", "fq2fa", str(args.input), "-o", str(args.output)]
        run(command)
        command_description = " ".join(command)
    elif args.input_format in {"sam", "bam", "cram"} and args.output_format in {"sam", "bam", "cram"}:
        tools["samtools"] = command_version("samtools")
        if "cram" in pair and args.reference is None:
            parser.error("--reference is required for reproducible CRAM conversion")
        flag = {"sam": "-h", "bam": "-b", "cram": "-C"}[args.output_format]
        command = ["samtools", "view", flag, "-@", str(args.threads), "-o", str(args.output)]
        if args.reference:
            if not args.reference.is_file():
                parser.error(f"reference does not exist: {args.reference}")
            command.extend(["-T", str(args.reference)])
        command.append(str(args.input))
        run(command)
        command_description = " ".join(command)
    elif args.input_format in {"bam", "cram"} and args.output_format == "fastq":
        tools["samtools"] = command_version("samtools")
        if args.input_format == "cram" and args.reference is None:
            parser.error("--reference is required for CRAM input")
        command = ["samtools", "fastq", "-@", str(args.threads), "-F", "0x900", "-n"]
        if args.reference:
            command.extend(["--reference", str(args.reference)])
        if args.r2:
            command.extend(["-1", str(args.output), "-2", str(args.r2), "-0", "/dev/null", "-s", "/dev/null"])
        else:
            command.extend(["-0", str(args.output)])
        command.append(str(args.input))
        run(command)
        command_description = " ".join(command)
    elif args.input_format == "biom" and args.output_format in {"tsv", "json"}:
        tools["biom"] = command_version("biom")
        target_flag = "--to-tsv" if args.output_format == "tsv" else "--to-json"
        command = ["biom", "convert", "-i", str(args.input), "-o", str(args.output), target_flag]
        run(command)
        command_description = " ".join(command)
    elif args.input_format == "tsv" and args.output_format == "biom":
        tools["biom"] = command_version("biom")
        command = ["biom", "convert", "-i", str(args.input), "-o", str(args.output), "--table-type", "OTU table", "--to-hdf5"]
        run(command)
        command_description = " ".join(command)
    elif pair == ("wide-tsv", "long-tsv"):
        convert_wide_to_long(args.input, args.output, args.id_column)
        command_description = f"wide-to-long id_column={args.id_column}"
    elif pair == ("long-tsv", "wide-tsv"):
        convert_long_to_wide(args.input, args.output, args.id_column, args.sample_column, args.value_column)
        command_description = f"long-to-wide feature={args.id_column} sample={args.sample_column} value={args.value_column}"
    else:
        parser.error(f"unsupported conversion: {args.input_format} -> {args.output_format}")

    outputs = [args.output, *([args.r2] if args.r2 else [])]
    metadata = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "input": {"path": str(args.input.resolve()), "format": args.input_format, "sha256": sha256(args.input), "size": args.input.stat().st_size, "records": count_records(args.input, args.input_format)},
        "outputs": [
            {"path": str(path.resolve()), "format": args.output_format, "sha256": sha256(path), "size": path.stat().st_size, "records": count_records(path, args.output_format)}
            for path in outputs
        ],
        "reference": {"path": str(args.reference.resolve()), "sha256": sha256(args.reference)} if args.reference else None,
        "command": command_description,
        "tools": tools,
        "python": platform.python_version(),
    }
    log_path = args.output.with_name(args.output.name + ".conversion.json")
    log_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

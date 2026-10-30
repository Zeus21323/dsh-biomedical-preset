#!/usr/bin/env python3
"""Validate inputs, run an installed STRiker checkout, and record provenance."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXPECTED_COLUMNS = [
    "gene",
    "chr",
    "start",
    "end",
    "known_motif",
    "pathogenic_expansion_number",
]
DNA_ALPHABET = set("ACGTN")
CONFIG_NAMES = {
    "REFERENCE_MINIMUM_MOTIF_LENGTH",
    "REFERENCE_MAXIMUM_MOTIF_LENGTH",
    "REFERENCE_CONSECUTIVE_THRESHOLD",
    "REFERENCE_LEFT_TRIM",
    "REFERENCE_RIGHT_TRIM",
    "MINIMUM_MOTIF_LENGTH",
    "MAXIMUM_MOTIF_LENGTH",
    "CONSECUTIVE_THRESHOLD",
    "MINIMUM_MOTIF_COVERAGE",
    "COVERAGE_THRESHOLD",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_config(path: Path) -> dict[str, int | float | str]:
    if not path.is_file():
        raise ValueError(f"STRiker config not found: {path}")
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, int | float | str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value_node = node.value
        for target in targets:
            if not isinstance(target, ast.Name) or target.id not in CONFIG_NAMES:
                continue
            try:
                value = ast.literal_eval(value_node)
            except (ValueError, TypeError):
                continue
            if isinstance(value, (int, float, str)):
                values[target.id] = value
    return values


def read_fai(reference: Path) -> dict[str, int]:
    index = Path(str(reference) + ".fai")
    if not reference.is_file():
        raise ValueError(f"reference FASTA not found: {reference}")
    if not index.is_file():
        raise ValueError(f"reference FASTA index not found: {index}")
    contigs: dict[str, int] = {}
    with index.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            fields = raw.rstrip("\n").split("\t")
            if len(fields) < 2:
                raise ValueError(f"malformed FAI row {line_number}: {index}")
            name = fields[0]
            if name in contigs:
                raise ValueError(f"duplicate reference contig in FAI: {name}")
            contigs[name] = int(fields[1])
    if not contigs:
        raise ValueError(f"empty reference FASTA index: {index}")
    return contigs


def bam_index_path(bam: Path) -> Path | None:
    candidates = [Path(str(bam) + ".bai"), bam.with_suffix(".bai")]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def parse_loci(
    path: Path,
    coordinate_system: str,
    reference_contigs: dict[str, int],
    left_flank: int,
    right_flank: int,
) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"loci CSV not found: {path}")
    raw_lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not raw_lines:
        raise ValueError(f"empty loci CSV: {path}")
    if any('"' in line for line in raw_lines):
        raise ValueError("quoted CSV fields are unsupported by STRiker")
    rows = list(csv.reader(raw_lines))
    header = [field.strip().lower() for field in rows[0]]
    if header != EXPECTED_COLUMNS:
        raise ValueError(
            "loci header/order must be: " + ",".join(EXPECTED_COLUMNS)
        )

    parsed: list[dict[str, Any]] = []
    genes: set[str] = set()
    for line_number, row in enumerate(rows[1:], 2):
        if not row or all(not field.strip() for field in row):
            raise ValueError(f"blank loci row at line {line_number}")
        if len(row) != len(EXPECTED_COLUMNS):
            raise ValueError(f"loci row {line_number} has {len(row)} fields; expected 6")
        gene, chrom, raw_start, raw_end, raw_motif, raw_expansion = [
            field.strip() for field in row
        ]
        if not gene or gene in genes:
            raise ValueError(f"missing or duplicate gene at line {line_number}: {gene!r}")
        genes.add(gene)
        if chrom not in reference_contigs:
            raise ValueError(f"locus contig absent from reference at line {line_number}: {chrom}")
        try:
            start = int(raw_start)
            end = int(raw_end)
            expansion = int(raw_expansion)
        except ValueError as exc:
            raise ValueError(f"non-integer coordinate/threshold at line {line_number}") from exc
        if coordinate_system == "1-based-inclusive":
            start -= 1
        if start < 0 or end <= start:
            raise ValueError(f"invalid interval at line {line_number}: {start}-{end}")
        if expansion < 0:
            raise ValueError(f"negative expansion threshold at line {line_number}")
        motifs = raw_motif.upper().split("/")
        if any(not motif or set(motif) - DNA_ALPHABET for motif in motifs):
            raise ValueError(f"invalid known_motif at line {line_number}: {raw_motif!r}")
        contig_length = reference_contigs[chrom]
        if start - left_flank < 0 or end + right_flank > contig_length:
            raise ValueError(
                f"STRiker reference window leaves contig at line {line_number}: "
                f"{chrom}:{start}-{end}, flanks={left_flank}/{right_flank}"
            )
        parsed.append(
            {
                "gene": gene,
                "chr": chrom,
                "start": start,
                "end": end,
                "known_motif": "/".join(motifs),
                "pathogenic_expansion_number": expansion,
            }
        )
    if not parsed:
        raise ValueError("loci CSV has no data rows")
    return parsed


def write_loci(path: Path, loci: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(loci)


def inspect_bam(
    bam: Path,
    reference_contigs: dict[str, int],
    loci: list[dict[str, Any]],
    left_flank: int,
    right_flank: int,
) -> tuple[dict[str, Any], list[str]]:
    if not bam.is_file():
        raise ValueError(f"BAM not found: {bam}")
    if bam.suffix.lower() != ".bam":
        raise ValueError("STRiker runner currently accepts indexed BAM input only")
    index = bam_index_path(bam)
    if index is None:
        raise ValueError(f"BAM index not found for: {bam}")
    try:
        import pysam  # type: ignore
    except ImportError as exc:
        raise ValueError("pysam is required; run inside the STRiker environment") from exc

    summaries: list[dict[str, Any]] = []
    warnings: list[str] = []
    with pysam.AlignmentFile(str(bam), "rb") as handle:
        header = handle.header.to_dict()
        sort_order = header.get("HD", {}).get("SO")
        if sort_order != "coordinate":
            warnings.append(f"BAM header sort order is {sort_order!r}, not 'coordinate'")
        bam_contigs = dict(zip(handle.references, handle.lengths))
        for locus in loci:
            chrom = locus["chr"]
            if chrom not in bam_contigs:
                raise ValueError(f"locus contig absent from BAM: {chrom}")
            if bam_contigs[chrom] != reference_contigs[chrom]:
                raise ValueError(
                    f"BAM/reference contig length mismatch for {chrom}: "
                    f"{bam_contigs[chrom]} != {reference_contigs[chrom]}"
                )
            start, end = locus["start"], locus["end"]
            window_start = start - left_flank
            window_end = end + right_flank
            target_spanning = 0
            window_spanning = 0
            mapqs: list[int] = []
            forward = 0
            reverse = 0
            for read in handle.fetch(chrom, window_start, window_end):
                if read.is_unmapped or read.is_secondary or read.is_supplementary:
                    continue
                if read.reference_start <= start and read.reference_end >= end:
                    target_spanning += 1
                    mapqs.append(read.mapping_quality)
                    if read.is_reverse:
                        reverse += 1
                    else:
                        forward += 1
                if read.reference_start < window_start and read.reference_end > window_end:
                    window_spanning += 1
            if target_spanning == 0:
                warnings.append(f"{locus['gene']}: no primary read spans the target interval")
            summaries.append(
                {
                    "gene": locus["gene"],
                    "target_spanning_reads": target_spanning,
                    "window_spanning_reads": window_spanning,
                    "mapping_quality_min": min(mapqs) if mapqs else None,
                    "mapping_quality_max": max(mapqs) if mapqs else None,
                    "forward_reads": forward,
                    "reverse_reads": reverse,
                }
            )
    return {"index": str(index.resolve()), "loci": summaries}, warnings


def expected_outputs(output_dir: Path, bam: Path) -> list[Path]:
    sample = bam.name.removesuffix(".bam")
    return [
        output_dir / "motif_results" / f"{sample}_motif_ref_denovo.xlsx",
        output_dir / "motif_results" / f"{sample}_coverage.txt",
        output_dir / "gene_panel_output" / f"{bam.name}_gene_panel_output.pdf",
    ]


def run_self_test() -> None:
    with tempfile.TemporaryDirectory(prefix="striker-runner-test-") as raw_tmp:
        tmp = Path(raw_tmp)
        reference = tmp / "ref.fa"
        reference.write_text(">chr1\n" + "A" * 2000 + "\n", encoding="utf-8")
        Path(str(reference) + ".fai").write_text(
            "chr1\t2000\t6\t2000\t2001\n", encoding="utf-8"
        )
        loci_path = tmp / "loci.csv"
        loci_path.write_text(
            "gene,chr,start,end,known_motif,pathogenic_expansion_number\n"
            "TEST,chr1,701,800,CAG,40\n",
            encoding="utf-8",
        )
        loci = parse_loci(loci_path, "1-based-inclusive", read_fai(reference), 500, 500)
        assert loci[0]["start"] == 700
        assert loci[0]["end"] == 800
        config = tmp / "config.py"
        config.write_text(
            "REFERENCE_LEFT_TRIM = 500\nCOVERAGE_THRESHOLD = 30\nIGNORED = object()\n",
            encoding="utf-8",
        )
        assert read_config(config) == {
            "REFERENCE_LEFT_TRIM": 500,
            "COVERAGE_THRESHOLD": 30,
        }
    print("ok: STRiker runner self-test")


def require_path(parser: argparse.ArgumentParser, value: Path | None, option: str) -> Path:
    if value is None:
        parser.error(f"{option} is required")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--striker-script", type=Path)
    parser.add_argument("--loci", type=Path)
    parser.add_argument("--coordinate-system", choices=("0-based-half-open", "1-based-inclusive"))
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--bam", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--processes", type=int)
    parser.add_argument("--python-executable", default=sys.executable)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--hash-large-inputs", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    striker_script = require_path(parser, args.striker_script, "--striker-script").resolve()
    loci_path = require_path(parser, args.loci, "--loci").resolve()
    reference = require_path(parser, args.reference, "--reference").resolve()
    bam = require_path(parser, args.bam, "--bam").resolve()
    output_dir = require_path(parser, args.output_dir, "--output-dir").resolve()
    if args.coordinate_system is None:
        parser.error("--coordinate-system is required; coordinates are never guessed")
    if args.processes is not None and args.processes < 1:
        parser.error("--processes must be positive")
    if not striker_script.is_file():
        parser.error(f"STRiker script not found: {striker_script}")
    if output_dir.exists() and any(output_dir.iterdir()):
        parser.error(f"output directory must be new or empty: {output_dir}")

    config_path = striker_script.parent / "config" / "__init__.py"
    try:
        config = read_config(config_path)
        reference_contigs = read_fai(reference)
        left_flank = int(config.get("REFERENCE_LEFT_TRIM", 500))
        right_flank = int(config.get("REFERENCE_RIGHT_TRIM", 500))
        loci = parse_loci(
            loci_path,
            args.coordinate_system,
            reference_contigs,
            left_flank,
            right_flank,
        )
        bam_qc, warnings = inspect_bam(
            bam, reference_contigs, loci, left_flank, right_flank
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    output_dir.mkdir(parents=True, exist_ok=True)
    normalized_loci = output_dir / "loci.striker.0-based-half-open.csv"
    write_loci(normalized_loci, loci)

    version_result = subprocess.run(
        [args.python_executable, str(striker_script), "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    version = (version_result.stdout or version_result.stderr).strip()
    if version_result.returncode != 0:
        parser.error(f"unable to start STRiker environment: {version}")

    command = [
        args.python_executable,
        str(striker_script),
        str(normalized_loci),
        str(reference),
        str(bam),
        "-o",
        str(output_dir),
    ]
    if args.processes is not None:
        command.extend(["-p", str(args.processes)])

    manifest_path = output_dir / "striker_run.json"
    log_path = output_dir / "striker.log"
    expected = expected_outputs(output_dir, bam)
    manifest: dict[str, Any] = {
        "status": "validated" if args.dry_run else "running",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tool": {"version": version, "script": str(striker_script)},
        "config": {
            "path": str(config_path.resolve()),
            "sha256": sha256(config_path),
            "values": config,
        },
        "inputs": {
            "loci": {
                "path": str(loci_path),
                "sha256": sha256(loci_path),
                "coordinate_system": args.coordinate_system,
                "normalized_path": str(normalized_loci),
            },
            "reference": {"path": str(reference), "size": reference.stat().st_size},
            "bam": {"path": str(bam), "size": bam.stat().st_size},
        },
        "parameters": {"processes": args.processes},
        "bam_qc": bam_qc,
        "warnings": warnings,
        "command": command,
        "expected_outputs": [str(path) for path in expected],
        "license_notice": "STRiker upstream declares CC BY-NC-SA 4.0; verify authorization before use.",
    }
    if args.hash_large_inputs:
        manifest["inputs"]["reference"]["sha256"] = sha256(reference)
        manifest["inputs"]["bam"]["sha256"] = sha256(bam)

    if args.dry_run:
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(shlex.join(command))
        print(f"validated: {manifest_path}")
        return 0

    started = datetime.now(timezone.utc).isoformat()
    with log_path.open("w", encoding="utf-8") as log_handle:
        process = subprocess.Popen(
            command,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log_handle.write(line)
        returncode = process.wait()

    missing = [str(path) for path in expected if not path.is_file() or path.stat().st_size == 0]
    if returncode == 0 and not missing:
        status = "completed"
    elif returncode == 0:
        status = "incomplete"
    else:
        status = "failed"
    manifest.update(
        {
            "status": status,
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "returncode": returncode,
            "missing_outputs": missing,
            "log": str(log_path),
        }
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    if returncode != 0:
        return returncode
    if missing:
        print("STRiker returned success but expected outputs are missing:", file=sys.stderr)
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        return 3
    print(f"completed: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

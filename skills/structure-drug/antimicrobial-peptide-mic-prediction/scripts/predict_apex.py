#!/usr/bin/env python3
"""Predict pathogen-specific peptide MICs with a trusted local APEX ensemble."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_PATHOGENS = [
    "A. baumannii ATCC 19606",
    "E. coli ATCC 11775",
    "E. coli AIC221",
    "E. coli AIC222",
    "K. pneumoniae ATCC 13883",
    "P. aeruginosa PA01",
    "P. aeruginosa PA14",
    "S. aureus ATCC 12600",
    "S. aureus (ATCC BAA-1556) - MRSA",
    "vancomycin-resistant E. faecalis ATCC 700802",
    "vancomycin-resistant E. faecium ATCC 700221",
]
CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apex-repo", required=True, type=Path)
    parser.add_argument("--models-dir", required=True, type=Path)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    parser.add_argument("--batch-size", type=int, default=8192)
    parser.add_argument("--pathogens-json", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"input FASTA not found: {args.input}")
    if not args.apex_repo.is_dir() or not args.models_dir.is_dir():
        parser.error("--apex-repo and --models-dir must exist")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")

    try:
        import numpy as np
        import pandas as pd
        import torch
        from Bio import SeqIO
    except ImportError as exc:
        parser.error(f"missing APEX runtime dependency: {exc}")

    if args.device == "cuda" and not torch.cuda.is_available():
        parser.error("CUDA was requested but is not available")
    device = "cuda" if args.device == "cuda" or (args.device == "auto" and torch.cuda.is_available()) else "cpu"

    sys.path.insert(0, str(args.apex_repo.resolve()))
    try:
        from utils import make_vocab, onehot_encoding
    except ImportError as exc:
        parser.error(f"cannot import APEX utilities from {args.apex_repo}: {exc}")

    ids: list[str] = []
    sequences: list[str] = []
    seen_ids: set[str] = set()
    for record in SeqIO.parse(str(args.input), "fasta"):
        identifier = record.id
        sequence = str(record.seq).upper()
        if identifier in seen_ids:
            parser.error(f"duplicate peptide ID: {identifier}")
        if not sequence or len(sequence) > 50:
            parser.error(f"peptide {identifier} must contain 1-50 amino acids")
        invalid = set(sequence) - CANONICAL_AA
        if invalid:
            parser.error(f"peptide {identifier} contains unsupported residues: {sorted(invalid)}")
        seen_ids.add(identifier)
        ids.append(identifier)
        sequences.append(sequence)
    if not sequences:
        parser.error("no peptide records found")

    pathogens = DEFAULT_PATHOGENS
    if args.pathogens_json:
        pathogens = json.loads(args.pathogens_json.read_text(encoding="utf-8"))
        if not isinstance(pathogens, list) or not all(isinstance(value, str) for value in pathogens):
            parser.error("--pathogens-json must contain a JSON string array")

    model_files = sorted(Path(path) for path in glob.glob(str(args.models_dir / "APEX_*")) if Path(path).is_file())
    if not model_files:
        parser.error(f"no APEX_* model files found in {args.models_dir}")

    word2idx, _ = make_vocab()
    sequence_array = np.asarray(sequences)
    prediction_sum = None
    started = datetime.now(timezone.utc).isoformat()
    for model_path in model_files:
        model = torch.load(model_path, map_location=device)
        model = model.to(device).eval()
        batches = []
        for start in range(0, len(sequence_array), args.batch_size):
            batch = sequence_array[start:start + args.batch_size]
            encoded = onehot_encoding(batch, 52, word2idx)
            with torch.no_grad():
                batches.append(model(torch.LongTensor(encoded).to(device)).cpu().numpy())
        prediction = 10 ** (6 - np.vstack(batches))
        prediction_sum = prediction if prediction_sum is None else prediction_sum + prediction

    predictions = prediction_sum / len(model_files)
    if predictions.shape[1] != len(pathogens):
        parser.error(f"model output has {predictions.shape[1]} columns but pathogen list has {len(pathogens)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = pd.DataFrame(predictions, columns=pathogens)
    result.insert(0, "sequence", sequences)
    result.insert(0, "peptide_id", ids)
    result.to_csv(args.output, index=False)

    metadata_path = args.metadata or args.output.with_name(args.output.name + ".apex_run.json")
    metadata = {
        "status": "completed",
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "input": {"path": str(args.input.resolve()), "sha256": sha256(args.input), "records": len(sequences)},
        "output": {"path": str(args.output.resolve()), "sha256": sha256(args.output), "unit": "uM"},
        "models": [{"path": str(path.resolve()), "sha256": sha256(path)} for path in model_files],
        "parameters": {"device": device, "batch_size": args.batch_size, "max_peptide_length": 50, "ensemble_models": len(model_files)},
        "pathogens": pathogens,
        "environment": {"python": platform.python_version(), "torch": torch.__version__, "numpy": np.__version__, "pandas": pd.__version__},
    }
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

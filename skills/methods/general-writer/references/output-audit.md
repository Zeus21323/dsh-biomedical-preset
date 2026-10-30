# Output Audit

Run before delivering a full LaTeX manuscript:

```bash
python3 scripts/validate_claim_evidence_map.py claim_evidence_map.json --project-root .

python3 scripts/audit_manuscript.py \
  --tex manuscript/mainbody.tex \
  --bib manuscript/references.bib \
  --evidence-map claim_evidence_map.json \
  --manuscript-plan manuscript_plan.json \
  --approval-receipt manuscript_approval.json \
  --project-root . \
  --report manuscript/paper_audit.json
```

Exit status `0` means implemented checks passed, `1` means delivery-blocking findings remain, and `2` means an input could not be read or parsed.

## Mechanical Gates

The scripts check:

- study type, claim-map structure, stable unique IDs, evidence type/status, and source-file existence;
- current-conversation manuscript approval, approved-plan status, scope, method, and exact plan SHA-256;
- minimum primary evidence appropriate to the study type;
- nonempty evidence locators, bounded wording, and caveats;
- citation keys against the BibTeX library;
- manually rendered author-year citations and hand-written bibliography blocks;
- duplicate and unresolved LaTeX labels/references;
- relative image paths;
- unresolved authoring markers;
- abstract, introduction, body evidence/results, limitations, and conclusion section families.

## Judgment Gates

Review manually:

- every number, comparison, quotation, theme, proposition, and novelty statement against its locator;
- fair comparison scope, denominators, units, transformations, uncertainty, and missing data;
- whether citations support the exact sentence;
- whether causal, generalization, mechanism, SOTA, clinical, policy, or theoretical claims fit the design;
- whether negative, null, mixed, failed, and contradictory evidence is represented;
- whether limitations, ethics, validity, anonymity, and reproducibility are proportional to the study;
- whether final PDF/DOCX rendering is visually sound.

Treat errors as blockers. The JSON report records checks; it does not prove that scientific claims are true.

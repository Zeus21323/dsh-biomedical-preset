# Evidence And Claims

Use this reference to inventory sources and build `claim_evidence_map.json`.

## Evidence Priority

Prefer, when applicable:

1. Machine-readable primary results, transcripts, derivations, proofs, and source data.
2. Reproducible scripts plus identified input and output versions.
3. Publication-ready tables, figures, models, or coded qualitative material.
4. Protocols, laboratory or field notes, method specifications, and design documents.
5. Literature records and verified source texts.
6. Prose summaries and screenshots.

Report conflicts instead of selecting the most favorable value. Preserve raw sources and write normalized derivatives elsewhere.

## Source Inventory

Record for each item:

- exact path, format, version, and status;
- role: literature, data, method, analysis, result, proof, transcript, table, figure, or venue constraint;
- scope: population, dataset, corpus, time, geography, task, workload, treatment, assumptions, or theoretical domain;
- units, sample/run/participant count, aggregation, uncertainty, coding, and transformations when applicable;
- whether it is canonical, derived, superseded, incomplete, inconsistent, or ambiguous.
- one stable BibTeX key for each citable literature record; do not store a rendered author-year string as the identifier.

## Claim-Evidence Map

Use this shape:

```json
{
  "paper_goal": "Explain or evaluate ...",
  "study_type": "experimental",
  "discipline_profiles": ["generic"],
  "research_questions": [
    {
      "id": "RQ1",
      "question": "How does ...?",
      "answer_scope": "Population or assumptions under which the answer holds",
      "claims": [
        {
          "id": "C1",
          "text": "Bounded claim text",
          "evidence_type": "data",
          "verification_status": "verified",
          "source_files": ["results/main.csv"],
          "locator": "rows A-B; column outcome; model 3",
          "statistics": ["estimate=...", "95% CI=..."],
          "allowed_wording": "is associated with ... in the analyzed sample",
          "prohibited_wording": ["causes", "proves"],
          "caveats": ["observational design"],
          "section": "sec:results",
          "table_or_figure": "tab:main_results",
          "citation_keys": ["verifiedSource2026"]
        }
      ]
    }
  ]
}
```

For literature-supported claims, populate `citation_keys` from verified records before prose drafting. The manuscript writer must copy these keys into LaTeX citation commands at sentence-generation time.

Use these evidence types:

```text
data | analysis | experiment | qualitative | literature | artifact | theory | mixed
```

Use `verified`, `limited`, `inconsistent`, or `unsupported` for `verification_status`. An `unsupported` claim blocks polished delivery. Keep a `limited` or `inconsistent` claim only with calibrated wording and explicit caveats.

## Study-Type Minimum Evidence

- Experimental, computational, observational, empirical, qualitative, mixed-methods, methods, and case-study papers require at least one claim grounded in primary study evidence: `data`, `analysis`, `experiment`, `qualitative`, `artifact`, or `mixed`.
- Review papers may use literature evidence exclusively, but must identify the corpus, search/selection method, and synthesis scope.
- Theoretical papers require `theory` or `artifact` evidence containing assumptions, derivations, proofs, counterexamples, or formal constructions.
- Literature-only evidence can establish context or prior work; it cannot establish a new measured result.

## Wording Calibration

- Replace `better` with the exact improved outcome and scope.
- Replace `proves` with `supports`, `shows under the stated assumptions`, or another design-appropriate verb.
- Replace `causes` with `is associated with` unless identification supports causality.
- Distinguish `no statistically significant difference` from equivalence.
- Distinguish percent change, percentage-point change, ratio, odds ratio, and standardized effect.
- State whether an explanation was directly tested or is an interpretation.

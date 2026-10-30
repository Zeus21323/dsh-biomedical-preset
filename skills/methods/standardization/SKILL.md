---
name: standardization
description: Mandatory entry-point router for standardized browser-based research workflows. Use when the user asks for browser research, source verification, literature search, multi-source synthesis, biomedical or medical research, life-science research, economics research, finance research, engineering research, computer science research, software engineering research, Chinese academic literature, CNKI search, PubMed search, Google Scholar search, arXiv search, IEEE/ACM search, or website investigation. First decide whether the request is biomedical/life-science, economics/finance, or engineering/computer-science, then strictly read and obey the matching SKILL.md under references1, references2, or references3 before searching or answering.
---

# Standardization Router

Use this file as the entry point. Do not treat it as the full research workflow.

Before searching, browsing, downloading, or answering, first decide whether the user's request belongs to the biomedical/life-science domain, the economics/finance domain, or the engineering/computer-science domain. Then read the matching reference skill and obey its rules. The reference skill is mandatory, not optional.

## Routing

1. Biomedical, medical, clinical, pharmaceutical, genetics, biology, public-health, or life-science requests:
   - Read `/home/ubuntu/speedclaw_skillsurvey/speedskills/research-skills-local/Standardization/references1/SKILL.md`.
   - Strictly follow its PubMed-first workflow, literature download rules, source-priority rules, and browser-use constraints.
2. Economics, finance, political economy, industrial organization, macroeconomics, microeconomics, econometrics, development economics, labor economics, public finance, international trade, Chinese economic policy, or Chinese economics literature requests:
   - Read `/home/ubuntu/speedclaw_skillsurvey/speedskills/research-skills-local/Standardization/references2/SKILL.md`.
   - Strictly follow its CNKI-first workflow, high-priority Google Scholar/arXiv supplementary search rules, Renmin University of China Economics A/B journal priority, and high-citation/top-journal screening rules.
3. Engineering, computer science, software engineering, artificial intelligence, machine learning, data engineering, cybersecurity, networking, systems, databases, programming languages, human-computer interaction, robotics, control, electronics, communications, or applied engineering technology requests:
   - Read `/home/ubuntu/speedclaw_skillsurvey/speedskills/research-skills-local/Standardization/references3/SKILL.md`.
   - Strictly follow its IEEE/ACM/Google Scholar/arXiv/DBLP workflow, venue-priority rules, standard/specification/source-code verification rules, and reproducibility screening rules.
4. Mixed biomedical, economics, and engineering requests:
   - Read every relevant reference skill.
   - Apply the source priority for each subtopic: PubMed first for biomedical claims; CNKI first for Chinese economics claims; IEEE/ACM/Google Scholar/arXiv/DBLP and standards/source repositories for engineering claims.
5. Other browser-based research requests:
   - Use the general browser lifecycle rules from `browser_use` or the remote-browser skill.
   - Prefer authoritative primary sources, multi-source verification, concise synthesis, and auditable source metadata.

## Common Browser Rules

Before browser work, read and follow the relevant browser-use rules from `browser_use` or the remote-browser skill.

When `mcp_remote_browser_*` tools are available:

1. List devices first.
2. Create a task-specific session.
3. Check existing tabs before opening duplicates.
4. Prefer structured element refs over selectors or coordinates.
5. Request user approval for sensitive actions.
6. Finalize tabs before ending browser work.

## Output Standard

Always state which route was used:

- `references1`: biomedical/PubMed-first route.
- `references2`: economics/CNKI-first route.
- `references3`: engineering/computer-science route.
- `mixed`: mixed route using two or more reference skills.
- `general`: other research route.

Include source links and enough metadata to audit the answer. If the expected priority source was not used, explain why.

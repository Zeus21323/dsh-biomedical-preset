# PRD Approval Interaction Contract

Apply this contract at both the analysis-PRD gate and manuscript-PRD gate.

## Hard tool rule

On SpeedClaw, `ask_user` is a built-in, interactive, non-deferred tool. Call it
whenever this contract requires a decision. Do not substitute an ordinary chat
question, a request to type “同意”, or a generic “please confirm”. On other
hosts, use `request_user_input` first when available, then structured
`ask_user`. Use one dedicated question with exactly these three choices:

1. `批准并继续` (recommended when the displayed PRD is correct): approve the
   displayed artifact and allow the next phase.
2. `需要修改`: keep the gate closed and collect the requested changes.
3. `暂不批准`: keep the gate pending and stop.

For the analysis gate use:

```text
header: 实验 PRD
question: 是否批准刚才展示的实验分析 PRD，并按该方案开始运行？
```

For the manuscript gate use:

```text
header: 论文 PRD
question: 是否批准刚才展示的逐章论文 PRD，并按该方案进入图表整理、文献调研和写作？
```

Put the recommended approval choice first. The ask-user response is the user's
explicit decision; never ask for an additional typed confirmation.

For SpeedClaw, set `allow_other: false` and submit the three choices through
the `ask_user` JSON schema. The direct-chat fallback is invalid while the
SpeedClaw `ask_user` tool is present.

## No-tool fallback

Only when no ask-user tool is available, print the same question and all three
numbered choices directly in chat, then stop. Do not reduce the fallback to two
choices or ask an open-ended confirmation question. Record
`approval_source: direct_chat` after the user replies.

## Decision handling

- `批准并继续`: write the current-conversation approval receipt with exact
  returned text and matching artifact hashes, validate it, then continue.
- `需要修改`: mark the PRD `revised`, collect the requested changes, present the
  full revised summary, and invoke this contract again.
- `暂不批准`: keep the PRD `pending` and stop all downstream work.

Never create an approval receipt from silence, a timeout, an old approval, an
existing output file, or an inferred preference.

## Deterministic analysis approval receipt

After the analysis-gate answer is `批准并继续`, never construct the receipt or
hashes manually. Run:

```bash
python3 /home/ubuntu/speedclaw_skillsurvey/Bioinformatics_writer/scripts/create_analysis_approval.py \
  --project-root . \
  --analysis-prd analysis_prd.md \
  --analysis-inventory analysis_inventory.json \
  --approval-receipt analysis_approval.json \
  --approval-source ask_user \
  --user-approval-text "批准并继续"
```

Pass the exact returned answer as `--user-approval-text`. Use
`--approval-source direct_chat` only for the no-tool fallback. The creator is
the sole writer of `analysis_approval.json`; it conforms to
`templates/analysis_approval.schema.json` and writes exactly:

```json
{
  "approval_choice": "approved",
  "approval_source": "ask_user",
  "approved_in_current_conversation": true,
  "user_approval_text": "批准并继续",
  "approved_prd_sha256": "<64 lowercase hex characters>",
  "approved_inventory_sha256": "<64 lowercase hex characters>"
}
```

The creator accepts plain, backtick-wrapped, bold, list-item, table, and Chinese
status forms, then normalizes non-approved status lines before hashing. Never
edit the PRD or inventory after receipt creation. If either artifact changes,
mark the PRD `revised`, obtain approval again, and rerun the creator. Use
`scripts/validate_analysis_approval.py` only for a read-only recheck of an
existing receipt.

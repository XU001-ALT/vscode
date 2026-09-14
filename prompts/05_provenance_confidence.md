# Prompt 05 - Provenance And Confidence Extraction

读取当前 paper 的 context_blocks，为前四个 stage 的候选值补全或审计 provenance/confidence。不要新增没有证据的数据值。

## Fields

- page
- table/figure
- caption
- evidence_text
- unit
- is_calculated
- is_from_figure
- confidence
- conflict_flag
- qc_note

## Output JSON Shape

```json
{
  "paper_id": "<paper_id>",
  "stage": "provenance_confidence",
  "provenance_records": [
    {
      "target_stage": "metadata|catalyst|reaction_conditions|performance",
      "target_field": null,
      "target_record_id": null,
      "page": null,
      "table_or_figure": null,
      "caption": null,
      "evidence_text": null,
      "unit": null,
      "is_calculated": false,
      "is_from_figure": false,
      "confidence": 0,
      "conflict_flag": false,
      "qc_note": null
    }
  ]
}
```

## Stage-Specific Rules

- evidence_text 保持短片段，通常 10-40 个词；不要粘贴整段。
- 如果同一字段在正文和表格冲突，保留两条 provenance_records，并标记 conflict_flag=true。
- 如果值来自图读数，必须写 is_from_figure=true，并说明 figure/caption。
- 如果值由单位换算或差值计算得出，必须写 is_calculated=true，并在 qc_note 说明公式。


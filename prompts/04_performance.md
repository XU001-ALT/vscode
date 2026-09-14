# Prompt 04 - Performance Data Extraction

读取当前 paper 的 context_blocks，只抽取性能数据。每组 catalyst + condition + metric + product range 生成一条 performance record。

## Fields

- conversion
- selectivity
- yield
- STY
- C5+
- C8-C16
- CH4
- CO
- CO2
- liquid hydrocarbon
- jet-fuel-range hydrocarbons
- olefin/paraffin ratio
- productivity
- deactivation/time-on-stream performance

## Output JSON Shape

```json
{
  "paper_id": "<paper_id>",
  "stage": "performance",
  "performance_records": [
    {
      "performance_id": "<paper_id>:perf001",
      "catalyst_ref": {"value": null, "provenance": {}, "confidence": 0},
      "condition_ref": {"value": null, "provenance": {}, "confidence": 0},
      "metric": "conversion|selectivity|yield|STY|productivity|ratio|stability",
      "species_or_range": "CO2|CO|CH4|C5+|C8-C16|liquid hydrocarbon|jet-fuel-range hydrocarbons|null",
      "value": null,
      "unit": null,
      "basis": null,
      "is_calculated": false,
      "is_from_figure": false,
      "source_value": null,
      "source_unit": null,
      "provenance": {},
      "confidence": 0,
      "uncertainty": null
    }
  ]
}
```

## Stage-Specific Rules

- conversion 必须标明对象：CO conversion、CO2 conversion、syngas conversion 等。
- selectivity 必须标明 carbon basis、product basis 或原文 basis；没有 basis 填 null 并降低 confidence。
- C5+、C8-C16、jet-fuel-range hydrocarbons、liquid hydrocarbon 既可能是 selectivity，也可能是 yield 或 fraction，必须按原文字段记录 metric。
- STY/productivity 必须保留单位，例如 gHC gcat^-1 h^-1、mmol gFe^-1 h^-1。
- 同一表格多行数据不要合并成一个均值；每个可追踪条件单独记录。

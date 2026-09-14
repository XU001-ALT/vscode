# Prompt 03 - Reaction Conditions Extraction

读取当前 paper 的 context_blocks，只抽取反应条件。每组 catalyst + feed + condition + reactor 生成一条 reaction condition record。

## Fields

- catalyst_id_or_name
- feed_gas
- H2/CO2
- H2/CO
- CO2/CO
- temperature
- pressure
- GHSV/WHSV
- reactor
- time_on_stream
- reduction_before_reaction
- diluent/internal_standard

## Output JSON Shape

```json
{
  "paper_id": "<paper_id>",
  "stage": "reaction_conditions",
  "reaction_conditions": [
    {
      "condition_id": "<paper_id>:cond001",
      "catalyst_ref": {"value": null, "provenance": {}, "confidence": 0},
      "feed_gas": [{"component": null, "value": null, "unit": null, "provenance": {}, "confidence": 0}],
      "h2_co2_ratio": {"value": null, "unit": null, "provenance": {}, "confidence": 0},
      "h2_co_ratio": {"value": null, "unit": null, "provenance": {}, "confidence": 0},
      "temperature": {"value": null, "unit": null, "provenance": {}, "confidence": 0},
      "pressure": {"value": null, "unit": null, "provenance": {}, "confidence": 0},
      "space_velocity": {"value": null, "unit": null, "type": null, "provenance": {}, "confidence": 0},
      "reactor": {"value": null, "provenance": {}, "confidence": 0},
      "time_on_stream": {"value": null, "unit": null, "provenance": {}, "confidence": 0},
      "reduction_before_reaction": {"value": null, "provenance": {}, "confidence": 0}
    }
  ]
}
```

## Stage-Specific Rules

- H2/CO2 与 H2/CO 不可混淆；若 feed 同时含 CO 与 CO2，分别记录。
- GHSV、WHSV、SV、contact time、residence time 必须保留原文单位。
- temperature/pressure 若为范围，保留范围字符串，并可额外给 min/max。
- 反应器类型要尽可能具体：fixed-bed, slurry-bed, microreactor, autoclave, photothermal reactor 等。


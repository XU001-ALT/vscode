# Prompt 02 - Catalyst Information Extraction

读取当前 paper 的 context_blocks，只抽取催化剂信息。一个 catalyst formulation / sample code 生成一条 catalyst record。

## Fields

- catalyst_name_or_code
- active_metal
- support
- promoter
- loading
- metal_ratio
- preparation_method
- calcination
- reduction
- pretreatment
- characterization_phase

## Output JSON Shape

```json
{
  "paper_id": "<paper_id>",
  "stage": "catalyst",
  "catalysts": [
    {
      "catalyst_id": "<paper_id>:cat001",
      "catalyst_name_or_code": {"value": null, "provenance": {}, "confidence": 0},
      "active_metal": [{"value": null, "provenance": {}, "confidence": 0}],
      "support": {"value": null, "provenance": {}, "confidence": 0},
      "promoter": [{"value": null, "provenance": {}, "confidence": 0}],
      "loading": [{"value": null, "unit": null, "basis": null, "provenance": {}, "confidence": 0}],
      "metal_ratio": [{"value": null, "unit": null, "basis": null, "provenance": {}, "confidence": 0}],
      "preparation_method": {"value": null, "provenance": {}, "confidence": 0},
      "calcination": {"temperature": null, "time": null, "atmosphere": null, "provenance": {}, "confidence": 0},
      "reduction": {"temperature": null, "time": null, "atmosphere": null, "provenance": {}, "confidence": 0},
      "pretreatment": {"value": null, "provenance": {}, "confidence": 0},
      "characterization_phase": [{"value": null, "provenance": {}, "confidence": 0}]
    }
  ]
}
```

## Stage-Specific Rules

- 区分 active metal、support、promoter：例如 K/Fe/Mn/SiO2 中 Fe 通常为 active metal，K/Mn 可能为 promoter，SiO2 为 support，但必须由上下文确认。
- loading 必须保留 wt%, mol%, atomic ratio, mass ratio 等原始单位和 basis。
- catalyst code 与组成要分离；不要把 "Fe-ZSM-5" 同时错误写成 support 和 active metal，除非上下文说明。
- calcination/reduction 必须尽量拆出 temperature、time、atmosphere；缺项填 null。


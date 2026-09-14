# Prompt 01 - Paper Metadata Extraction

读取当前 paper 的 metadata prior 和 context_blocks，只抽取论文元数据。不要抽取催化剂、反应条件或性能数据。

## Fields

- title
- DOI
- journal
- year
- authors
- document_type
- route_type
- exclusion_reason

## Output JSON Shape

```json
{
  "paper_id": "<paper_id>",
  "stage": "metadata",
  "metadata": {
    "title": {"value": null, "provenance": {}, "confidence": 0},
    "doi": {"value": null, "provenance": {}, "confidence": 0},
    "journal": {"value": null, "provenance": {}, "confidence": 0},
    "year": {"value": null, "provenance": {}, "confidence": 0},
    "authors": [{"value": null, "provenance": {}, "confidence": 0}],
    "document_type": {"value": null, "provenance": {}, "confidence": 0},
    "route_type": [{"value": null, "provenance": {}, "confidence": 0}],
    "exclusion_reason": {"value": null, "provenance": {}, "confidence": 0}
  }
}
```

## Stage-Specific Rules

- metadata_prior 可作为候选值，但必须用 context_blocks 或 prior_source 标记来源。
- DOI 优先使用 PDF 首页或页眉页脚证据；若只有 prior_doi，也可保留但 confidence 不超过 0.75。
- route_type 必须基于题名、摘要、关键词或实验描述判断。review / TEA / LCA 也要标出。
- authors 输出作者字符串数组；不要拆错复姓或缩写，证据不足时保留原始作者串。


#!/usr/bin/env python
"""Validate staged LLM extraction JSONL before database ingestion."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "metadata": ["paper_id", "stage", "metadata"],
    "catalyst": ["paper_id", "stage", "catalysts"],
    "reaction_conditions": ["paper_id", "stage", "reaction_conditions"],
    "performance": ["paper_id", "stage", "performance_records"],
    "provenance_confidence": ["paper_id", "stage", "provenance_records"],
}


def iter_records(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line), None
            except json.JSONDecodeError as exc:
                yield line_no, None, exc


def walk_values(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from walk_values(value)
    elif isinstance(obj, list):
        for item in obj:
            yield from walk_values(item)


def has_provenance(value: dict[str, Any]) -> bool:
    if "provenance" in value and isinstance(value["provenance"], dict):
        prov = value["provenance"]
        return bool(prov.get("page") and (prov.get("evidence_text") or prov.get("table_or_figure")))
    return bool(value.get("page") and (value.get("evidence_text") or value.get("table_or_figure")))


def validate_record(line_no: int, record: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    stage = record.get("stage")
    if stage not in REQUIRED_TOP_LEVEL:
        issues.append({"line": line_no, "severity": "error", "code": "unknown_stage", "stage": stage})
        return issues

    for key in REQUIRED_TOP_LEVEL[stage]:
        if key not in record:
            issues.append({"line": line_no, "severity": "error", "code": "missing_top_level_key", "key": key})

    for obj in walk_values(record):
        if "confidence" in obj:
            try:
                conf = float(obj["confidence"])
                if conf < 0 or conf > 1:
                    issues.append({"line": line_no, "severity": "error", "code": "confidence_out_of_range"})
            except (TypeError, ValueError):
                issues.append({"line": line_no, "severity": "error", "code": "confidence_not_numeric"})
        if "value" in obj and obj.get("value") not in (None, ""):
            if not has_provenance(obj) and stage != "provenance_confidence":
                issues.append(
                    {
                        "line": line_no,
                        "severity": "warning",
                        "code": "value_without_provenance",
                        "field": obj.get("field", ""),
                    }
                )
            if isinstance(obj.get("value"), (int, float)) and not obj.get("unit"):
                issues.append(
                    {
                        "line": line_no,
                        "severity": "warning",
                        "code": "numeric_value_without_unit",
                        "field": obj.get("field", ""),
                    }
                )

    return issues


def validate_file(path: Path) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    records_by_stage = Counter()
    records_by_paper = defaultdict(set)
    parsed_records = 0

    for line_no, record, error in iter_records(path):
        if error:
            issues.append({"line": line_no, "severity": "error", "code": "invalid_json", "message": str(error)})
            continue
        parsed_records += 1
        stage = record.get("stage", "UNKNOWN")
        paper_id = record.get("paper_id", "UNKNOWN")
        records_by_stage[stage] += 1
        records_by_paper[paper_id].add(stage)
        issues.extend(validate_record(line_no, record))

    missing_stage = []
    expected = set(REQUIRED_TOP_LEVEL)
    for paper_id, stages in records_by_paper.items():
        missing = sorted(expected - stages)
        if missing:
            missing_stage.append({"paper_id": paper_id, "missing_stages": missing})

    issue_counts = Counter(issue["code"] for issue in issues)
    severity_counts = Counter(issue["severity"] for issue in issues)
    return {
        "input": str(path),
        "parsed_records": parsed_records,
        "records_by_stage": dict(records_by_stage),
        "papers_seen": len(records_by_paper),
        "issue_counts": dict(issue_counts),
        "severity_counts": dict(severity_counts),
        "missing_stage_count": len(missing_stage),
        "missing_stage_examples": missing_stage[:50],
        "issues": issues[:1000],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input_jsonl")
    parser.add_argument("--out", default="")
    args = parser.parse_args()
    result = validate_file(Path(args.input_jsonl).resolve())
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).resolve().write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

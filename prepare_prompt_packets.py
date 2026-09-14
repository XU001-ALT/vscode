#!/usr/bin/env python
"""Prepare staged prompt packets from a PDF manifest.

Each output JSONL row is one paper-stage packet. It contains compact evidence
blocks, not the whole paper, so the downstream LLM call stays auditable.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter

from pathlib import Path
from typing import Any

from pypdf import PdfReader


STAGE_KEYWORDS = {
    "metadata": [
        "doi",
        "abstract",
        "journal",
        "received",
        "accepted",
        "published",
        "keywords",
    ],
    "catalyst": [
        "catalyst",
        "catalysts",
        "support",
        "supported",
        "promoter",
        "loading",
        "impregnation",
        "precipitation",
        "calcined",
        "calcination",
        "reduced",
        "reduction",
        "preparation",
        "synthesis of",
        "wt%",
    ],
    "reaction_conditions": [
        "reaction conditions",
        "fixed-bed",
        "slurry",
        "reactor",
        "h2/co",
        "h2/co2",
        "ghsv",
        "whsv",
        "temperature",
        "pressure",
        "time on stream",
        "time-on-stream",
        "tos",
        "feed gas",
    ],
    "performance": [
        "conversion",
        "selectivity",
        "yield",
        "sty",
        "space time yield",
        "c5+",
        "c8-c16",
        "ch4",
        "methane",
        "co selectivity",
        "liquid hydrocarbon",
        "jet fuel",
        "hydrocarbons",
    ],
    "provenance_confidence": [
        "table",
        "figure",
        "fig.",
        "caption",
        "supplementary",
        "calculated",
        "estimated",
        "read from",
    ],
}

PROMPT_FILES = {
    "metadata": "prompts/01_metadata.md",
    "catalyst": "prompts/02_catalyst.md",
    "reaction_conditions": "prompts/03_reaction_conditions.md",
    "performance": "prompts/04_performance.md",
    "provenance_confidence": "prompts/05_provenance_confidence.md",
}


def load_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def page_texts(pdf_path: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(pdf_path))
    pages = []
    for idx, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001 - record page-level failure.
            text = f"[PAGE_TEXT_ERROR: {type(exc).__name__}: {exc}]"
        normalized = re.sub(r"\s+", " ", text).strip()
        pages.append({"page": idx, "text": normalized})
    return pages


def keyword_score(text: str, keywords: list[str]) -> tuple[int, list[str]]:
    low = text.lower()
    hits = [kw for kw in keywords if kw in low]
    return len(hits), hits


def extract_captions(text: str) -> list[str]:
    captions: list[str] = []
    pattern = re.compile(r"\b((?:Table|Fig\.?|Figure)\s*\d+[\w.-]*\s*[:.\-]?\s*[^.]{20,260})", re.I)
    for match in pattern.finditer(text):
        captions.append(re.sub(r"\s+", " ", match.group(1)).strip())
    return captions[:12]


def select_blocks(
    pages: list[dict[str, Any]],
    stage: str,
    max_pages: int,
    max_chars: int,
) -> list[dict[str, Any]]:
    keywords = STAGE_KEYWORDS[stage]
    scored = []
    for page in pages:
        score, hits = keyword_score(page["text"], keywords)
        boost = 1 if stage == "metadata" and page["page"] <= 2 else 0
        if score or boost:
            scored.append((score + boost, page["page"], hits, page["text"]))

    if stage == "metadata":
        for page in pages[:2]:
            if all(item[1] != page["page"] for item in scored):
                scored.append((1, page["page"], ["first_page"], page["text"]))

    scored.sort(key=lambda item: (-item[0], item[1]))
    selected = scored[:max_pages]
    blocks = []
    for score, page_number, hits, text in selected:
        blocks.append(
            {
                "page": page_number,
                "selection_score": score,
                "keyword_hits": hits,
                "captions": extract_captions(text),
                "text": text[:max_chars],
            }
        )
    return blocks


def prior_from_row(row: dict[str, str]) -> dict[str, str]:
    keys = [
        "filename_author_guess",
        "filename_year_guess",
        "filename_title_guess",
        "first_page_doi",
        "prior_doi",
        "prior_title",
        "prior_journal",
        "prior_year",
        "prior_authors",
        "prior_publisher_group",
        "prior_document_type",
        "prior_keywords",
        "metadata_prior_match_score",
    ]
    return {key: row.get(key, "") for key in keys if row.get(key, "")}


def make_packets(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.root).resolve()
    manifest_rows = load_manifest(Path(args.manifest).resolve())
    stages = [stage.strip() for stage in args.stages.split(",") if stage.strip()]
    if "all" in stages:
        stages = list(STAGE_KEYWORDS)

    if args.paper_id:
        wanted = set(args.paper_id.split(","))
        manifest_rows = [row for row in manifest_rows if row.get("paper_id") in wanted]
    if args.limit:
        manifest_rows = manifest_rows[: args.limit]

    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    stats = Counter()
    with out_path.open("w", encoding="utf-8") as handle:
        for row_index, row in enumerate(manifest_rows, start=1):
            if str(row.get("valid_pdf_gt20kb", "")).lower() not in {"true", "1"}:
                stats["skipped_invalid_pdf"] += 1
                continue
            pdf_path = root / row["relative_path"]
            try:
                pages = page_texts(pdf_path)
            except Exception as exc:  # noqa: BLE001 - keep corpus moving.
                stats["pdf_read_error"] += 1
                error_packet = {
                    "paper_id": row.get("paper_id"),
                    "relative_path": row.get("relative_path"),
                    "error": f"{type(exc).__name__}: {exc}",
                }
                handle.write(json.dumps(error_packet, ensure_ascii=False) + "\n")
                continue

            for stage in stages:
                blocks = select_blocks(pages, stage, args.max_pages_per_stage, args.max_chars_per_page)
                packet = {
                    "paper_id": row.get("paper_id"),
                    "stage": stage,
                    "prompt_template": PROMPT_FILES.get(stage, ""),
                    "schema": "schemas/saf_extraction.schema.json",
                    "relative_path": row.get("relative_path"),
                    "file_name": row.get("file_name"),
                    "source_set": row.get("source_set"),
                    "route_type_seed": row.get("route_type_seed"),
                    "page_count": row.get("page_count"),
                    "metadata_prior": prior_from_row(row),
                    "context_blocks": blocks,
                    "expected_output": "strict JSON object matching the stage-specific schema; no markdown",
                    "notes": [
                        "Use only supplied context blocks and metadata priors.",
                        "Return null for absent fields; do not infer unsupported values.",
                        "Attach provenance to every extracted value.",
                    ],
                }
                handle.write(json.dumps(packet, ensure_ascii=False) + "\n")
                stats[f"packet_{stage}"] += 1
            stats["papers_processed"] += 1
            if args.progress_every and row_index % args.progress_every == 0:
                print(f"processed {row_index}/{len(manifest_rows)} papers")

    summary = {"output": str(out_path), "stats": dict(stats), "stages": stages}
    summary_path = out_path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=r"D:\Agent\Codex\files\H_ywj_95")
    parser.add_argument(
        "--manifest",
        default=r"D:\Agent\Codex\files\H_ywj_95\saf_prompt_pipeline\outputs\manifest_full.csv",
    )
    parser.add_argument(
        "--out",
        default=r"D:\Agent\Codex\files\H_ywj_95\saf_prompt_pipeline\outputs\sample_prompt_packets.jsonl",
    )
    parser.add_argument("--stages", default="all")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--paper-id", default="")
    parser.add_argument("--max-pages-per-stage", type=int, default=4)
    parser.add_argument("--max-chars-per-page", type=int, default=3500)
    parser.add_argument("--progress-every", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(make_packets(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

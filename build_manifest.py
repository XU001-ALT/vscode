#!/usr/bin/env python
"""Build a PDF manifest for the SAF literature prompt pipeline.

The manifest is deliberately file-system first. Existing XLSX files are used as
optional priors, because download-era filenames can differ from current files.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re

from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd
from pypdf import PdfReader

# ========== 修改点 1：不再使用固定的子目录，而是直接扫描根目录下所有 PDF ==========
# PDF_DIRS 改为一个元组，表示“扫描整个根目录”，source_set 设为 "root"
PDF_DIRS = [
    ("root", Path(".")),  # 表示扫描 root 目录本身（包括子目录，由 discover_pdfs 中的 rglob 实现）
]
# =================================================================================

STAGES = [
    "metadata",
    "catalyst",
    "reaction_conditions",
    "performance",
    "provenance_confidence",
]


def normalize_text(value: Any) -> str:
    text = "" if value is None else str(value)
    text = text.lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def parse_filename(path: Path) -> dict[str, str]:
    stem = path.stem
    suffix_hash = ""
    match = re.search(r"_([0-9a-f]{10,12})$", stem, flags=re.I)
    if match:
        suffix_hash = match.group(1).lower()
        stem = stem[: match.start()]

    year = ""
    author = ""
    title = stem.replace("_", " ")
    year_match = re.search(r"(^|_)(19|20)\d{2}(_|$)", stem)
    if year_match:
        year = year_match.group(0).strip("_")
        before = stem[: year_match.start()].strip("_")
        after = stem[year_match.end() :].strip("_")
        author = before.replace("_", " ").strip()
        title = after.replace("_", " ").strip() or title

    return {
        "filename_author_guess": author,
        "filename_year_guess": year,
        "filename_title_guess": title,
        "filename_hash_suffix": suffix_hash,
    }


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_pdf_info(path: Path) -> dict[str, Any]:
    info: dict[str, Any] = {
        "pdf_header_valid": False,
        "pdf_read_ok": False,
        "pdf_error": "",
        "page_count": "",
        "is_encrypted": "",
        "pdf_metadata_title": "",
        "pdf_metadata_author": "",
        "first_page_doi": "",
    }

    try:
        with path.open("rb") as handle:
            info["pdf_header_valid"] = handle.read(5) == b"%PDF-"
    except OSError as exc:
        info["pdf_error"] = f"header_read_error: {exc}"
        return info

    try:
        reader = PdfReader(str(path))
        info["is_encrypted"] = bool(reader.is_encrypted)
        info["page_count"] = len(reader.pages)
        meta = reader.metadata or {}
        info["pdf_metadata_title"] = str(meta.get("/Title", "") or "")[:500]
        info["pdf_metadata_author"] = str(meta.get("/Author", "") or "")[:500]
        if reader.pages:
            text = reader.pages[0].extract_text() or ""
            doi_match = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", text, flags=re.I)
            if doi_match:
                info["first_page_doi"] = doi_match.group(0).rstrip(".,;)").lower()
        info["pdf_read_ok"] = True
    except Exception as exc:  # noqa: BLE001 - record and continue over a corpus.
        info["pdf_error"] = f"{type(exc).__name__}: {exc}"

    return info


def load_xlsx_priors(root: Path) -> list[dict[str, str]]:
    candidates = [
        ("T_ywj_downloaded_completed_summary(1).xlsx", "Downloaded_All"),
        ("T_ywj_OA_by_publisher.xlsx", "All_OA"),
        ("T_ywj_non_OA_by_publisher(1).xlsx", "All_NonOA"),
    ]
    rows: list[dict[str, str]] = []
    keep = [
        "DOI",
        "Article Title",
        "Source Title",
        "Publication Year",
        "Authors",
        "publisher_group",
        "publisher_basis",
        "access_classification",
        "Document Type",
        "Publication Type",
        "Author Keywords",
        "Abstract",
    ]
    for filename, sheet in candidates:
        path = root / filename
        if not path.exists():
            continue
        try:
            frame = pd.read_excel(path, sheet_name=sheet, dtype=str)
        except Exception:
            continue
        for _, row in frame.iterrows():
            record = {key: str(row.get(key, "") or "") for key in keep}
            record["_source_workbook"] = filename
            record["_source_sheet"] = sheet
            record["_norm_title"] = normalize_text(record.get("Article Title"))
            record["_norm_author"] = normalize_text(record.get("Authors", "").split(";")[0])
            if record["_norm_title"]:
                rows.append(record)
    return rows


def best_prior_match(parsed: dict[str, str], priors: list[dict[str, str]]) -> dict[str, str]:
    title_norm = normalize_text(parsed.get("filename_title_guess"))
    author_norm = normalize_text(parsed.get("filename_author_guess"))
    year = parsed.get("filename_year_guess", "")
    if not title_norm:
        return {}

    best_score = 0.0
    best: dict[str, str] = {}
    for prior in priors:
        if year and prior.get("Publication Year") and year != str(prior.get("Publication Year"))[:4]:
            continue
        prior_title = prior.get("_norm_title", "")
        if not prior_title:
            continue
        title_score = SequenceMatcher(None, title_norm, prior_title).ratio()
        if title_norm in prior_title or prior_title in title_norm:
            title_score = max(title_score, 0.92)
        author_score = 0.0
        prior_author = prior.get("_norm_author", "")
        if author_norm and prior_author:
            author_score = 1.0 if author_norm[:8] and author_norm[:8] in prior_author else 0.0
        score = title_score * 0.9 + author_score * 0.1
        if score > best_score:
            best_score = score
            best = prior

    if best_score < 0.72:
        return {"metadata_prior_match_score": f"{best_score:.3f}"}

    return {
        "metadata_prior_match_score": f"{best_score:.3f}",
        "prior_doi": best.get("DOI", ""),
        "prior_title": best.get("Article Title", ""),
        "prior_journal": best.get("Source Title", ""),
        "prior_year": best.get("Publication Year", ""),
        "prior_authors": best.get("Authors", ""),
        "prior_publisher_group": best.get("publisher_group", ""),
        "prior_access_classification": best.get("access_classification", ""),
        "prior_document_type": best.get("Document Type", ""),
        "prior_publication_type": best.get("Publication Type", ""),
        "prior_keywords": best.get("Author Keywords", ""),
        "prior_abstract": best.get("Abstract", ""),
        "prior_source_workbook": best.get("_source_workbook", ""),
        "prior_source_sheet": best.get("_source_sheet", ""),
    }


# ========== 修改点 2：改为递归扫描根目录下所有 PDF，忽略子目录结构 ==========
def discover_pdfs(root: Path) -> list[tuple[str, Path]]:
    pdfs: list[tuple[str, Path]] = []
    # 使用 rglob 递归查找所有 .pdf 文件
    for path in sorted(root.rglob("*.pdf")):
        pdfs.append(("root", path))  # 全部标记为 source_set = "root"
    return pdfs
# ========================================================================


def build_manifest(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(args.root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    priors = load_xlsx_priors(root) if args.use_xlsx_priors else []
    pdfs = discover_pdfs(root)
    rows: list[dict[str, Any]] = []

    for index, (source_set, path) in enumerate(pdfs, start=1):
        rel_path = path.relative_to(root).as_posix()
        stat = path.stat()
        parsed = parse_filename(path)
        pdf_info = read_pdf_info(path)
        paper_id = hashlib.sha1(rel_path.encode("utf-8")).hexdigest()[:16]
        row: dict[str, Any] = {
            "paper_id": paper_id,
            "source_set": source_set,
            "route_type_seed": source_set,
            "relative_path": rel_path,
            "file_name": path.name,
            "file_size_bytes": stat.st_size,
            "file_size_mb": round(stat.st_size / 1024 / 1024, 3),
            "valid_pdf_gt20kb": bool(stat.st_size > 20_000 and pdf_info["pdf_header_valid"]),
            "last_write_time": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            **parsed,
            **pdf_info,
        }
        if args.hash_files:
            row["sha256"] = sha256_file(path)
        row.update(best_prior_match(parsed, priors))
        for stage in STAGES:
            row[f"{stage}_status"] = "queued" if row["valid_pdf_gt20kb"] else "blocked_invalid_pdf"
        rows.append(row)
        if args.progress_every and index % args.progress_every == 0:
            print(f"processed {index}/{len(pdfs)}")

    summary = summarize(rows)
    summary["root"] = str(root)
    summary["created_at"] = datetime.now(timezone.utc).isoformat()
    summary["xlsx_prior_rows_loaded"] = len(priors)
    summary["pdf_dirs"] = [{"source_set": name, "relative_dir": rel.as_posix()} for name, rel in PDF_DIRS]
    return rows, summary


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def counter(field: str, limit: int = 30) -> dict[str, int]:
        values = [str(row.get(field, "") or "UNKNOWN") for row in rows]
        return dict(Counter(values).most_common(limit))

    years = [row.get("filename_year_guess") or row.get("prior_year") or "UNKNOWN" for row in rows]
    invalid = [row for row in rows if not row.get("valid_pdf_gt20kb")]
    no_text = [row for row in rows if not row.get("pdf_read_ok")]
    matched = [
        row
        for row in rows
        if float(str(row.get("metadata_prior_match_score") or 0) or 0) >= 0.72
    ]

    return {
        "pdf_count": len(rows),
        "valid_pdf_count": len(rows) - len(invalid),
        "invalid_pdf_count": len(invalid),
        "pdf_read_error_count": len(no_text),
        "metadata_prior_matched_count": len(matched),
        "by_source_set": counter("source_set"),
        "by_year_guess": dict(Counter(years).most_common(40)),
        "by_prior_publisher_group": counter("prior_publisher_group"),
        "by_prior_access_classification": counter("prior_access_classification"),
        "smallest_files": sorted(
            [
                {
                    "file_name": row["file_name"],
                    "source_set": row["source_set"],
                    "file_size_mb": row["file_size_mb"],
                    "valid_pdf_gt20kb": row["valid_pdf_gt20kb"],
                }
                for row in rows
            ],
            key=lambda item: item["file_size_mb"],
        )[:20],
    }


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], out_dir: Path) -> None:
    manifest_path = out_dir / "manifest_full.csv"
    if rows:
        fieldnames: list[str] = []
        for row in rows:
            for key in row:
                if key not in fieldnames:
                    fieldnames.append(key)
        with manifest_path.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    with (out_dir / "manifest_summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)

    md_lines = [
        "# SAF PDF Manifest Coverage",
        "",
        f"- PDF count: {summary['pdf_count']}",
        f"- Valid PDF count: {summary['valid_pdf_count']}",
        f"- Invalid or tiny PDF count: {summary['invalid_pdf_count']}",
        f"- PDF read error count: {summary['pdf_read_error_count']}",
        f"- XLSX metadata prior matches: {summary['metadata_prior_matched_count']}",
        "",
        "## Source Sets",
        "",
    ]
    for key, value in summary["by_source_set"].items():
        md_lines.append(f"- {key}: {value}")
    md_lines.extend(["", "## Top Year Guesses", ""])
    for key, value in list(summary["by_year_guess"].items())[:20]:
        md_lines.append(f"- {key}: {value}")
    md_lines.extend(["", "## Smallest Files To Check", ""])
    for item in summary["smallest_files"][:15]:
        md_lines.append(
            f"- {item['source_set']} | {item['file_size_mb']} MB | "
            f"valid={item['valid_pdf_gt20kb']} | {item['file_name']}"
        )
    (out_dir / "coverage_matrix.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    # ========== 修改点 3：将默认 root 改为 D:\downloads ==========
    parser.add_argument("--root", default=r"D:\downloads")
    parser.add_argument("--out-dir", default=r"D:\agent\saf_extraction\outputs")
    parser.add_argument("--hash-files", action="store_true", help="Compute SHA-256 for every PDF.")
    parser.add_argument("--no-xlsx-priors", dest="use_xlsx_priors", action="store_false")
    parser.add_argument("--progress-every", type=int, default=100)
    parser.set_defaults(use_xlsx_priors=True)
    args = parser.parse_args()

    rows, summary = build_manifest(args)
    write_outputs(rows, summary, Path(args.out_dir).resolve())
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
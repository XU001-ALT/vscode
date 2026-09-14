"""
ingest_extraction.py
把 LLM 5 阶段抽取的 JSON 结果写入 SQLite 三张表：
  - papers（1 篇 1 行）
  - formulations（1 催化剂 1 行）
  - numeric_observations（每条数值 1 行）

写入后由 rebuild_parquet.py 聚合生成 parquet 宽表。

用法（在 app27.py 中调用）:
    from ingest_extraction import ingest_extraction
    stats = ingest_extraction(con, paper_id, sha256, file_name, file_size, page_count, extraction_results)
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd


import numpy as np
# ════════════════════════════════════════════════════
# 辅助函数
# ════════════════════════════════════════════════════
def _ensure_tables(con: sqlite3.Connection) -> None:
    """确保三张表存在（首次运行 / 新数据库时自动建表，已有表不受影响）"""
    con.executescript("""
    CREATE TABLE IF NOT EXISTS papers (
        paper_id TEXT PRIMARY KEY,
        source_file TEXT,
        relative_path TEXT,
        folder_group TEXT,
        file_size_bytes INTEGER,
        modified_utc TEXT,
        pdf_sha256 TEXT,
        page_count INTEGER,
        publisher_group TEXT,
        extraction_status TEXT,
        extraction_error TEXT,
        parser_version TEXT,
        extracted_at TEXT,
        doi TEXT,
        title TEXT,
        year INTEGER,
        journal TEXT,
        authors TEXT
    );

    CREATE TABLE IF NOT EXISTS formulations (
        formulation_id TEXT PRIMARY KEY,
        paper_id TEXT,
        formulation_label TEXT,
        catalyst_name_raw TEXT,
        catalyst_name_normalized TEXT,
        catalyst_family TEXT,
        support TEXT,
        support_type TEXT,
        structure_type TEXT,
        formulation_confidence TEXT,
        source_page INTEGER,
        evidence_hash TEXT,
        review_status TEXT,
        promoter TEXT,
        preparation_method TEXT,
        calcination_temperature TEXT,
        calcination_time TEXT,
        calcination_atmosphere TEXT,
        reduction_temperature TEXT,
        reduction_time TEXT,
        reduction_atmosphere TEXT
    );

    CREATE TABLE IF NOT EXISTS numeric_observations (
        observation_id TEXT PRIMARY KEY,
        paper_id TEXT,
        page_number INTEGER,
        line_number INTEGER,
        field_family TEXT,
        metric_hint TEXT,
        raw_value TEXT,
        normalized_value REAL,
        raw_unit TEXT,
        normalized_unit TEXT,
        context TEXT,
        evidence_hash TEXT,
        parser_version TEXT,
        confidence REAL,
        review_status TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_no_paper ON numeric_observations(paper_id);
    CREATE INDEX IF NOT EXISTS idx_no_field ON numeric_observations(field_family, metric_hint);
    CREATE INDEX IF NOT EXISTS idx_form_paper ON formulations(paper_id);
    """)


def _first_value(field: Any, key: str = "value") -> Any:
    """从字段中取 value，兼容单对象和列表两种格式"""
    if not field:
        return None
    if isinstance(field, list):
        if not field:
            return None
        field = field[0]
    if isinstance(field, dict):
        return field.get(key)
    return field


def _first_number(val: Any) -> Optional[float]:
    """从可能含范围的字符串提取数字，如 '210-240' → 240.0（取上限）"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    nums = re.findall(r"[\d.]+", str(val))
    if nums:
        try:
            return float(nums[-1])  # 取最后一个数字（通常是上限）
        except Exception:
            return None
    return None


def _parse_ratio(val: Any) -> Optional[float]:
    """解析 H2/CO 比例值，支持 '2/1', '2:1', 2.0 等"""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    m = re.match(r"^([\d.]+)\s*[:/]\s*([\d.]+)$", s)
    if m:
        num, den = float(m.group(1)), float(m.group(2))
        return num / den if den != 0 else None
    try:
        return float(s)
    except Exception:
        return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_hash(paper_id: str, *parts) -> str:
    """生成稳定的 evidence_hash"""
    raw = paper_id + "|" + "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _extract_number_from_text(text: str, unit: Optional[str] = None) -> Optional[float]:
    """从文本里提取数值。
    优先提取 unit 前面的数字（如 '4 bar' + unit='bar' → 4.0）；
    没有 unit 时取第一个数字（通常是目标值）。
    """
    if not text:
        return None
    text = str(text)

    # 如果有 unit，尝试提取 unit 紧邻的数字
    if unit:
        unit_escaped = re.escape(str(unit))
        # 匹配 "数字 + 可选空格 + unit"，如 "4 bar", "33%", "0.92"
        patterns = [
            rf"([\d.]+)\s*{unit_escaped}",  # 数字在 unit 前
            rf"=\s*([\d.]+)",  # " = 0.92" 格式
        ]
        for pat in patterns:
            matches = re.findall(pat, text)
            if matches:
                try:
                    return float(matches[0])
                except Exception:
                    continue

    # 无 unit 或未匹配：取第一个数字（通常是目标值，而非上下文中的其他数值）
    nums = re.findall(r"[\d.]+", text)
    if nums:
        try:
            return float(nums[0])
        except Exception:
            return None
    return None


# 非数值型 target_field（不写入 numeric_observations）
_NON_NUMERIC_FIELDS = {
    "journal", "doi", "catalyst_type", "catalyst_initial_state",
}


# ════════════════════════════════════════════════════
# 主函数
# ════════════════════════════════════════════════════
def ingest_extraction(
    con: sqlite3.Connection,
    paper_id: str,
    sha256: str,
    file_name: str,
    file_size: int,
    page_count: Optional[int],
    extraction_results: Dict[str, Any],
) -> Dict[str, int]:
    """
    把 LLM 5 阶段抽取结果写入 SQLite 三张表。

    返回: {"papers": 1, "formulations": N, "numeric_observations": N}
    """
    now = _now_iso()
    stats = {"papers": 0, "formulations": 0, "numeric_observations": 0}

    # 确保三张表存在（首次运行 / 新数据库时自动建表）
    _ensure_tables(con)

    # 先删除该 paper_id 的旧数据（覆盖模式）
    for tbl in ("numeric_observations", "formulations", "papers"):
        con.execute(f"DELETE FROM {tbl} WHERE paper_id = ?", (paper_id,))

    # ── 1. 从 metadata 阶段提取论文元数据 ──
    meta = extraction_results.get("metadata", {}).get("metadata", {})
    meta_doi = _first_value(meta.get("doi"))
    meta_title = _first_value(meta.get("title"))
    meta_year = _first_value(meta.get("year"))
    meta_journal = _first_value(meta.get("journal"))
    # authors 是列表，拼成逗号分隔字符串
    authors_list = meta.get("authors", [])
    if isinstance(authors_list, list):
        meta_authors = ", ".join(
            str(_first_value(a)) for a in authors_list if _first_value(a)
        ) or None
    else:
        meta_authors = _first_value(authors_list)

    # ── 2. 写入 papers 表（含元数据） ──
    con.execute(
        """INSERT INTO papers
           (paper_id, source_file, relative_path, folder_group, file_size_bytes,
            modified_utc, pdf_sha256, page_count, publisher_group,
            extraction_status, extraction_error, parser_version, extracted_at,
            doi, title, year, journal, authors)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            paper_id,
            file_name,
            f"uploads/{file_name}",
            "uploads",
            file_size,
            now,
            sha256,
            page_count,
            None,  # publisher_group 未知
            "success",
            None,
            "llm_extraction_v1",
            now,
            meta_doi,
            meta_title,
            meta_year,
            meta_journal,
            meta_authors,
        ),
    )
    stats["papers"] = 1

    # ── 3. 写入 formulations 表（含催化剂详情） ──
    cat_stage = extraction_results.get("catalyst", {})
    catalysts = cat_stage.get("catalysts", [])
    if catalysts:
        for cat in catalysts:
            cat_id = cat.get("catalyst_id") or f"{paper_id}:cat001"
            active_metal = _first_value(cat.get("active_metal"))
            support = _first_value(cat.get("support"))
            name_raw = _first_value(cat.get("catalyst_name_or_code"))

            # 构造 catalyst_name_normalized
            if active_metal and support:
                name_norm = f"{active_metal} on {support}"
            elif active_metal:
                name_norm = active_metal
            else:
                name_norm = name_raw or "unknown"

            # 派生 catalyst_family
            if active_metal:
                family = f"{active_metal}-based"
            else:
                family = None

            # promoter 列表拼成字符串
            promoter_list = cat.get("promoter", [])
            if isinstance(promoter_list, list):
                promoter_str = ", ".join(
                    str(_first_value(p)) for p in promoter_list if _first_value(p)
                ) or None
            else:
                promoter_str = _first_value(promoter_list)

            # preparation_method
            prep_method = _first_value(cat.get("preparation_method"))

            # calcination / reduction（嵌套对象，取 temperature/time/atmosphere）
            calc = cat.get("calcination") or {}
            red = cat.get("reduction") or {}
            calc_temp = calc.get("temperature") if isinstance(calc, dict) else None
            calc_time = calc.get("time") if isinstance(calc, dict) else None
            calc_atm = calc.get("atmosphere") if isinstance(calc, dict) else None
            red_temp = red.get("temperature") if isinstance(red, dict) else None
            red_time = red.get("time") if isinstance(red, dict) else None
            red_atm = red.get("atmosphere") if isinstance(red, dict) else None

            # 取 provenance page
            source_page = None
            for field_name in ("catalyst_name_or_code", "active_metal", "support"):
                field_obj = cat.get(field_name)
                if isinstance(field_obj, dict):
                    prov = field_obj.get("provenance", {})
                    page = prov.get("page")
                    if page:
                        source_page = page if isinstance(page, int) else (
                            page[0] if isinstance(page, list) and page else None
                        )
                        break

            con.execute(
                """INSERT INTO formulations
                   (formulation_id, paper_id, formulation_label,
                    catalyst_name_raw, catalyst_name_normalized, catalyst_family,
                    support, support_type, structure_type,
                    formulation_confidence, source_page, evidence_hash, review_status,
                    promoter, preparation_method,
                    calcination_temperature, calcination_time, calcination_atmosphere,
                    reduction_temperature, reduction_time, reduction_atmosphere)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    cat_id,
                    paper_id,
                    "llm_extracted",
                    name_raw,
                    name_norm,
                    family,
                    support,
                    None,  # support_type
                    None,  # structure_type
                    "llm_extracted",
                    source_page,
                    _evidence_hash(paper_id, cat_id, name_norm),
                    "llm_extracted",
                    promoter_str,
                    prep_method,
                    calc_temp, calc_time, calc_atm,
                    red_temp, red_time, red_atm,
                ),
            )
            stats["formulations"] += 1
    else:
        # 没有 catalyst 数据，写一条最小记录保证 formulations 有行
        con.execute(
            """INSERT INTO formulations
               (formulation_id, paper_id, formulation_label,
                catalyst_name_raw, catalyst_name_normalized, catalyst_family,
                support, support_type, structure_type,
                formulation_confidence, source_page, evidence_hash, review_status,
                promoter, preparation_method,
                calcination_temperature, calcination_time, calcination_atmosphere,
                reduction_temperature, reduction_time, reduction_atmosphere)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"{paper_id}:form001",
                paper_id,
                "llm_extracted",
                None, None, None, None, None, None,
                "llm_extracted", None,
                _evidence_hash(paper_id, "form001"),
                "llm_extracted",
                None, None, None, None, None, None, None, None,
            ),
        )
        stats["formulations"] = 1

    # ── 3. 写入 numeric_observations 表 ──
    obs_rows = _build_numeric_observations(paper_id, extraction_results, now)
    for r in obs_rows:
        con.execute(
            """INSERT INTO numeric_observations
               (observation_id, paper_id, page_number, line_number,
                field_family, metric_hint, raw_value, normalized_value,
                raw_unit, normalized_unit, context, evidence_hash,
                parser_version, confidence, review_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                r["evidence_hash"],
                paper_id,
                r["page_number"],
                r["line_number"],
                r["field_family"],
                r["metric_hint"],
                r["raw_value"],
                r["normalized_value"],
                r["raw_unit"],
                r["normalized_unit"],
                r["context"],
                r["evidence_hash"],
                "llm_extraction_v1",
                "llm_extracted",
                "llm_extracted",
            ),
        )
    stats["numeric_observations"] = len(obs_rows)

    con.commit()
    return stats


def _build_numeric_observations(
    paper_id: str,
    extraction_results: Dict[str, Any],
    now: str,
) -> List[Dict[str, Any]]:
    """从 5 阶段 JSON 构建 numeric_observations 记录列表。

    关键：context 字段必须和 rebuild_parquet.py 的 SQL 过滤逻辑对齐。
    """
    rows: List[Dict[str, Any]] = []
    seq = 0  # 用于 evidence_hash 去重

    def _add(field_family: str, metric_hint: str, value: Optional[float],
             unit: Optional[str], context: str, page: int = 1):
        nonlocal seq
        if value is None:
            return
        seq += 1
        rows.append({
            "page_number": page,
            "line_number": seq,
            "field_family": field_family,
            "metric_hint": metric_hint,
            "raw_value": str(value),
            "normalized_value": value,
            "raw_unit": unit or "",
            "normalized_unit": unit or "",
            "context": context,
            "evidence_hash": _evidence_hash(paper_id, field_family, metric_hint,
                                            value, context, seq),
        })

    # ── 3a. reaction_conditions 阶段 ──
    rc_stage = extraction_results.get("reaction_conditions", {})
    rc_list = rc_stage.get("reaction_conditions", [])
    for rc in rc_list:
        # 温度：context 必须含 "reaction" 才能被 rebuild_parquet 识别
        temp_raw = _first_value(rc.get("temperature"))
        temp_val = _first_number(temp_raw)
        temp_unit = None
        temp_obj = rc.get("temperature")
        if isinstance(temp_obj, dict):
            temp_unit = temp_obj.get("unit")
        if temp_val and 100 <= temp_val <= 600:
            _add("reaction_conditions", "temperature", temp_val,
                 temp_unit or "°C", "reaction temperature (FTS)")

        # 压力
        press_raw = _first_value(rc.get("pressure"))
        press_val = _first_number(press_raw)
        if press_val and 0.1 <= press_val <= 100:
            _add("reaction_conditions", "pressure", press_val,
                 "bar", "reaction pressure")

        # GHSV (space_velocity)
        sv = rc.get("space_velocity")
        if sv:
            sv_val = _first_number(_first_value(sv))
            sv_unit = sv.get("unit") if isinstance(sv, dict) else None
            if sv_val and 1 <= sv_val <= 100000:
                _add("reaction_conditions", "ghsv", sv_val,
                     sv_unit or "h-1", "GHSV space velocity")

        # H2/CO ratio：context 必须含 "H2" 和 "CO"
        h2co_raw = _first_value(rc.get("h2_co_ratio"))
        h2co_val = _parse_ratio(h2co_raw)
        if h2co_val and 0.5 <= h2co_val <= 4:
            _add("reaction_conditions", "unassigned", h2co_val,
                 None, "H2/CO ratio = syngas feed ratio")

        # time_on_stream
        tos_raw = _first_value(rc.get("time_on_stream"))
        tos_val = _first_number(tos_raw)
        if tos_val and 1 <= tos_val <= 1000:
            _add("reaction_conditions", "time_on_stream", tos_val,
                 "h", "time on stream")

    # ── 3b. performance 阶段 ──
    perf_stage = extraction_results.get("performance", {})
    perf_records = perf_stage.get("performance_records", [])
    for rec in perf_records:
        metric = str(rec.get("metric", "")).lower()
        species = str(rec.get("species_or_range", "") or "").lower()
        val = rec.get("value")
        unit = rec.get("unit")
        page = 1
        prov = rec.get("provenance", {})
        if isinstance(prov, dict) and prov.get("page"):
            p = prov["page"]
            page = p if isinstance(p, int) else (p[0] if isinstance(p, list) and p else 1)

        try:
            val = float(val)
        except (TypeError, ValueError):
            continue  # 跳过非数值（如 stability 描述）

        if metric == "conversion":
            if "co2" in species:
                if 0 <= val <= 100:
                    _add("performance", "co2_conversion", val, unit or "%",
                         "CO2 conversion", page)
            else:
                if 0 <= val <= 100:
                    _add("performance", "co_conversion", val, unit or "%",
                         "CO conversion", page)
        elif metric == "selectivity":
            if "c5" in species:
                if 0 <= val <= 100:
                    _add("performance", "selectivity", val, unit or "%",
                         "C5+ selectivity", page)
            elif "ch4" in species or "methane" in species:
                if 0 <= val <= 100:
                    _add("performance", "selectivity", val, unit or "%",
                         "CH4 selectivity", page)
            elif "c8" in species or "c8-c16" in species or "kerosene" in species:
                if 0 <= val <= 100:
                    _add("performance", "selectivity", val, unit or "%",
                         "C8-C16 selectivity", page)
            elif "liquid" in species:
                if 0 <= val <= 100:
                    _add("performance", "selectivity", val, unit or "%",
                         "liquid hydrocarbon selectivity", page)
            elif "jet" in species:
                if 0 <= val <= 100:
                    _add("performance", "selectivity", val, unit or "%",
                         "jet-fuel-range selectivity", page)
            elif "co2" in species:
                if 0 <= val <= 100:
                    _add("performance", "selectivity", val, unit or "%",
                         "CO2 selectivity", page)
            elif "c2" in species or "c2-c4" in species:
                if 0 <= val <= 100:
                    _add("performance", "selectivity", val, unit or "%",
                         "C2-C4 selectivity", page)
            else:
                # 其他选择性也记录，context 含 species 关键词
                if 0 <= val <= 100 and species:
                    _add("performance", "selectivity", val, unit or "%",
                         f"{species} selectivity", page)
        elif metric == "yield":
            if 0 <= val <= 100:
                ctx = f"{species} yield" if species else "yield"
                _add("performance", "yield", val, unit or "%", ctx, page)
        elif metric == "sty":
            if val > 0:
                _add("performance", "sty", val, unit or "g/(gcat·h)",
                     "space-time yield", page)
        elif metric == "productivity":
            if val > 0:
                _add("performance", "productivity", val, unit or "g/(gcat·h)",
                     "productivity", page)
        elif metric == "ratio":
            if val > 0:
                ctx = f"{species} ratio" if species else "olefin/paraffin ratio"
                _add("performance", "ratio", val, None, ctx, page)
        elif metric == "stability":
            if 0 <= val <= 100:
                _add("performance", "stability", val, unit or "%",
                     f"{species} stability" if species else "stability", page)

    # ── 3c. catalyst 阶段（loading / BET / particle_size）──
    cat_stage = extraction_results.get("catalyst", {})
    catalysts = cat_stage.get("catalysts", [])
    for cat in catalysts:
        # loading
        loading_list = cat.get("loading")
        if isinstance(loading_list, list):
            for ld in loading_list:
                if isinstance(ld, dict):
                    ld_val = _first_number(ld.get("value"))
                    ld_unit = ld.get("unit", "wt%")
                    if ld_val and 0.1 <= ld_val <= 50:
                        _add("catalyst", "loading", ld_val, ld_unit,
                             "active metal loading (wt%)")
        elif isinstance(loading_list, dict):
            ld_val = _first_number(loading_list.get("value"))
            if ld_val and 0.1 <= ld_val <= 50:
                _add("catalyst", "loading", ld_val,
                     loading_list.get("unit", "wt%"),
                     "active metal loading (wt%)")

    # ── 3d. provenance_confidence 阶段（丰富数据）──
    prov_stage = extraction_results.get("provenance_confidence", {})
    prov_records = prov_stage.get("provenance_records", [])
    for rec in prov_records:
        target_field = rec.get("target_field")
        target_stage = rec.get("target_stage")
        if not target_field or target_field in _NON_NUMERIC_FIELDS:
            continue

        # 从 evidence_text 提取数值（传入 unit 提高准确性）
        evidence_text = rec.get("evidence_text", "")
        unit = rec.get("unit")
        val = _extract_number_from_text(evidence_text, unit)
        if val is None:
            continue

        page = rec.get("page", 1)
        if isinstance(page, list):
            page = page[0] if page else 1

        # field_family 映射
        field_family_map = {
            "reaction_conditions": "reaction_conditions",
            "performance": "performance",
            "catalyst": "catalyst",
            "characterization": "characterization",
        }
        field_family = field_family_map.get(target_stage, target_stage or "performance")

        # metric_hint 直接用 target_field（rich 函数会聚合）
        _add(field_family, target_field, val, unit,
             f"{target_field}: {evidence_text}", page)

    return rows


# ════════════════════════════════════════════════════
# 预览函数（供 app27.py 预览用，不写库）
# ════════════════════════════════════════════════════
def build_preview_row(
    paper_id: str,
    sha256: str,
    file_name: str,
    extraction_results: Dict[str, Any],
) -> Dict[str, Any]:
    """从抽取结果构建一行预览数据（和 parquet 核心列对齐）"""
    row = {
        "paper_id": paper_id,
        "pdf_sha256": sha256,
        "source_file": file_name,
        "doi": None, "paper_title": None, "year": None,
        "metadata_journal": None,
        "catalyst_name_normalized": None,
        "active_metal": None, "support": None, "support_type": None,
        "active_metal_loading_wt_pct": None,
        "reaction_temperature_C": None, "reaction_pressure_bar": None,
        "GHSV_h_per_g": None, "time_on_stream_h": None, "H2_CO_ratio": None,
        "CO_conversion_pct": None, "CO2_conversion_pct": None,
        "C5plus_selectivity_pct": None, "CH4_selectivity_pct": None,
        "yield_pct": None,
    }

    # metadata
    meta = extraction_results.get("metadata", {}).get("metadata", {})
    row["doi"] = _first_value(meta.get("doi"))
    row["paper_title"] = _first_value(meta.get("title"))
    row["year"] = _first_value(meta.get("year"))
    row["metadata_journal"] = _first_value(meta.get("journal"))

    # catalyst
    cat = extraction_results.get("catalyst", {}).get("catalysts", [])
    if cat:
        c0 = cat[0]
        active_metal = _first_value(c0.get("active_metal"))
        row["active_metal"] = active_metal
        row["support"] = _first_value(c0.get("support"))
        loading = _first_value(c0.get("loading"))
        if loading is not None:
            try:
                row["active_metal_loading_wt_pct"] = float(loading)
            except (TypeError, ValueError):
                pass
        if active_metal and row["support"]:
            row["catalyst_name_normalized"] = f"{active_metal} on {row['support']}"
        elif active_metal:
            row["catalyst_name_normalized"] = active_metal

    # reaction_conditions
    rc = extraction_results.get("reaction_conditions", {}).get("reaction_conditions", [])
    if rc:
        c0 = rc[0]
        row["reaction_temperature_C"] = _first_number(_first_value(c0.get("temperature")))
        row["reaction_pressure_bar"] = _first_number(_first_value(c0.get("pressure")))
        sv = c0.get("space_velocity")
        if sv:
            row["GHSV_h_per_g"] = _first_number(_first_value(sv))
        h2co = _first_value(c0.get("h2_co_ratio"))
        row["H2_CO_ratio"] = _parse_ratio(h2co)
        tos = _first_value(c0.get("time_on_stream"))
        row["time_on_stream_h"] = _first_number(tos)

    # performance
    perf = extraction_results.get("performance", {}).get("performance_records", [])
    co_conv, co2_conv, c5, ch4, yld = [], [], [], [], []
    for rec in perf:
        metric = str(rec.get("metric", "")).lower()
        species = str(rec.get("species_or_range", "") or "").lower()
        val = rec.get("value")
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue
        if metric == "conversion":
            if "co2" in species:
                co2_conv.append(val)
            else:
                co_conv.append(val)
        elif metric == "selectivity":
            if "c5" in species:
                c5.append(val)
            elif "ch4" in species or "methane" in species:
                ch4.append(val)
        elif metric == "yield":
            yld.append(val)

    if co_conv:
        row["CO_conversion_pct"] = max(co_conv)
    if co2_conv:
        row["CO2_conversion_pct"] = max(co2_conv)
    if c5:
        row["C5plus_selectivity_pct"] = max(c5)
    if ch4:
        row["CH4_selectivity_pct"] = max(ch4)
    if yld:
        row["yield_pct"] = max(yld)

    return row


# ════════════════════════════════════════════════════
# 直接追加到 parquet（不经过 SQLite）
# ════════════════════════════════════════════════════
def append_to_parquet(
    paper_id: str,
    sha256: str,
    file_name: str,
    file_size: int,
    page_count: Optional[int],
    extraction_results: Dict[str, Any],
    parquet_path: Path,
) -> Dict[str, int]:
    """把 LLM 提取结果直接追加到 parquet（不写 SQLite）。

    - 核心列由 build_preview_row 填充
    - 统计量列（xxx_max/mean/min/count/std）由 _build_numeric_observations 填充
    - 缺失列补 NaN，只保留 parquet 已有列
    """
    now = _now_iso()

    # 1. 构建核心列
    row = build_preview_row(paper_id, sha256, file_name, extraction_results)

    # 2. 构建统计量列（每个数值生成 max=mean=min=值, count=1, std=0）
    numeric_obs = _build_numeric_observations(paper_id, extraction_results, now)
    for obs in numeric_obs:
        col_base = f"{obs['field_family']}_{obs['metric_hint']}"
        val = obs["normalized_value"]
        if val is not None:
            row[f"{col_base}_max"] = val
            row[f"{col_base}_mean"] = val
            row[f"{col_base}_min"] = val
            row[f"{col_base}_count"] = 1
            row[f"{col_base}_std"] = 0.0

    # 3. 读旧 parquet，追加新行
    df_old = pd.read_parquet(parquet_path)
    df_new = pd.DataFrame([row])

    # 关键：确保 pdf_sha256 和 source_file 在最终 parquet 中
    # （旧 parquet 可能没有这两列，需要主动保留）
    final_columns = list(df_old.columns)
    for must_have in ["pdf_sha256", "source_file"]:
        if must_have not in final_columns:
            final_columns.append(must_have)

    # 为 df_old 补缺失的必须列
    for must_have in ["pdf_sha256", "source_file"]:
        if must_have not in df_old.columns:
            df_old[must_have] = None

    # 为 df_new 补 parquet 已有列中缺失的
    for col in df_old.columns:
        if col not in df_new.columns:
            df_new[col] = None
    # 为 df_new 补它自己有但 df_old 没有的必须列
    for must_have in ["pdf_sha256", "source_file"]:
        if must_have not in df_new.columns and must_have in row:
            df_new[must_have] = row[must_have]

    df_new = df_new[final_columns]
    df_old = df_old[final_columns]

    # 删除旧 paper_id 的行（覆盖模式），再追加
    df_old = df_old[df_old["paper_id"] != paper_id]

    # ══════════════════════════════════════════════════════════════
    #  逐列类型对齐（修复 pyarrow.lib.ArrowInvalid）
    #
    #  ⚠️ 核心原则：只修改 df_new（待入库的 1 行），绝不改写 df_old（历史数据）的
    #  值和类型。历史 parquet 是什么样就保留什么样，新行主动去兼容旧列。
    # ══════════════════════════════════════════════════════════════
    import pyarrow as pa
    import pyarrow.parquet as pq

    # 先把新行里的非标量（list/dict）强行转 JSON 字符串，避免 pyarrow 无法推断
    for col in final_columns:
        new_vals = df_new[col].tolist()
        cleaned = []
        for v in new_vals:
            if v is None or (isinstance(v, float) and pd.isna(v)):
                cleaned.append(None)
            elif isinstance(v, (list, dict)):
                try:
                    cleaned.append(json.dumps(v, ensure_ascii=False))
                except Exception:
                    cleaned.append(str(v))
            else:
                cleaned.append(v)
        df_new[col] = cleaned

    # 逐列判断旧列的数据类型，只把新行的值转成与旧列兼容的类型
    for col in final_columns:
        old_series = df_old[col]
        new_series = df_new[col]
        old_has_data = not (old_series.isna().all())
        new_has_data = not (new_series.isna().all())

        if not new_has_data:
            # 新行本列为空 → 无需处理，保留 None/NA 即可
            continue

        # 依据旧列的真实值推断目标类型（比 trust pandas dtype 更稳）
        target_dtype = None
        if old_has_data:
            old_nonnull = old_series.dropna().tolist()
            all_bool = all(isinstance(v, (bool, np.bool_)) for v in old_nonnull)
            all_int = all(isinstance(v, (int, np.integer)) and not all_bool for v in old_nonnull)
            all_float = all(isinstance(v, (int, float)) and not isinstance(v, (bool, np.bool_))
                            for v in old_nonnull)
            all_str = all(isinstance(v, str) for v in old_nonnull)
            if all_bool:
                target_dtype = "boolean"
            elif all_int:
                target_dtype = "Int64"
            elif all_float:
                target_dtype = "Float64"
            elif all_str:
                target_dtype = "string"
            else:
                # 旧列是混合类型 → 把新行这列转字符串，保证能与旧列 concat
                target_dtype = "string"
        else:
            # 旧列全为 NULL（pyarrow 的 null_type）→ 按新行值推断一个干净类型
            new_nonnull = new_series.dropna().tolist()
            all_bool = all(isinstance(v, (bool, np.bool_)) for v in new_nonnull)
            all_int = all(isinstance(v, (int, np.integer)) and not all_bool for v in new_nonnull)
            all_float = all(isinstance(v, (int, float)) and not isinstance(v, (bool, np.bool_))
                            for v in new_nonnull)
            all_str = all(isinstance(v, str) for v in new_nonnull)
            if all_bool:
                target_dtype = "boolean"
            elif all_int:
                target_dtype = "Int64"
            elif all_float:
                target_dtype = "Float64"
            elif all_str:
                target_dtype = "string"
            else:
                target_dtype = "string"

        # ⚠️ 只对新行做类型转换；df_old 原封不动
        def _coerce_new(series: pd.Series, dtype: str) -> pd.Series:
            """只针对待入库的一行做安全类型转换；失败时回退为 None，绝不影响旧数据。"""
            if dtype == "boolean":
                out = []
                for v in series.tolist():
                    if v is None or (isinstance(v, float) and pd.isna(v)):
                        out.append(pd.NA)
                    elif isinstance(v, bool) or isinstance(v, (np.bool_,)):
                        out.append(bool(v))
                    elif isinstance(v, str):
                        vl = v.strip().lower()
                        if vl in ("true", "1", "yes", "y", "on"):
                            out.append(True)
                        elif vl in ("false", "0", "no", "n", "off", ""):
                            out.append(False if vl else pd.NA)
                        else:
                            out.append(pd.NA)
                    else:
                        try:
                            out.append(bool(int(float(v))))
                        except Exception:
                            out.append(pd.NA)
                return pd.Series(out, index=series.index, dtype="boolean")

            if dtype == "Int64":
                num = pd.to_numeric(series, errors="coerce")
                return num.round().astype("Int64")

            if dtype == "Float64":
                num = pd.to_numeric(series, errors="coerce")
                return num.astype("Float64")

            if dtype == "string":
                out = []
                for v in series.tolist():
                    if v is None or (isinstance(v, float) and pd.isna(v)):
                        out.append(None)
                    elif isinstance(v, (list, dict)):
                        try:
                            out.append(json.dumps(v, ensure_ascii=False))
                        except Exception:
                            out.append(str(v))
                    else:
                        out.append(str(v))
                return pd.Series(out, index=series.index, dtype="object")

            return series

        df_new[col] = _coerce_new(df_new[col], target_dtype)

    df_combined = pd.concat([df_old, df_new], ignore_index=True)

    # 最后一道保险：写入时出错，绝不改写历史数据
    try:
        df_combined.to_parquet(parquet_path, index=False)
    except (pa.ArrowInvalid, pa.ArrowTypeError, TypeError) as _write_err:
        # 终极降级：仍然保持 df_old 原封不动，只把新行的所有列安全字符串化后再拼接写盘
        for col in final_columns:
            s = df_new[col].astype(object).where(df_new[col].notna(), None)
            out = []
            for v in s.tolist():
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    out.append(None)
                elif isinstance(v, (list, dict)):
                    try:
                        out.append(json.dumps(v, ensure_ascii=False))
                    except Exception:
                        out.append(str(v))
                else:
                    out.append(str(v))
            df_new[col] = pd.Series(out, index=df_new.index, dtype="object")
        df_combined_safe = pd.concat([df_old, df_new], ignore_index=True)
        df_combined_safe.to_parquet(parquet_path, index=False)

    return {"appended": 1, "total_rows": len(df_old) + 1}

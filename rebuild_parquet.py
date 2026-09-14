"""
rebuild_parquet.py
从 sqlite 的 formulations + numeric_observations 提取清洗数据，
用 Crossref API 补元数据，生成 parquet + CSV 供前端读取。

用法: python rebuild_parquet.py
"""
from __future__ import annotations

import sqlite3
import json
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

# ════════════════════════════════════════════════════
# 配置
# ════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "fts_evidence_lake.sqlite"
OUTPUTS_DIR = BASE_DIR / "outputs"
PARQUET_PATH = OUTPUTS_DIR / "FT_SAF_catalyst_extraction_wide_table.parquet"
CSV_PATH = OUTPUTS_DIR / "extractions_long.csv"
CACHE_PATH = OUTPUTS_DIR / "crossref_cache.json"

OUTPUTS_DIR.mkdir(exist_ok=True)


# ════════════════════════════════════════════════════
# 第 0 步：从 papers 表提取所有论文作为基底（4067 篇）
# ════════════════════════════════════════════════════
def extract_papers(con):
    """从 papers 表提取所有论文 ID 作为基底，确保 4067 篇全覆盖
    含 LLM 提取的 doi/title/year/journal/authors（新列，旧数据为 NULL）
    """
    df = pd.read_sql("""
        SELECT DISTINCT paper_id, pdf_sha256, source_file,
               doi, title, year, journal, authors
        FROM papers
    """, con)
    # 重命名以和 parquet 列对齐
    df = df.rename(columns={
        "title": "paper_title",
        "journal": "metadata_journal",
    })
    return df


# ════════════════════════════════════════════════════
# 第 1 步：从 formulations 表提取催化剂信息
# ════════════════════════════════════════════════════
def extract_formulations(con):
    """从 formulations 表提取催化剂基础信息（含 LLM 提取的 promoter/calcination/reduction）"""
    df = pd.read_sql("""
        SELECT
            paper_id,
            formulation_id,
            catalyst_name_normalized,
            catalyst_name_raw,
            catalyst_family,
            support,
            support_type,
            promoter,
            preparation_method,
            calcination_temperature,
            calcination_time,
            calcination_atmosphere,
            reduction_temperature,
            reduction_time,
            reduction_atmosphere
        FROM formulations
    """, con)

    # 派生 active_metal（从 catalyst_name_normalized 取第一个金属）
    # 例如 "Fe/Cu promoted by K/Mn/Zn on SiO2" → "Fe"
    _NON_METAL_WORDS = {"promoted", "on", "by", "the", "with", "and", "via", "using", "supported"}

    def _first_metal(name):
        if pd.isna(name):
            return None
        # 逐段检查 "/" 分隔的每一段，找到第一个真正的金属
        for part in str(name).split("/"):
            part = part.strip()
            # 只取第一段里的首字母词
            m = re.match(r"[A-Za-z]+", part)
            if not m:
                continue
            word = m.group(0).lower()
            if word in _NON_METAL_WORDS:
                continue
            return m.group(0)
        return None

    df["active_metal"] = df["catalyst_name_normalized"].apply(_first_metal)

    # 派生 support_primary 和 support_type_primary（取第一个，避免多值组合）
    df["support_primary"] = df["support"].apply(
        lambda x: str(x).split(";")[0].strip() if pd.notna(x) and str(x).strip() else None
    )
    df["support_type_primary"] = df["support_type"].apply(
        lambda x: str(x).split(";")[0].strip() if pd.notna(x) and str(x).strip() else None
    )
    return df


# ════════════════════════════════════════════════════
# 第 2 步：从 numeric_observations 清洗提取数值
# ════════════════════════════════════════════════════
def extract_numeric_data(con):
    """直接从 numeric_observations 提取，跳过三张空表，用范围过滤清洗噪音"""

    # 2.1 反应条件（温度/压力/GHSV/时长）
    #     温度在 characterization 类（reaction_conditions 没有 temperature hint）
    #     H2/CO 从 context 关键词提取
    conditions = pd.read_sql("""
        SELECT paper_id,
            -- 温度：从 characterization 类提取，用 context 过滤反应温度
            MAX(CASE
                WHEN metric_hint='temperature'
                 AND normalized_value BETWEEN 100 AND 600
                 AND context NOT LIKE '%[%'
                 AND context NOT LIKE '%calcination%'
                 AND context NOT LIKE '%calcined%'
                 AND context NOT LIKE '%reduction%'
                 AND context NOT LIKE '%reduced%'
                 AND (context LIKE '%reaction%' OR context LIKE '%reactor%'
                      OR context LIKE '%FTS%' OR context LIKE '%Fischer%'
                      OR context LIKE '%performed at%' OR context LIKE '%conducted at%')
                THEN normalized_value
            END) as reaction_temperature_C,

            -- 温度备选：从 reaction_conditions 的 unassigned 里找
            MAX(CASE
                WHEN metric_hint='unassigned'
                 AND normalized_value BETWEEN 100 AND 600
                 AND context NOT LIKE '%[%'
                 AND (context LIKE '%°C%' OR context LIKE '%K%'
                      OR context LIKE '%temperature%')
                 AND (context LIKE '%reaction%' OR context LIKE '%reactor%'
                      OR context LIKE '%performed at%' OR context LIKE '%conducted at%')
                THEN normalized_value
            END) as reaction_temperature_C_alt,

            MAX(CASE
                WHEN metric_hint='pressure'
                 AND normalized_value BETWEEN 0.1 AND 100
                 AND context NOT LIKE '%[%'
                THEN normalized_value
            END) as reaction_pressure_bar,

            MAX(CASE
                WHEN metric_hint='ghsv'
                 AND normalized_value BETWEEN 1 AND 100000
                THEN normalized_value
            END) as GHSV_h_per_g,

            MAX(CASE
                WHEN metric_hint='time_on_stream'
                 AND normalized_value BETWEEN 1 AND 1000
                THEN normalized_value
            END) as time_on_stream_h
        FROM numeric_observations
        WHERE field_family IN ('reaction_conditions', 'characterization')
        GROUP BY paper_id
    """, con)

    # 合并两个温度列（优先用主温度，备选兜底）
    conditions["reaction_temperature_C"] = conditions["reaction_temperature_C"].fillna(
        conditions["reaction_temperature_C_alt"]
    )
    conditions = conditions.drop(columns=["reaction_temperature_C_alt"])

    # 2.1b H2/CO 比例：从所有类的 context 里提取
    h2co = pd.read_sql("""
        SELECT paper_id,
            MAX(CASE
                WHEN normalized_value BETWEEN 0.5 AND 4
                 AND context NOT LIKE '%[%'
                 AND (context LIKE '%H2/CO%'
                      OR context LIKE '%H2/CO ratio%'
                      OR context LIKE '%H₂/CO%'
                      OR context LIKE '%H2 to CO%'
                      OR context LIKE '%syngas ratio%')
                THEN normalized_value
            END) as H2_CO_ratio
        FROM numeric_observations
        WHERE context LIKE '%H2%CO%' OR context LIKE '%H₂%CO%'
        GROUP BY paper_id
    """, con)

    conditions = conditions.merge(h2co, on="paper_id", how="left")

    # 2.2 性能数据（转化率/选择性）
    performance = pd.read_sql("""
        SELECT paper_id,
            MAX(CASE
                WHEN metric_hint='co_conversion'
                 AND normalized_value BETWEEN 0 AND 100
                 AND context NOT LIKE '%[%'
                THEN normalized_value
            END) as CO_conversion_pct,

            MAX(CASE
                WHEN metric_hint='co2_conversion'
                 AND normalized_value BETWEEN 0 AND 100
                 AND context NOT LIKE '%[%'
                THEN normalized_value
            END) as CO2_conversion_pct,

            MAX(CASE
                WHEN metric_hint='selectivity'
                 AND context LIKE '%C5%'
                 AND normalized_value BETWEEN 0 AND 100
                 AND context NOT LIKE '%[%'
                THEN normalized_value
            END) as C5plus_selectivity_pct,

            MAX(CASE
                WHEN metric_hint='selectivity'
                 AND context LIKE '%CH4%'
                 AND normalized_value BETWEEN 0 AND 100
                 AND context NOT LIKE '%[%'
                THEN normalized_value
            END) as CH4_selectivity_pct,

            MAX(CASE
                WHEN metric_hint='yield'
                 AND normalized_value BETWEEN 0 AND 100
                 AND context NOT LIKE '%[%'
                THEN normalized_value
            END) as yield_pct
        FROM numeric_observations
        WHERE field_family='performance'
        GROUP BY paper_id
    """, con)

    # 2.3 催化剂表征数据（负载量/BET/粒径）
    characterization = pd.read_sql("""
        SELECT paper_id,
            MAX(CASE
                WHEN metric_hint='loading'
                 AND normalized_value BETWEEN 0.1 AND 50
                THEN normalized_value
            END) as active_metal_loading_wt_pct,

            MAX(CASE
                WHEN metric_hint='surface_area'
                 AND normalized_value BETWEEN 1 AND 1000
                THEN normalized_value
            END) as BET_surface_area_m2_g,

            MAX(CASE
                WHEN metric_hint='particle_size'
                 AND normalized_value BETWEEN 0.5 AND 100
                THEN normalized_value
            END) as metal_particle_size_nm
        FROM numeric_observations
        WHERE field_family IN ('catalyst', 'characterization')
        GROUP BY paper_id
    """, con)

    # 2.4 从 context 里提取 promoter_elements（助剂元素）
    promoters = pd.read_sql("""
        SELECT paper_id,
            MAX(CASE
                WHEN context LIKE '%promoted by%'
                THEN context
            END) as promoter_context
        FROM numeric_observations
        WHERE field_family='catalyst'
          AND context LIKE '%promoted by%'
        GROUP BY paper_id
    """, con)

    # 从 catalyst_name_normalized 提取 promoter（更可靠）
    # 例如 "Fe/Cu promoted by K/Mn/Zn on SiO2" → "K/Mn/Zn"
    def _extract_promoters(name):
        if pd.isna(name):
            return None
        m = re.search(r"promoted by ([\w/]+)", str(name))
        return m.group(1) if m else None

    # 合并所有数值数据
    result = conditions.merge(performance, on="paper_id", how="outer")
    result = result.merge(characterization, on="paper_id", how="outer")
    result = result.merge(promoters[["paper_id"]], on="paper_id", how="outer")

    return result


# ════════════════════════════════════════════════════
# 第 2b 步：从 numeric_observations 提取所有已分类数据的统计量（丰富数据点）
# ════════════════════════════════════════════════════
def extract_numeric_data_rich(con):
    """从 numeric_observations 提取所有 field_family × metric_hint 组合的统计量
    每种组合生成 5 列（max/mean/min/count/std），共 81×5=405 列
    """
    df = pd.read_sql("""
        SELECT paper_id, field_family, metric_hint, normalized_value
        FROM numeric_observations
        WHERE field_family != 'raw_evidence'
          AND normalized_value IS NOT NULL
    """, con)

    if df.empty:
        return pd.DataFrame({"paper_id": []})

    # 按 paper_id × field_family × metric_hint 分组，计算统计量
    grouped = df.groupby(["paper_id", "field_family", "metric_hint"])["normalized_value"].agg(
        ["max", "mean", "min", "count", "std"]
    ).reset_index()

    # 透视成宽表：列名 = field_family_metric_hint_stat
    grouped["col_name"] = grouped["field_family"] + "_" + grouped["metric_hint"]
    pivot = grouped.pivot(index="paper_id", columns="col_name",
                          values=["max", "mean", "min", "count", "std"])
    # 扁平化多级列名
    pivot.columns = [f"{c[1]}_{c[0]}" for c in pivot.columns]
    pivot = pivot.reset_index()

    print(f"  丰富数据: {len(pivot)} 篇论文, {len(pivot.columns)} 列（含 paper_id）")
    return pivot


# ════════════════════════════════════════════════════
# 第 3 步：从 numeric_observations 的 context 提取 DOI
# ════════════════════════════════════════════════════
def extract_dois(con):
    """从 numeric_observations 的 context 字段里正则提取 DOI"""
    # DOI 格式: 10.xxxx/xxx（后面可能有空格或标点）
    doi_pattern = re.compile(r"10\.\d{4,9}/[^\s,;\"'\]>]+", re.IGNORECASE)

    rows = con.execute("""
        SELECT DISTINCT paper_id, context
        FROM numeric_observations
        WHERE context LIKE '%10.%/%'
    """).fetchall()

    paper_to_doi = {}
    for paper_id, context in rows:
        if paper_id in paper_to_doi:
            continue
        m = doi_pattern.search(str(context))
        if m:
            doi = m.group(0).rstrip(").,;]")
            paper_to_doi[paper_id] = doi
    return paper_to_doi


# ════════════════════════════════════════════════════
# 第 4 步：从 papers 表的 source_file 提取年份和标题（Crossref 失败的备选）
# ════════════════════════════════════════════════════
# 文件名格式: Author_Year_Title_hash.pdf  例如 Aad_2017_Inhibition_by_..._6c59fa362f.pdf
_FILENAME_RE = re.compile(
    r"^(?P<author>[A-Za-z][\w-]*?)_(?P<year>19\d{2}|20\d{2})_(?P<title>.+?)_(?P<hash>[0-9a-f]{8,12})\.pdf$",
    re.IGNORECASE,
)


def extract_metadata_from_filename(con):
    """从 PDF 文件名里提取年份和标题（如 Aad_2017_Inhibition_by_..._6c59fa362f.pdf）"""
    rows = con.execute("SELECT paper_id, source_file FROM papers").fetchall()
    result = {}
    for paper_id, source_file in rows:
        entry = {"year": None, "title": None}
        fname = str(source_file)
        m = _FILENAME_RE.match(fname)
        if m:
            entry["year"] = int(m.group("year"))
            # 标题中的 _ 替换为空格
            entry["title"] = m.group("title").replace("_", " ").strip()
        else:
            # 兜底：只提取 4 位年份
            ym = re.search(r"(?:^|_)(19\d{2}|20\d{2})(?:_|-|\.)", fname)
            if ym:
                entry["year"] = int(ym.group(1))
        if entry["year"] or entry["title"]:
            result[paper_id] = entry
    return result


# ════════════════════════════════════════════════════
# 第 5 步：用 Crossref API 补元数据（带缓存）
# ════════════════════════════════════════════════════
def load_cache():
    if CACHE_PATH.exists():
        try:
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache):
    try:
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  ⚠️ 缓存保存失败: {e}")


def fetch_crossref(doi, cache):
    """用 DOI 调 Crossref API 拿元数据，带缓存"""
    if doi in cache:
        return cache[doi]

    try:
        url = f"https://api.crossref.org/works/{doi}"
        r = requests.get(url, timeout=15,
                         headers={"User-Agent": "SAF-Platform/1.0 (mailto:research@example.com)"})
        if r.status_code == 200:
            data = r.json()["message"]
            # 提取年份（可能有多种字段）
            year = None
            for date_field in ["published", "published-print", "published-online", "issued"]:
                if date_field in data:
                    parts = data[date_field].get("date-parts", [[None]])
                    if parts and parts[0]:
                        year = parts[0][0]
                        break

            result = {
                "title": data.get("title", [""])[0] if data.get("title") else None,
                "year": year,
                "journal": data.get("container-title", [""])[0] if data.get("container-title") else None,
                "publisher": data.get("publisher"),
            }
        else:
            result = {"title": None, "year": None, "journal": None, "publisher": None}
    except Exception as e:
        print(f"  ⚠️ Crossref 查询失败 {doi}: {e}")
        result = {"title": None, "year": None, "journal": None, "publisher": None}

    cache[doi] = result
    return result


def enrich_with_crossref(df, doi_mapping, filename_meta, max_queries=None):
    """批量补元数据，Crossref 失败/无 DOI 时用文件名兜底 year 和 title"""
    cache = load_cache()
    total = len(doi_mapping)
    queried = 0

    print(f"  Crossref 需查询: {total} 篇")

    # 添加列（如果 papers 表已有值则保留，不覆盖）
    if "paper_title" not in df.columns:
        df["paper_title"] = None
    if "year" not in df.columns:
        df["year"] = None
    if "metadata_journal" not in df.columns:
        df["metadata_journal"] = None
    if "metadata_publisher" not in df.columns:
        df["metadata_publisher"] = None
    df["metadata_access_route"] = None  # 从 folder_group 推断

    for idx, row in df.iterrows():
        paper_id = row["paper_id"]
        doi = doi_mapping.get(paper_id)

        if doi:
            if max_queries is not None and queried >= max_queries:
                # 达到查询上限，用缓存或文件名兜底
                meta = cache.get(doi, {"title": None, "year": None, "journal": None})
            else:
                meta = fetch_crossref(doi, cache)
                queried += 1
                if queried % 50 == 0:
                    print(f"    已查询 {queried}/{total}...")
                    save_cache(cache)
                time.sleep(0.5)  # 限速

            # 只在 papers 表没有值时才用 Crossref 补
            if pd.isna(df.at[idx, "paper_title"]) or df.at[idx, "paper_title"] is None:
                df.at[idx, "paper_title"] = meta.get("title")
            if (pd.isna(df.at[idx, "year"]) or df.at[idx, "year"] is None) and meta.get("year"):
                df.at[idx, "year"] = meta["year"]
            if pd.isna(df.at[idx, "metadata_journal"]) or df.at[idx, "metadata_journal"] is None:
                df.at[idx, "metadata_journal"] = meta.get("journal")
            df.at[idx, "metadata_publisher"] = meta.get("publisher")

    save_cache(cache)
    print(f"  Crossref 实际查询: {queried} 篇（缓存命中: {total - queried} 篇）")

    # 统一用文件名元数据兜底所有缺失的 year 和 paper_title
    year_filled = 0
    title_filled = 0
    for idx, row in df.iterrows():
        paper_id = row["paper_id"]
        fmeta = filename_meta.get(paper_id)
        if not fmeta:
            continue
        # year 兜底
        if (pd.isna(df.at[idx, "year"]) or df.at[idx, "year"] is None) and fmeta.get("year"):
            df.at[idx, "year"] = fmeta["year"]
            year_filled += 1
        # paper_title 兜底
        if (pd.isna(df.at[idx, "paper_title"]) or df.at[idx, "paper_title"] is None) and fmeta.get("title"):
            df.at[idx, "paper_title"] = fmeta["title"]
            title_filled += 1
    print(f"  文件名兜底: year +{year_filled}, paper_title +{title_filled}")

    # 过滤异常年份（> 2026 视为错误数据）
    CURRENT_YEAR = 2026
    bad_years = (df["year"].notna()) & (df["year"] > CURRENT_YEAR)
    if bad_years.any():
        print(f"  过滤异常年份: {bad_years.sum()} 篇 (> {CURRENT_YEAR})")
        df.loc[bad_years, "year"] = None

    return df


# ════════════════════════════════════════════════════
# 第 6 步：补 folder_group（用于推断 access_route）
# ════════════════════════════════════════════════════
def enrich_access_route(df, con):
    """从 papers 表的 folder_group 推断 OA/非OA"""
    folder_df = pd.read_sql("SELECT paper_id, folder_group, publisher_group FROM papers", con)
    folder_map = dict(zip(folder_df["paper_id"], folder_df["folder_group"]))
    publisher_map = dict(zip(folder_df["paper_id"], folder_df["publisher_group"]))

    df["metadata_access_route"] = df["paper_id"].map(folder_map)
    df["metadata_publisher"] = df["paper_id"].map(publisher_map)
    # 标准化 access_route
    df["metadata_access_route"] = df["metadata_access_route"].apply(
        lambda x: "OA" if str(x).strip().upper() == "OA" else ("non-OA" if x else None)
    )
    return df


# ════════════════════════════════════════════════════
# 第 7 步：合并 formulations + numeric + 元数据，生成 parquet + CSV
# ════════════════════════════════════════════════════
def main():
    if not DB_PATH.exists():
        print(f"❌ 数据库不存在: {DB_PATH}")
        return

    print(f"📂 连接数据库: {DB_PATH}")
    con = sqlite3.connect(str(DB_PATH))

    # 1. 提取 papers 表作为基底（确保 4067 篇全覆盖）
    print("\n[1/7] 提取 papers 表作为基底...")
    papers_base = extract_papers(con)
    print(f"  ✅ {len(papers_base)} 篇论文（基底）")

    # 2. 提取催化剂信息
    print("\n[2/7] 提取 formulations 表...")
    formulations = extract_formulations(con)
    print(f"  ✅ {len(formulations)} 条催化剂配方")

    # 3. 提取数值数据（清洗后）
    print("\n[3/8] 提取并清洗 numeric_observations...")
    numeric_data = extract_numeric_data(con)
    print(f"  ✅ {len(numeric_data)} 篇论文的数值数据")

    # 3b. 提取丰富的统计量数据（81 种组合 × 5 统计量 = 405 列）
    print("\n[3b/8] 提取 numeric_observations 的丰富统计量...")
    numeric_rich = extract_numeric_data_rich(con)
    print(f"  ✅ {len(numeric_rich)} 篇论文, {len(numeric_rich.columns)-1} 个统计列")

    # 4. 以 papers 为基底左连接 formulations + numeric + rich（保证 4067 篇全覆盖）
    print("\n[4/8] 以 papers 为基底左连接 formulations + numeric + rich...")
    df = papers_base.merge(formulations, on="paper_id", how="left")
    df = df.merge(numeric_data, on="paper_id", how="left")
    df = df.merge(numeric_rich, on="paper_id", how="left")
    print(f"  ✅ 合并后: {len(df)} 行 × {len(df.columns)} 列（应为 {len(papers_base)} 篇）")

    # 5. 从 context 提取 DOI（作为兜底，papers 表已有的 doi 优先）
    print("\n[5/7] 提取 DOI...")
    doi_mapping = extract_dois(con)
    print(f"  ✅ 从 context 找到 {len(doi_mapping)} 篇的 DOI")
    # 优先用 papers 表的 doi，为空时用 context 提取的兜底
    if "doi" not in df.columns:
        df["doi"] = None
    df["doi"] = df["doi"].fillna(df["paper_id"].map(doi_mapping))

    # 从文件名提取年份和标题（备选）
    filename_meta = extract_metadata_from_filename(con)
    year_cnt = sum(1 for v in filename_meta.values() if v.get("year"))
    title_cnt = sum(1 for v in filename_meta.values() if v.get("title"))
    print(f"  ✅ 从文件名提取 {year_cnt} 篇的年份、{title_cnt} 篇的标题")

    # 6. 用 Crossref 补元数据（首次只查 200 篇验证，后续可调大）
    import sys
    max_queries = int(sys.argv[1]) if len(sys.argv) > 1 else 200
    print(f"\n[6/7] 调用 Crossref API 补元数据（最多查询 {max_queries} 篇）...")
    df = enrich_with_crossref(df, doi_mapping, filename_meta, max_queries=max_queries)

    # 补 access_route 和 publisher
    df = enrich_access_route(df, con)

    # 6. 派生 CO_or_CO2_route（从 CO2_conversion 是否存在推断）
    df["CO_or_CO2_route"] = df.apply(
        lambda r: "CO2" if pd.notna(r.get("CO2_conversion_pct")) else "CO",
        axis=1
    )

    # 派生 promoter_elements（从 catalyst_name_normalized 提取）
    def _extract_promoters(name):
        if pd.isna(name):
            return None
        m = re.search(r"promoted by ([\w/]+)", str(name))
        return m.group(1) if m else None
    df["promoter_elements"] = df["catalyst_name_normalized"].apply(_extract_promoters)

    # 7. 重排列，对齐前端期望的列名
    final_cols = [
        "paper_id", "pdf_sha256", "source_file", "doi", "catalyst_name_normalized", "active_metal",
        "active_metal_loading_wt_pct", "support", "support_type",
        "support_primary", "support_type_primary", "promoter_elements",
        "BET_surface_area_m2_g", "metal_particle_size_nm",
        "reaction_temperature_C", "reaction_pressure_bar", "GHSV_h_per_g",
        "time_on_stream_h", "H2_CO_ratio",
        "CO_conversion_pct", "CO2_conversion_pct",
        "C5plus_selectivity_pct", "CH4_selectivity_pct", "yield_pct",
        "CO_or_CO2_route", "year", "paper_title",
        "metadata_journal", "metadata_publisher", "metadata_access_route",
        "catalyst_family", "catalyst_name_raw",
        # LLM 提取的新列（旧数据为 NULL）
        "authors", "promoter", "preparation_method",
        "calcination_temperature", "calcination_time", "calcination_atmosphere",
        "reduction_temperature", "reduction_time", "reduction_atmosphere",
    ]
    # 只保留存在的列（核心列 + rich 统计列）
    final_cols = [c for c in final_cols if c in df.columns]
    # rich 列 = df 中不在 final_cols 的列（统计量列）
    rich_cols = [c for c in df.columns if c not in final_cols]
    df = df[final_cols + rich_cols]

    # 8. 生成 parquet
    print(f"\n[7/7] 生成 parquet + CSV...")
    df.to_parquet(str(PARQUET_PATH), index=False)
    print(f"  ✅ parquet: {PARQUET_PATH}")
    print(f"     {len(df)} 行 × {len(df.columns)} 列")

    # 打印每列的非空数量
    print("\n  各列非空统计:")
    for col in df.columns:
        non_null = df[col].notna().sum()
        pct = non_null / len(df) * 100 if len(df) > 0 else 0
        print(f"    {col:<35} {non_null:>5} / {len(df)}  ({pct:.1f}%)")

    # 9. 生成 CSV（每行一篇论文，列名直接是字段名，供平台总览页读）
    # 前端 load_overview_stats 期望宽表格式，列名如 metadata_year/metadata_publisher
    csv_cols = ["paper_id", "year", "paper_title",
                "metadata_journal", "metadata_publisher", "metadata_access_route",
                "catalyst_name_normalized", "catalyst_family", "support", "active_metal",
                "reaction_temperature_C", "reaction_pressure_bar", "H2_CO_ratio",
                "CO_conversion_pct", "CO2_conversion_pct",
                "C5plus_selectivity_pct", "CH4_selectivity_pct"]
    csv_cols = [c for c in csv_cols if c in df.columns]
    csv_df = df[csv_cols].copy()
    # year 重命名为 metadata_year（前端期望的列名）
    if "year" in csv_df.columns:
        csv_df = csv_df.rename(columns={"year": "metadata_year"})
    # paper_title 重命名为 metadata_title
    if "paper_title" in csv_df.columns:
        csv_df = csv_df.rename(columns={"paper_title": "metadata_title"})
    csv_df.to_csv(str(CSV_PATH), index=False, encoding="utf-8-sig")
    print(f"\n  ✅ CSV: {CSV_PATH}")
    print(f"     {len(csv_df)} 行 × {len(csv_df.columns)} 列（宽表格式）")

    # 验证前端期望的列是否齐全
    print("\n" + "=" * 60)
    print("【前端数据库浏览页期望的列 - 覆盖率验证】")
    print("=" * 60)
    frontend_cols = {
        "catalyst_name_normalized": "催化剂名称",
        "active_metal": "活性金属",
        "active_metal_loading_wt_pct": "负载量",
        "support": "载体",
        "promoter_elements": "助剂",
        "BET_surface_area_m2_g": "BET",
        "metal_particle_size_nm": "粒径",
        "reaction_temperature_C": "温度",
        "reaction_pressure_bar": "压力",
        "H2_CO_ratio": "H2/CO",
        "CO_conversion_pct": "CO转化率",
        "CO2_conversion_pct": "CO2转化率",
        "C5plus_selectivity_pct": "C5+选择性",
        "CH4_selectivity_pct": "CH4选择性",
        "CO_or_CO2_route": "原料气",
        "year": "年份",
        "paper_title": "标题",
    }
    for col, label in frontend_cols.items():
        if col in df.columns:
            non_null = df[col].notna().sum()
            pct = non_null / len(df) * 100 if len(df) > 0 else 0
            status = "✅" if pct > 10 else "⚠️" if pct > 0 else "❌"
            print(f"  {status} {label:<12} ({col}): {non_null:>5} / {len(df)}  ({pct:.1f}%)")
        else:
            print(f"  ❌ {label:<12} ({col}): 列不存在")

    con.close()
    print(f"\n🎉 完成！parquet 已更新，可刷新前端验证。")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""
FTS 证据数据湖 → extractions_long.csv
==========================================================
适用于：核心表(formulation_tests / performance_observations)尚未填充，
        科学数值都还在 numeric_observations 证据层的情况。

数据来源映射：
  stage=metadata            ← papers
  stage=catalyst            ← formulations（若为空则跳过）
  stage=reaction_conditions ← numeric_observations WHERE field_family='reaction_conditions'
  stage=performance         ← numeric_observations WHERE field_family='performance'

排除 raw_evidence（未赋予科学指标的原始数值），否则图上全是噪声。

用法：
    python export_evidence_to_long.py
    python export_evidence_to_long.py D:\\ftweb\\fts_evidence_lake.sqlite

脚本末尾会打印完整诊断（指标分布、归类情况、覆盖论文数），
可据此判断数据质量，不需要另外跑验证脚本。
"""

from __future__ import annotations

import os
import re
import sys
import sqlite3
import pandas as pd

# ============================================================
# 参数区
# ============================================================
DB_PATH = r"D:\ftweb\fts_evidence_lake.sqlite"
OUT_CSV = "extractions_long.csv"

# 每个 stage 最多导出多少行。0 = 不限制。
# 本地建议 0（全量）；要传云端(Streamlit免费版内存1GB)建议设 20000 左右。
MAX_ROWS_PER_STAGE = 0

# 置信度门槛：低于此值的证据不导出。设 0 表示不过滤。
MIN_CONFIDENCE = 0.0


# ============================================================
# 工具
# ============================================================
def table_exists(con, name):
    return con.execute(
        "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone()[0] > 0


def cols_of(con, table):
    return [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]


def pick(df, *names):
    for n in names:
        if n in df.columns:
            return df[n]
    return pd.Series([None] * len(df), index=df.index)


def cap(df, n, label):
    if n and len(df) > n:
        print(f"  [抽样] {label}: {len(df):,} → {n:,} 行")
        return df.sample(n, random_state=42).reset_index(drop=True)
    return df


# ============================================================
# 反应条件：把 metric_hint 归到 temperature / pressure / time_on_stream
# app27 只认这三个字段，其余（GHSV、H2/CO）单独放列，不进条件图但保留信息
# ============================================================
COND_PATTERNS = [
    ("temperature",    r"temp|温度|°c|celsius"),
    ("pressure",       r"press|压力|bar|mpa|atm"),
    ("time_on_stream", r"time.?on.?stream|\btos\b|运行时长|duration|h on stream"),
]
EXTRA_COND = [
    ("space_velocity", r"ghsv|whsv|space.?velocity|sv\b"),
    ("h2_co_ratio",    r"h2\s*/\s*co|h2:co|ratio"),
]


def classify_condition(hint, unit):
    s = f"{hint or ''} {unit or ''}".lower()
    for field, pat in COND_PATTERNS:
        if re.search(pat, s):
            return field
    for field, pat in EXTRA_COND:
        if re.search(pat, s):
            return field
    # 兜底：靠单位判断
    u = (unit or "").lower()
    if "c" in u and "°" in u:
        return "temperature"
    if u in ("bar", "mpa", "atm", "psi"):
        return "pressure"
    if u in ("h", "hr", "hour", "hours"):
        return "time_on_stream"
    return None


def build_conditions(obs):
    """obs: numeric_observations 中 field_family='reaction_conditions' 的行"""
    if obs.empty:
        return pd.DataFrame()

    hint = pick(obs, "metric_hint").astype(str)
    unit = pick(obs, "normalized_unit").fillna(pick(obs, "raw_unit")).astype(str)
    val = pd.to_numeric(pick(obs, "normalized_value"), errors="coerce")

    field = [classify_condition(h, u) for h, u in zip(hint, unit)]
    out = pd.DataFrame({
        "paper_id":      pick(obs, "paper_id"),
        "stage":         "reaction_conditions",
        "condition_id":  pick(obs, "observation_id"),
        "catalyst_ref":  None,
        "page":          pick(obs, "page_number"),
        "evidence_text": pick(obs, "context"),
        "confidence":    pick(obs, "confidence"),
        "metric_hint_raw": hint,
        "_field": field,
        "_val": val,
        "_unit": unit,
    })
    out = out[out["_field"].notna() & out["_val"].notna()]
    if out.empty:
        return pd.DataFrame()

    # 关键：写成 "280 °C" 这种带单位的字符串，app27 才能解析并归一化
    for f in ["temperature", "pressure", "time_on_stream", "space_velocity", "h2_co_ratio"]:
        m = out["_field"] == f
        col = out["_val"].where(m).astype("object")
        if f == "h2_co_ratio":
            out[f] = col                      # 无量纲，直接给数值
        else:
            out[f] = [f"{v} {u}".strip() if pd.notna(v) else None
                      for v, u in zip(col, out["_unit"])]
    return out.drop(columns=["_field", "_val", "_unit"])


def build_performance(obs):
    if obs.empty:
        return pd.DataFrame()
    hint = pick(obs, "metric_hint").astype(str).str.strip()
    unit = pick(obs, "normalized_unit").fillna(pick(obs, "raw_unit"))
    val = pd.to_numeric(pick(obs, "normalized_value"), errors="coerce")

    out = pd.DataFrame({
        "paper_id":         pick(obs, "paper_id"),
        "stage":            "performance",
        "performance_id":   pick(obs, "observation_id"),
        "catalyst_ref":     None,
        "metric":           hint,
        "species_or_range": None,
        "value":            val,
        "unit":             unit,
        "page":             pick(obs, "page_number"),
        "evidence_text":    pick(obs, "context"),
        "confidence":       pick(obs, "confidence"),
    })
    return out[out["value"].notna()]


def build_metadata(papers):
    if papers.empty:
        return pd.DataFrame()
    return pd.DataFrame({
        "paper_id":               pick(papers, "paper_id"),
        "stage":                  "metadata",
        "metadata_title":         pick(papers, "title"),
        "metadata_doi":           pick(papers, "doi"),
        "metadata_journal":       pick(papers, "journal"),
        "metadata_year":          pick(papers, "year"),
        "metadata_authors":       pick(papers, "authors"),
        "metadata_publisher":     pick(papers, "publisher_group"),
        "metadata_access_route":  pick(papers, "access_route"),
        "confidence":             pick(papers, "metadata_confidence"),
    })


def build_catalyst(f):
    if f.empty:
        return pd.DataFrame()
    name = pick(f, "catalyst_name_normalized", "catalyst_name_raw", "formulation_label").astype(str)
    # 从 "Fe/SiO2" 这类归一化名里粗略拆出活性金属
    metals = ["Fe", "Co", "Ru", "Ni", "Cu", "Mo", "Mn", "Zn", "Pd", "Pt", "Rh"]
    def guess_metal(s):
        for m in metals:
            if re.search(rf"\b{m}\b", str(s)):
                return m
        return None
    return pd.DataFrame({
        "paper_id":        pick(f, "paper_id"),
        "stage":           "catalyst",
        "catalyst_id":     pick(f, "formulation_id"),
        "catalyst_name":   name,
        "active_metal":    name.apply(guess_metal),
        "support":         pick(f, "support"),
        "support_type":    pick(f, "support_type"),
        "catalyst_family": pick(f, "catalyst_family"),
        "promoter":        None,
        "preparation_method": None,
        "confidence":      pick(f, "formulation_confidence"),
        "page":            pick(f, "source_page"),
    })


# ============================================================
# 诊断：把 metric 归类情况打出来（内建，不用单独跑验证脚本）
# ============================================================
METRIC_RULES = [
    ("STY", ["sty", "space time yield", "space-time yield"]),
    ("productivity", ["productivity"]),
    ("yield", ["yield"]),
    ("selectivity", ["selectivity", "选择性"]),
    ("conversion", ["conversion", "转化率"]),
]


def categorize(m):
    s = str(m).lower()
    for cat, kws in METRIC_RULES:
        if any(k in s for k in kws):
            return cat
    return "其他"


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    if not os.path.exists(db):
        print(f"[错误] 数据库不存在：{db}")
        sys.exit(1)

    print(f"[连接] {db}  ({os.path.getsize(db)/1024**3:.2f} GB)\n")
    con = sqlite3.connect(db)

    conf_sql = f" AND confidence >= {MIN_CONFIDENCE}" if MIN_CONFIDENCE > 0 else ""

    print("读取数据（排除 raw_evidence）：")
    papers = pd.read_sql("SELECT * FROM papers", con) if table_exists(con, "papers") else pd.DataFrame()
    print(f"  papers                 {len(papers):>10,} 行")

    forms = pd.read_sql("SELECT * FROM formulations", con) if table_exists(con, "formulations") else pd.DataFrame()
    print(f"  formulations           {len(forms):>10,} 行")

    perf_obs = pd.read_sql(
        f"SELECT * FROM numeric_observations WHERE field_family='performance'{conf_sql}", con)
    print(f"  performance 证据       {len(perf_obs):>10,} 行")

    cond_obs = pd.read_sql(
        f"SELECT * FROM numeric_observations WHERE field_family='reaction_conditions'{conf_sql}", con)
    print(f"  reaction_conditions    {len(cond_obs):>10,} 行")
    con.close()

    print("\n构造各 stage：")
    blocks = {}
    blocks["metadata"] = build_metadata(papers)
    blocks["catalyst"] = build_catalyst(forms)
    blocks["reaction_conditions"] = build_conditions(cond_obs)
    blocks["performance"] = build_performance(perf_obs)
    for k, v in blocks.items():
        print(f"  {k:<22}{len(v):>10,} 行")
        blocks[k] = cap(v, MAX_ROWS_PER_STAGE, k)

    long_df = pd.concat([b for b in blocks.values() if not b.empty], ignore_index=True)
    long_df = long_df[long_df["paper_id"].notna()]

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), OUT_CSV)
    long_df.to_csv(out_path, index=False, encoding="utf-8-sig")

    # ── 诊断报告 ──
    print(f"\n{'='*60}")
    print(f"  已导出：{out_path}")
    print(f"  总行数：{len(long_df):,}   覆盖论文：{long_df['paper_id'].nunique():,} 篇")
    print(f"  文件大小：{os.path.getsize(out_path)/1024/1024:.1f} MB")
    print(f"{'='*60}")

    print("\n【各 stage 行数】")
    print(long_df["stage"].value_counts().to_string())

    perf = long_df[long_df["stage"] == "performance"]
    if not perf.empty:
        cats = perf["metric"].apply(categorize)
        print("\n【性能指标归类】（app27 只认前5类，落到「其他」的画图时会被归并）")
        print(cats.value_counts().to_string())
        other_ratio = (cats == "其他").mean()
        print(f"\n  归入「其他」的比例：{other_ratio:.1%}", end="  ")
        if other_ratio > 0.5:
            print("← 偏高，说明 metric_hint 多为粗糙关键词，建议加映射规则")
        else:
            print("← 正常")
        print("\n【metric_hint 原始取值 Top 20】")
        print(perf["metric"].value_counts().head(20).to_string())

    cond = long_df[long_df["stage"] == "reaction_conditions"]
    if not cond.empty:
        print("\n【反应条件字段填充】")
        for f in ["temperature", "pressure", "time_on_stream", "space_velocity", "h2_co_ratio"]:
            if f in cond.columns:
                print(f"  {f:<18}{cond[f].notna().sum():>10,} 行")

    print("\n下一步：把 extractions_long.csv 复制到 D:\\saf\\outputs\\，"
          "在网站「数据可视化分析」页点『加载数据』。")


if __name__ == "__main__":
    main()

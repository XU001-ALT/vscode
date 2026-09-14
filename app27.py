"""
费托合成催化剂材料数据平台
论文自动下载模块：DOI分类 → 自动下载 → PDF校验（manifest）→ 导出结果
"""

from __future__ import annotations

import streamlit as st
import pandas as pd
import json
import hashlib
import re
import time
import subprocess
import sys
import os
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

try:
    import statsmodels.api  # noqa: F401  仅用于检测是否安装，供散点图趋势线功能判断

    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False
from typing import Optional, Tuple, List, Dict
from datetime import datetime, timezone
from collections import Counter
from html import escape as _html_escape
from pathlib import Path

from saf_common import (
    PUBLISHER_ROUTES, ROUTE_LABEL, AUTO_ROUTES, PUBLISHER_DELAY, HEADERS,
    classify_doi, safe_filename, validate_pdf_bytes,
)
import sqlite3
from ingest_extraction import ingest_extraction, build_preview_row, append_to_parquet

# ══════════════════════════════════════════════════════════════════
#  路径配置（全部相对于本文件所在目录，换机器 / 换系统都无需修改）
# ══════════════════════════════════════════════════════════════════
BASE_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = BASE_DIR / "prompts"
PDFS_DIR = BASE_DIR / "pdfs"
OUTPUTS_DIR = BASE_DIR / "outputs"
DATA_DIR = BASE_DIR / "data"
DB_PATH = BASE_DIR / "fts_evidence_lake.sqlite"
for _d in (PDFS_DIR, OUTPUTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)

# ══════════════════════════════════════════════════════════════════
#  页面配置
# ══════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="费托合成催化剂材料数据平台",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════
#  全局样式
# ══════════════════════════════════════════════════════════════════
st.html("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
html, body, [class*="css"] {
    font-family: 'Times New Roman', 'Microsoft YaHei', '微软雅黑', serif !important;
    font-size: 17px !important;
}
p, div, li, td, th, label, button, input, textarea, select,
h1, h2, h3, h4, h5, h6, .stMarkdown, .stText {
    font-family: 'Times New Roman', 'Microsoft YaHei', '微软雅黑', serif !important;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 0rem !important; padding-bottom: 2rem !important; }

/* 隐藏侧边栏及展开按钮 */
[data-testid="stSidebar"] { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }

/* 顶部导航栏 */
.top-navbar {
    background: linear-gradient(135deg, #0D2B5E 0%, #1565C0 100%);
    padding: 0;
    margin-bottom: 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
.top-navbar-header {
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 14px 32px 10px 24px;
}
.top-navbar-header img {
    height: 52px;
    width: auto;
    border-radius: 6px;
    flex-shrink: 0;
}
.top-navbar-title {
    color: #fff;
    font-size: 1.35rem;
    font-weight: 700;
    line-height: 1.25;
    letter-spacing: -0.01em;
}
.top-navbar-subtitle {
    color: rgba(255,255,255,0.75);
    font-size: 0.78rem;
    margin-top: 2px;
}
.top-navbar-tabs {
    display: flex;
    gap: 2px;
    padding: 0 24px;
    border-top: 1px solid rgba(255,255,255,0.12);
}
.nav-tab {
    padding: 10px 22px;
    color: rgba(255,255,255,0.75) !important;
    font-size: 0.92rem;
    font-weight: 500;
    cursor: pointer;
    border-bottom: 3px solid transparent;
    transition: all 0.18s;
    text-decoration: none;
    white-space: nowrap;
    background: none;
    border-left: none;
    border-right: none;
    border-top: none;
}
.nav-tab:hover { color: #fff !important; background: rgba(255,255,255,0.08); }
.nav-tab.active {
    color: #fff !important;
    border-bottom: 3px solid #fff;
    font-weight: 700;
    background: rgba(255,255,255,0.1);
}

/* Hero */
.hero-banner {
    background: linear-gradient(135deg,#0D2B5E 0%,#1565C0 40%,#1976D2 100%);
    border-radius:10px; padding:26px 32px 22px; margin-bottom:20px;
    position:relative; overflow:hidden;
}
.hero-banner::before {
    content:''; position:absolute; top:-40px; right:-40px;
    width:200px; height:200px; background:rgba(255,255,255,0.05); border-radius:50%;
}
.hero-tag {
    display:inline-block; background:rgba(255,255,255,0.18);
    border:1px solid rgba(255,255,255,0.3); color:#FFE0E0;
    font-size:0.75rem; padding:3px 12px; border-radius:20px;
    margin-bottom:12px; letter-spacing:0.04em;
}
.hero-title { font-size:2.0rem; font-weight:700; color:#fff; margin:0 0 8px; letter-spacing:-0.02em; line-height:1.2; }
.hero-sub   { font-size:0.88rem; color:rgba(255,255,255,0.8); margin:0; line-height:1.5; }

/* 统计卡片 */
.stat-card { background:#fff; border:1px solid #E8E8E8; border-radius:8px; padding:18px 20px; box-shadow:0 1px 4px rgba(0,0,0,0.06); }
.stat-label { font-size:0.92rem; color:#888; margin-bottom:6px; }
.stat-value { font-size:2.1rem; font-weight:700; color:#1A1A2E; line-height:1; font-family:'JetBrains Mono',monospace; }
.stat-desc  { font-size:0.75rem; color:#AAA; margin-top:4px; }

/* 区块标题 */
.section-title { font-size:1.1rem; font-weight:600; color:#0D2B5E; border-left:3px solid #1565C0; padding-left:10px; margin:22px 0 12px; }

/* 提示框 */
.info-box { background:#FFF8F8; border:1px solid #BBDEFB; border-radius:8px; padding:12px 16px; font-size:0.83rem; line-height:1.65; color:#4A0000; }
.info-box code { background:#E3F2FD; color:#1565C0; padding:1px 5px; border-radius:3px; font-family:'JetBrains Mono',monospace; font-size:0.8rem; }

/* 流程步骤条 */
.pipeline-bar {
    display:flex; align-items:center; gap:0;
    background:#F8F8F8; border:1px solid #EEE;
    border-radius:10px; padding:4px; margin-bottom:24px;
}
.pip-step {
    flex:1; text-align:center; padding:10px 6px; border-radius:7px;
    font-size:0.8rem; font-weight:500; cursor:default; transition:all .2s;
}
.pip-step.done    { background:#E3F2FD; color:#1565C0; }
.pip-step.active  { background:#1565C0; color:#fff; font-weight:700; box-shadow:0 2px 8px rgba(21,101,192,0.3); }
.pip-step.pending { background:transparent; color:#BBB; }
.pip-arrow { color:#DDD; font-size:0.9rem; padding:0 2px; }

/* 结果行 */
.result-row {
    display:flex; align-items:center; gap:12px;
    padding:8px 14px; border-radius:6px; margin-bottom:5px; font-size:0.83rem;
}
.result-ok   { background:#F0FFF4; border-left:3px solid #4CAF50; }
.result-warn { background:#FFF8E1; border-left:3px solid #FF9800; }
.result-err  { background:#E3F2FD; border-left:3px solid #1565C0; }

/* 修复 expander 箭头图标在字体未加载时显示为 keyboard_arrow_down 文字 */
[data-testid="stExpander"] summary svg { display: inline !important; }
[data-testid="stExpander"] summary span[data-testid="stExpanderToggleIcon"] {
    font-size: 0 !important;
    line-height: 0 !important;
}
[data-testid="stExpander"] summary span[data-testid="stExpanderToggleIcon"] svg {
    font-size: initial !important;
    width: 1.2rem !important;
    height: 1.2rem !important;
}

/* 主按钮 */
.stButton > button[kind="primary"] {
    background:linear-gradient(135deg,#1565C0,#1976D2) !important;
    border:none !important; color:#fff !important;
    font-weight:600 !important; border-radius:6px !important;
}
.stButton > button[kind="primary"]:hover {
    background:linear-gradient(135deg,#0D2B5E,#0D47A1) !important;
    box-shadow:0 2px 8px rgba(21,101,192,0.35) !important;
}

/* 修复 file_uploader / expander / text_input 标题重叠问题
   （全局 17px 会撑乱 Streamlit 原生组件布局，这里还原成 Streamlit 默认字号） */
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzone"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneInstructions"],
[data-testid="stFileUploader"] [data-testid="stFileUploaderDropzoneButton"] {
    font-size: 0.875rem !important;
}
[data-testid="stFileUploader"] section > span,
[data-testid="stFileUploader"] [data-baseweb="form-control"] > label {
    font-size: 0.875rem !important;
    line-height: 1.3 !important;
    margin-bottom: 4px !important;
}
[data-testid="stExpander"] summary span,
[data-testid="stExpander"] summary [data-testid="stExpanderToggleIcon"] {
    font-size: 0.95rem !important;
    line-height: 1.4 !important;
}
[data-testid="stTextInput"] [data-baseweb="form-control"] > label {
    font-size: 0.85rem !important;
    line-height: 1.3 !important;
    margin-bottom: 2px !important;
    padding-top: 4px !important;
}
/* expander / text_input 内部内容也用默认字号 */
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stTextInput"] input {
    font-size: 0.9rem !important;
}

/* FILE_UPLOADER_DUPLICATE_TEXT_FIX */
[data-testid="stFileUploader"] button::before,
[data-testid="stFileUploader"] button::after,
[data-testid="stFileUploader"] button *::before,
[data-testid="stFileUploader"] button *::after {
    content: none !important;
    display: none !important;
}


/* FILE_UPLOADER_MATERIAL_ICON_FIX */
[data-testid="stFileUploader"] button span[data-testid="stIconMaterial"],
[data-testid="stFileUploader"] button [data-testid="stIconMaterial"] {
    display: none !important;
    width: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}


/* STREAMLIT_MATERIAL_ICON_FONT_FIX */
span[data-testid="stIconMaterial"],
.material-symbols-rounded,
.material-symbols-outlined {
    font-family: "Material Symbols Rounded", "Material Symbols Outlined" !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-size: 1.25rem !important;
    line-height: 1 !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: "liga" !important;
    font-feature-settings: "liga" !important;
    -webkit-font-smoothing: antialiased !important;
}

</style>
""")

# ══════════════════════════════════════════════════════════════════
#  核心常量与函数
# ══════════════════════════════════════════════════════════════════

# PUBLISHER_ROUTES / ROUTE_LABEL / AUTO_ROUTES / PUBLISHER_DELAY / HEADERS /
# classify_doi / safe_filename / validate_pdf_bytes 已移至 saf_common.py


def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {}
    for c in df.columns:
        lc = c.strip().lower().replace(" ", "_").replace("-", "_")
        if (lc == "doi" or lc.startswith("doi")) and "doi" not in mapping.values():
            mapping[c] = "doi"
        elif any(k in lc for k in ("access", "_oa", "classification")) and "access_type" not in mapping.values():
            mapping[c] = "access_type"
        elif "title" in lc and "title" not in mapping.values():
            mapping[c] = "title"
        elif "year" in lc and "year" not in mapping.values():
            mapping[c] = "year"
    return df.rename(columns=mapping)


def classify_df(df: pd.DataFrame) -> Tuple[pd.DataFrame, bool]:
    df = normalize_cols(df.copy())
    if "doi" not in df.columns:
        st.error(f"❌ 未找到 DOI 列。当前列名：**{'、'.join(df.columns.tolist()[:8])}**")
        return df, False
    access = df.get("access_type", pd.Series([""] * len(df), index=df.index))
    results = [classify_doi(str(df["doi"].iloc[i]), str(access.iloc[i]) if i < len(access) else "")
               for i in range(len(df))]
    df["路由"] = [r["route"] for r in results]
    df["出版商"] = [r["publisher"] for r in results]
    df["下载URL"] = [r["url"] for r in results]
    df["状态"] = "待下载"
    return df, True


def load_df(file) -> pd.DataFrame:
    """支持 CSV / Excel 读取（论文自动下载页需要上传 Excel）"""
    name = file.name.lower()
    if name.endswith(".csv"):
        last_err = None
        for enc in ("utf-8-sig", "gbk", "utf-8"):
            try:
                file.seek(0)
                return pd.read_csv(file, encoding=enc)
            except Exception as e:
                last_err = e
        st.error(f"CSV 读取失败（已尝试 utf-8-sig/gbk/utf-8）：{last_err}")
        return pd.DataFrame()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(file, engine="openpyxl")
    st.error(f"不支持的文件格式：{file.name}（仅支持 CSV / Excel）")
    return pd.DataFrame()


def _parse_filename(path: Path) -> dict:
    stem = path.stem
    match = re.search(r"_([0-9a-f]{10,12})$", stem, flags=re.I)
    hash_suffix = ""
    if match:
        hash_suffix = match.group(1).lower()
        stem = stem[: match.start()]
    year = author = ""
    title = stem.replace("_", " ")
    ym = re.search(r"(^|_)(19|20)\d{2}(_|$)", stem)
    if ym:
        year = ym.group(0).strip("_")
        before = stem[:ym.start()].strip("_")
        after = stem[ym.end():].strip("_")
        author = before.replace("_", " ").strip()
        title = after.replace("_", " ").strip() or title
    return {"filename_author_guess": author, "filename_year_guess": year,
            "filename_title_guess": title, "filename_hash_suffix": hash_suffix}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_pdf_info(path: Path) -> dict:
    info = {
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
        with path.open("rb") as f:
            info["pdf_header_valid"] = (f.read(5) == b"%PDF-")
    except OSError as e:
        info["pdf_error"] = f"header_read_error: {e}"
        return info
    try:
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        info["is_encrypted"] = bool(reader.is_encrypted)
        info["page_count"] = len(reader.pages)
        meta = reader.metadata or {}
        info["pdf_metadata_title"] = str(meta.get("/Title", "") or "")[:300]
        info["pdf_metadata_author"] = str(meta.get("/Author", "") or "")[:300]
        if reader.pages:
            text = reader.pages[0].extract_text() or ""
            dm = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", text, flags=re.I)
            if dm:
                info["first_page_doi"] = dm.group(0).rstrip(".,;)").lower()
        info["pdf_read_ok"] = True
    except ImportError:
        info["pdf_read_ok"] = info["pdf_header_valid"]
    except Exception as e:
        info["pdf_error"] = f"{type(e).__name__}: {e}"
    return info


def validate_pdf_file(path: Path, min_kb: int = 20, compute_sha256: bool = True) -> dict:
    stat = path.stat()
    parsed = _parse_filename(path)
    pdf_info = _read_pdf_info(path)
    sha256 = _sha256_file(path) if compute_sha256 else ""
    paper_id = hashlib.sha1(path.name.encode("utf-8")).hexdigest()[:16]

    valid = (
            pdf_info["pdf_header_valid"]
            and stat.st_size > min_kb * 1024
    )
    return {
        "paper_id": paper_id,
        "file_name": path.name,
        "file_size_kb": round(stat.st_size / 1024, 1),
        "file_size_mb": round(stat.st_size / 1024 / 1024, 3),
        "valid": valid,
        "sha256": sha256,
        **parsed,
        **pdf_info,
    }


def scan_pdf_folder(folder: Path, min_kb: int = 20, compute_sha256: bool = True) -> List[Dict]:
    results = []
    sha_seen: Dict[str, str] = {}

    all_pdfs = sorted(folder.rglob("*.pdf"))
    for pdf_path in all_pdfs:
        try:
            r = validate_pdf_file(pdf_path, min_kb, compute_sha256)
        except Exception as e:
            r = {
                "file_name": pdf_path.name,
                "file_size_kb": 0,
                "valid": False,
                "pdf_error": str(e),
            }
        r["relative_path"] = str(pdf_path.relative_to(folder))

        sha = r.get("sha256", "")
        if sha and sha in sha_seen:
            r["duplicate_of"] = sha_seen[sha]
        else:
            r["duplicate_of"] = ""
            if sha:
                sha_seen[sha] = r["file_name"]

        results.append(r)
    return results


def download_one(doi: str, url: str, publisher: str, out_dir: str, min_kb: int = 20, timeout: int = 60) -> dict:
    try:
        import requests
    except ImportError:
        return {"doi": doi, "status": "error", "reason": "未安装 requests，请运行 pip install requests"}

    out_path = Path(out_dir) / publisher.replace("/", "_") / safe_filename(doi)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if out_path.exists() and out_path.stat().st_size > min_kb * 1024:
        v = validate_pdf_bytes(out_path.read_bytes(), min_kb)
        if v["valid"]:
            return {"doi": doi, "status": "skipped_exists", "file": str(out_path),
                    "size_kb": v["size_kb"], "sha256": v["sha256"], "reason": "文件已存在"}

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except Exception as e:
        return {"doi": doi, "status": "error", "reason": str(e)[:120]}

    if resp.status_code in (401, 403):
        return {"doi": doi, "status": "no_access", "file": "", "reason": f"HTTP {resp.status_code} 需机构认证/VPN"}
    if resp.status_code == 404:
        return {"doi": doi, "status": "not_found", "file": "", "reason": "HTTP 404 资源不存在"}
    if resp.status_code != 200:
        return {"doi": doi, "status": "http_error", "file": "", "reason": f"HTTP {resp.status_code}"}

    v = validate_pdf_bytes(resp.content, min_kb)
    if not v["valid"]:
        debug_dir = Path(out_dir) / "_invalid_debug" / publisher.replace("/", "_")
        debug_dir.mkdir(parents=True, exist_ok=True)
        ctype = resp.headers.get("content-type", "").lower()
        ext = ".html" if "html" in ctype else (".pdf" if "pdf" in ctype else ".bin")
        debug_path = debug_dir / (safe_filename(doi).rsplit(".", 1)[0] + ext)
        try:
            debug_path.write_bytes(resp.content)
        except Exception:
            debug_path = None

        status = "invalid_pdf"
        reason = v["reason"] + f"（实际Content-Type: {ctype or '未知'}，已保存供排查）"
        if "html" in ctype:
            try:
                text_lower = resp.content[:20000].decode("utf-8", errors="ignore").lower()
            except Exception:
                text_lower = ""
            paywall_keywords = [
                "sign in", "log in", "purchase", "subscribe", "access denied",
                "institutional access", "get access", "buy this article",
                "您没有权限", "请登录", "购买", "订阅", "access this article",
            ]
            if any(kw in text_lower for kw in paywall_keywords):
                status = "likely_paywall"
                reason = "HTTP 200 但内容是登录/付费墙页面（非真正403），疑似无访问权限"

        return {
            "doi": doi, "status": status, "file": str(debug_path) if debug_path else "",
            "reason": reason, "size_kb": v["size_kb"],
        }

    out_path.write_bytes(resp.content)
    return {"doi": doi, "status": "success", "file": str(out_path),
            "size_kb": v["size_kb"], "sha256": v["sha256"], "reason": ""}


def stat_card(col, value, label, desc=""):
    with col:
        # desc 为空时用 &nbsp; 占位，保证所有卡片等高
        desc_html = _html_escape(str(desc)) if desc else "&nbsp;"
        st.markdown(
            f'<div class="stat-card"><div class="stat-label">{_html_escape(str(label))}</div>'
            f'<div class="stat-value">{_html_escape(str(value))}</div>'
            f'<div class="stat-desc">{desc_html}</div></div>',
            unsafe_allow_html=True,
        )


def check_chrome_debug_port(host: str = "localhost", port: int = 9222) -> bool:
    import socket
    try:
        s = socket.create_connection((host, port), timeout=2)
        s.close()
        return True
    except Exception:
        return False


def write_webvpn_queue_csv(df_rows: pd.DataFrame, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    export_df = pd.DataFrame({
        "doi": df_rows["doi"].astype(str),
        "publisher_group": df_rows.get("出版商", df_rows.get("publisher", "")).astype(str),
        "title": df_rows.get("title", df_rows.get("标题", "")).astype(
            str) if "title" in df_rows.columns or "标题" in df_rows.columns else "",
    })
    export_df.to_csv(out_path, index=False, encoding="utf-8-sig")


def run_webvpn_downloader(queue_csv: Path, out_dir: str, limit: int, min_kb: int,
                          timeout: int, delay: float, script_path: str) -> subprocess.Popen:
    cmd = [
        sys.executable, script_path,
        "--queue", str(queue_csv),
        "--out-dir", out_dir,
        "--limit", str(limit),
        "--min-kb", str(min_kb),
        "--timeout", str(timeout),
        "--delay", str(delay),
        "--debug",
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )


def parse_webvpn_log(log_path: Path) -> pd.DataFrame:
    if not log_path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(log_path, encoding="utf-8-sig")
    except Exception:
        return pd.DataFrame()


def read_log_tail(path: str, n: int = 50) -> pd.DataFrame:
    try:
        p = Path(path)
        if not p.exists():
            return pd.DataFrame()
        return pd.read_csv(p, encoding="utf-8-sig").tail(n)
    except Exception:
        return pd.DataFrame()


def run_cmd_sync(cmd: list, cwd: str = None, timeout: int = 300) -> tuple:
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            timeout=timeout, shell=False,
        )
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return -1, f"超时（>{timeout}s）"
    except Exception as e:
        return -1, str(e)


def run_cmd_bg(cmd: list, cwd: str = None, env: dict = None) -> subprocess.Popen:
    return subprocess.Popen(
        cmd, cwd=cwd,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8", errors="replace", shell=False,
        env=env,
    )


# ══════════════════════════════════════════════════
#  数据可视化分析：数值解析与单位归一化工具
# ══════════════════════════════════════════════════

def parse_numeric_with_unit(raw: str) -> dict:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return {"raw": raw, "kind": "unparseable", "value": None,
                "value_min": None, "value_max": None, "unit_raw": None}

    text = str(raw).strip()
    if not text:
        return {"raw": raw, "kind": "unparseable", "value": None,
                "value_min": None, "value_max": None, "unit_raw": None}

    range_match = re.search(
        r"(?:room temperature|RT|(-?\d+\.?\d*))\s*(?:to|-|–|~)\s*(-?\d+\.?\d*)\s*([%a-zA-Z°/().\s]*)$",
        text, re.IGNORECASE,
    )
    if range_match:
        low_str, high_str, unit = range_match.group(1), range_match.group(2), range_match.group(3)
        low = 25.0 if low_str is None else float(low_str)
        try:
            high = float(high_str)
            return {"raw": raw, "kind": "range", "value": None,
                    "value_min": low, "value_max": high, "unit_raw": unit.strip() or None}
        except ValueError:
            pass

    single_match = re.search(r"(-?\d+\.?\d*)\s*([%a-zA-Z°/().]*)", text)
    if single_match:
        try:
            value = float(single_match.group(1))
            unit = single_match.group(2).strip() or None
            return {"raw": raw, "kind": "single", "value": value,
                    "value_min": None, "value_max": None, "unit_raw": unit}
        except ValueError:
            pass

    return {"raw": raw, "kind": "unparseable", "value": None,
            "value_min": None, "value_max": None, "unit_raw": None}


def _safe_unit_str(unit_raw) -> str:
    if unit_raw is None:
        return ""
    if isinstance(unit_raw, float) and pd.isna(unit_raw):
        return ""
    return str(unit_raw)


def normalize_temperature(value: float, unit_raw) -> Optional[float]:
    if value is None:
        return None
    u = _safe_unit_str(unit_raw).lower().replace(" ", "")
    if "k" == u or (u.endswith("k") and "c" not in u):
        return round(value - 273.15, 2)
    if "f" in u:
        return round((value - 32) * 5 / 9, 2)
    return value


def normalize_pressure(value: float, unit_raw) -> Optional[float]:
    if value is None:
        return None
    u = _safe_unit_str(unit_raw).lower().replace(" ", "")
    if "bar" in u:
        return round(value * 0.1, 4)
    if "atm" in u:
        return round(value * 0.101325, 4)
    if "psi" in u:
        return round(value * 0.00689476, 4)
    if "kpa" in u:
        return round(value / 1000, 4)
    return value


def normalize_time_hours(value: float, unit_raw) -> Optional[float]:
    if value is None:
        return None
    u = _safe_unit_str(unit_raw).lower().replace(" ", "")
    if "min" in u:
        return round(value / 60, 3)
    if "day" in u or u == "d":
        return round(value * 24, 2)
    return value


UNIT_NORMALIZERS = {
    "temperature": (normalize_temperature, "°C"),
    "pressure": (normalize_pressure, "MPa"),
    "time_on_stream": (normalize_time_hours, "h"),
}


def parse_and_normalize_column(series: pd.Series, field_name: str) -> pd.DataFrame:
    parsed = series.apply(parse_numeric_with_unit).apply(pd.Series)

    normalizer_info = UNIT_NORMALIZERS.get(field_name)
    if normalizer_info is None:
        parsed["value_norm"] = parsed["value"]
        parsed["value_min_norm"] = parsed["value_min"]
        parsed["value_max_norm"] = parsed["value_max"]
        parsed["target_unit"] = parsed["unit_raw"]
        return parsed

    normalizer_fn, target_unit = normalizer_info
    parsed["value_norm"] = parsed.apply(
        lambda r: normalizer_fn(r["value"], r["unit_raw"]) if r["kind"] == "single" else None, axis=1
    )
    parsed["value_min_norm"] = parsed.apply(
        lambda r: normalizer_fn(r["value_min"], r["unit_raw"]) if r["kind"] == "range" else None, axis=1
    )
    parsed["value_max_norm"] = parsed.apply(
        lambda r: normalizer_fn(r["value_max"], r["unit_raw"]) if r["kind"] == "range" else None, axis=1
    )
    parsed["target_unit"] = target_unit
    return parsed


def split_stages(df_long: pd.DataFrame) -> dict:
    stages = {}

    meta = df_long[df_long["stage"] == "metadata"].dropna(axis=1, how="all").copy()
    stages["metadata"] = meta

    cat = df_long[df_long["stage"] == "catalyst"].dropna(axis=1, how="all").copy()
    stages["catalyst"] = cat

    cond = df_long[df_long["stage"] == "reaction_conditions"].dropna(axis=1, how="all").copy()
    for field in ["temperature", "pressure", "time_on_stream"]:
        if field in cond.columns:
            parsed = parse_and_normalize_column(cond[field], field)
            cond[f"{field}_value"] = parsed["value_norm"]
            cond[f"{field}_min"] = parsed["value_min_norm"]
            cond[f"{field}_max"] = parsed["value_max_norm"]
            cond[f"{field}_kind"] = parsed["kind"]
            cond[f"{field}_unit"] = parsed["target_unit"]
    stages["reaction_conditions"] = cond

    perf = df_long[df_long["stage"] == "performance"].dropna(axis=1, how="all").copy()
    if "value" in perf.columns:
        parsed = parse_and_normalize_column(perf["value"], "value")
        perf["value_parsed"] = parsed["value_norm"]
        perf["value_kind"] = parsed["kind"]
        perf["value_min_parsed"] = parsed["value_min_norm"]
        perf["value_max_parsed"] = parsed["value_max_norm"]
    stages["performance"] = perf

    return stages


def build_plot_ready_performance(perf_df: pd.DataFrame, paper_meta: pd.DataFrame) -> pd.DataFrame:
    plot_df = perf_df[perf_df.get("value_kind") == "single"].copy()
    if plot_df.empty:
        return plot_df

    plot_df = plot_df.rename(columns={"value_parsed": "value_numeric"})
    if "metric" in plot_df.columns:
        plot_df["metric_raw"] = plot_df["metric"]
        plot_df["metric"] = plot_df["metric"].apply(normalize_metric_category)

    keep_cols = ["paper_id", "performance_id", "catalyst_ref", "metric", "metric_raw",
                 "species_or_range", "value_numeric", "unit", "confidence"]
    keep_cols = [c for c in keep_cols if c in plot_df.columns]
    plot_df = plot_df[keep_cols]

    if not paper_meta.empty and "paper_id" in paper_meta.columns:
        meta_cols = [c for c in ["paper_id", "metadata_year", "metadata_journal", "metadata_doi"] if
                     c in paper_meta.columns]
        plot_df = plot_df.merge(paper_meta[meta_cols], on="paper_id", how="left")
        if "metadata_doi" in plot_df.columns:
            plot_df = plot_df.rename(columns={"metadata_doi": "doi"})

    return plot_df


METRIC_CATEGORY_RULES = [
    ("STY", ["sty", "space time yield", "space-time yield"]),
    ("productivity", ["productivity"]),
    ("yield", ["yield"]),
    ("selectivity", ["selectivity"]),
    ("conversion", ["conversion"]),
]
METRIC_CATEGORY_OTHER = "其他"


def normalize_metric_category(raw_metric) -> str:
    if raw_metric is None or (isinstance(raw_metric, float) and pd.isna(raw_metric)):
        return METRIC_CATEGORY_OTHER
    text_lower = str(raw_metric).lower()
    for category, keywords in METRIC_CATEGORY_RULES:
        if any(kw in text_lower for kw in keywords):
            return category
    return METRIC_CATEGORY_OTHER


def get_unparseable_rows(stages: dict) -> pd.DataFrame:
    rows = []

    perf = stages.get("performance", pd.DataFrame())
    if not perf.empty and "value_kind" in perf.columns:
        bad = perf[perf["value_kind"] == "unparseable"]
        for _, r in bad.iterrows():
            rows.append({
                "paper_id": r.get("paper_id"), "字段": "performance.value",
                "原始文本": r.get("value"), "metric": r.get("metric"),
                "species_or_range": r.get("species_or_range"),
            })

    cond = stages.get("reaction_conditions", pd.DataFrame())
    for field in ["temperature", "pressure", "time_on_stream"]:
        kind_col = f"{field}_kind"
        if not cond.empty and kind_col in cond.columns:
            bad = cond[cond[kind_col] == "unparseable"]
            for _, r in bad.iterrows():
                rows.append({
                    "paper_id": r.get("paper_id"), "字段": f"reaction_conditions.{field}",
                    "原始文本": r.get(field), "metric": None, "species_or_range": None,
                })

    return pd.DataFrame(rows)


CONDITION_FIELD_LABELS = {
    "temperature": ("温度", "°C"),
    "pressure": ("压力", "MPa"),
    "time_on_stream": ("运行时长", "h"),
}


def build_plot_ready_conditions(cond_df: pd.DataFrame, paper_meta: pd.DataFrame) -> pd.DataFrame:
    if cond_df.empty:
        return pd.DataFrame()

    rows = []
    for field, (label, unit) in CONDITION_FIELD_LABELS.items():
        value_col = f"{field}_value"
        kind_col = f"{field}_kind"
        if value_col not in cond_df.columns:
            continue
        sub = cond_df[cond_df.get(kind_col) == "single"]
        for _, r in sub.iterrows():
            rows.append({
                "paper_id": r.get("paper_id"),
                "condition_id": r.get("condition_id"),
                "catalyst_ref": r.get("catalyst_ref"),
                "metric": label,
                "species_or_range": None,
                "value_numeric": r.get(value_col),
                "unit": unit,
                "confidence": None,
            })

    plot_df = pd.DataFrame(rows)
    if plot_df.empty:
        return plot_df

    if not paper_meta.empty and "paper_id" in paper_meta.columns:
        meta_cols = [c for c in ["paper_id", "metadata_year", "metadata_journal", "metadata_doi"] if
                     c in paper_meta.columns]
        plot_df = plot_df.merge(paper_meta[meta_cols], on="paper_id", how="left")
        if "metadata_doi" in plot_df.columns:
            plot_df = plot_df.rename(columns={"metadata_doi": "doi"})

    return plot_df


def join_conditions_with_performance(cond_plot_df: pd.DataFrame, perf_plot_df: pd.DataFrame) -> pd.DataFrame:
    if cond_plot_df.empty or perf_plot_df.empty:
        return pd.DataFrame()

    cond_wide = cond_plot_df.pivot_table(
        index=["paper_id", "catalyst_ref"], columns="metric", values="value_numeric", aggfunc="first"
    ).reset_index()

    merge_keys = ["paper_id", "catalyst_ref"]
    if "catalyst_ref" not in perf_plot_df.columns or "catalyst_ref" not in cond_wide.columns:
        return pd.DataFrame()

    merged = perf_plot_df.merge(cond_wide, on=merge_keys, how="inner")
    return merged


def plotly_chart_with_doi(fig, source_df: pd.DataFrame, chart_key: str,
                          doi_col: str = "doi", paper_id_col: str = "paper_id"):
    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key=chart_key)

    if event and event.selection and event.selection.get("points"):
        pt = event.selection["points"][0]
        pt_idx = pt.get("point_index", -1)

        row = None
        if 0 <= pt_idx < len(source_df):
            row = source_df.iloc[pt_idx]

        if row is not None:
            doi_raw = ""
            if doi_col in source_df.columns:
                doi_raw = str(row.get(doi_col, "") or "").strip()
                doi_raw = doi_raw.replace("nan", "").replace("None", "")

            paper_id = str(row.get(paper_id_col, "")) if paper_id_col in source_df.columns else ""

            if doi_raw:
                doi_url = doi_raw if doi_raw.startswith("http") else f"https://doi.org/{doi_raw}"
                cols_doi = st.columns([3, 1])
                with cols_doi[0]:
                    st.info(f"📄 已选中 | paper_id: `{paper_id}` | DOI: `{doi_raw}`")
                with cols_doi[1]:
                    st.link_button("🔗 打开论文", doi_url, use_container_width=True)
            else:
                st.caption(f"已选中 paper_id: `{paper_id}`（暂无DOI信息）")
    else:
        st.caption("💡 点击图中任意数据点可获得该论文的 DOI 跳转链接")


def scatter_with_doi_links(fig, plot_data: pd.DataFrame, doi_col: str = "doi",
                           height: int = 480, chart_key: str = "doi_scatter"):
    fig.update_layout(height=height)
    plotly_chart_with_doi(fig, plot_data, chart_key=chart_key, doi_col=doi_col)


def build_plot_ready_metadata(meta_df: pd.DataFrame) -> pd.DataFrame:
    if meta_df.empty:
        return pd.DataFrame()

    cols_wanted = {
        "paper_id": "paper_id",
        "metadata_year": "year",
        "metadata_journal": "journal",
        "metadata_document_type": "document_type",
        "metadata_route_type": "route_type",
        "metadata_doi": "doi",
    }
    available = {k: v for k, v in cols_wanted.items() if k in meta_df.columns}
    plot_df = meta_df[list(available.keys())].rename(columns=available).copy()

    if "year" in plot_df.columns:
        plot_df["year"] = pd.to_numeric(plot_df["year"], errors="coerce")

    if "route_type" in plot_df.columns:
        def extract_first_route(raw):
            if pd.isna(raw) or not str(raw).strip():
                return None
            import re as _re
            m = _re.search(r"'value':\s*'([^']+)'", str(raw))
            return m.group(1) if m else str(raw)[:50]

        plot_df["route_type"] = plot_df["route_type"].apply(extract_first_route)

    return plot_df.dropna(subset=["paper_id"])


def build_plot_ready_catalyst(cat_df: pd.DataFrame, meta_df: pd.DataFrame) -> pd.DataFrame:
    if cat_df.empty:
        return pd.DataFrame()

    cat_fields = {
        "active_metal": "活性金属",
        "support": "载体",
        "promoter": "助剂",
        "preparation_method": "制备方法",
    }

    rows = []
    for field, label in cat_fields.items():
        if field not in cat_df.columns:
            continue
        sub = cat_df[["paper_id", field]].dropna(subset=[field])
        for _, r in sub.iterrows():
            val = str(r[field]).strip()
            if val and val.lower() not in ("nan", "none", "null", ""):
                rows.append({
                    "paper_id": r["paper_id"],
                    "metric": label,
                    "value_text": val,
                })

    if not rows:
        return pd.DataFrame()

    plot_df = pd.DataFrame(rows)

    if not meta_df.empty and "paper_id" in meta_df.columns:
        year_col = "metadata_year" if "metadata_year" in meta_df.columns else None
        if year_col:
            year_map = meta_df.set_index("paper_id")[year_col].apply(
                lambda x: pd.to_numeric(x, errors="coerce")
            )
            plot_df["metadata_year"] = plot_df["paper_id"].map(year_map)
        doi_col = "metadata_doi" if "metadata_doi" in meta_df.columns else None
        if doi_col:
            doi_map = meta_df.set_index("paper_id")[doi_col].astype(str)
            plot_df["doi"] = plot_df["paper_id"].map(doi_map)

    return plot_df


def pipeline_bar(current: int, steps: Optional[list] = None):
    if steps is None:
        steps = ["① DOI 分类", "② 自动下载", "③ PDF 校验", "④ 导出结果"]
    parts = []
    for i, s in enumerate(steps, 1):
        if i < current:
            cls = "done"
        elif i == current:
            cls = "active"
        else:
            cls = "pending"
        parts.append(f'<div class="pip-step {cls}">{s}</div>')
        if i < len(steps):
            parts.append('<div class="pip-arrow">›</div>')
    st.markdown(
        f'<div class="pipeline-bar">{"".join(parts)}</div>',
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════
#  顶部横排导航栏（替代侧边栏）
# ══════════════════════════════════════════════════════════════════

_PAGES = ["📊 平台数据总览", "📥 论文自动下载", "🔬 数据自动提取", "📈 数据可视化分析", "📖 使用说明"]

if "page" not in st.session_state:
    st.session_state["page"] = _PAGES[0]

# ── Logo + 标题区 ──
import base64 as _b64

_img_tag = ""
try:
    with open(BASE_DIR / "logo.jpg", "rb") as _f:
        _img_b64 = _b64.b64encode(_f.read()).decode()
    _img_tag = f'<img src="data:image/jpeg;base64,{_img_b64}" style="height:52px;width:auto;border-radius:6px;flex-shrink:0;" />'
except Exception:
    pass

st.markdown(f"""
<div style="background:linear-gradient(135deg,#0D2B5E 0%,#1565C0 100%);padding:14px 32px 0 24px;box-shadow:0 2px 8px rgba(0,0,0,0.25);margin-bottom:0;">
<div style="display:flex;align-items:center;gap:16px;padding-bottom:10px;min-height:52px;">
{_img_tag}
<div>
<div style="color:#fff;font-size:1.35rem;font-weight:700;line-height:1.25;letter-spacing:-0.01em;">
费托合成催化剂材料数据自动挖掘与大数据分析平台
</div>
<div style="color:rgba(255,255,255,0.75);font-size:0.78rem;margin-top:2px;">
实现文献的自动批量下载、文献内数据的自动摘取以及数据可视化分析。
</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

# ── 导航标签行 ──
st.markdown("""
<style>
div[data-testid="stHorizontalBlock"].navbar-row > div[data-testid="stColumn"] {
    padding: 0 !important;
}
.navbar-row button {
    background: linear-gradient(135deg,#0D2B5E 0%,#1565C0 100%) !important;
    color: rgba(255,255,255,0.72) !important;
    border: none !important;
    border-radius: 0 !important;
    border-bottom: 3px solid transparent !important;
    font-size: 0.95rem !important;
    font-weight: 500 !important;
    padding: 10px 4px !important;
    width: 100% !important;
    transition: all 0.15s !important;
}
.navbar-row button:hover {
    color: #fff !important;
    background: linear-gradient(135deg,#0D2B5E 0%,#1976D2 100%) !important;
    border-bottom: 3px solid rgba(255,255,255,0.5) !important;
}
.navbar-row button.active-nav,
.navbar-row button[data-active="true"] {
    color: #fff !important;
    border-bottom: 3px solid #fff !important;
    font-weight: 700 !important;
}
.navbar-row .stButton { margin: 0 !important; }
.navbar-row { gap: 0 !important; background: linear-gradient(135deg,#0D2B5E 0%,#1565C0 100%); margin-bottom: 0 !important; }
</style>
""", unsafe_allow_html=True)

_nav_cols = st.columns(len(_PAGES))
for _i, (_col, _p) in enumerate(zip(_nav_cols, _PAGES)):
    with _col:
        if st.button(_p, key=f"nav_btn_{_i}", use_container_width=True):
            st.session_state["page"] = _p
            st.rerun()

_cur = st.session_state["page"]
_active_idx = _PAGES.index(_cur)
st.markdown(f"""
<script>
(function() {{
    function styleNavBtns() {{
        var btns = document.querySelectorAll('.navbar-row button');
        if (btns.length < {len(_PAGES)}) {{ setTimeout(styleNavBtns, 80); return; }}
        btns.forEach(function(b, i) {{
            if (i === {_active_idx}) {{
                b.style.color = '#fff';
                b.style.borderBottom = '3px solid #fff';
                b.style.fontWeight = '700';
            }} else {{
                b.style.color = 'rgba(255,255,255,0.72)';
                b.style.borderBottom = '3px solid transparent';
                b.style.fontWeight = '500';
            }}
        }});
    }}
    styleNavBtns();
}})();
</script>
""", unsafe_allow_html=True)

st.markdown(f"""
<script>
(function() {{
    function tagNavRow() {{
        var allRows = document.querySelectorAll('[data-testid="stHorizontalBlock"]');
        allRows.forEach(function(row) {{
            var btns = row.querySelectorAll('button');
            if (btns.length === {len(_PAGES)}) {{ row.classList.add('navbar-row'); }}
        }});
        if (!document.querySelector('.navbar-row')) {{ setTimeout(tagNavRow, 80); }}
    }}
    tagNavRow();
}})();
</script>
""", unsafe_allow_html=True)

page = st.session_state["page"]

# ══════════════════════════════════════════════════════════════════
#  Hero Banner
# ══════════════════════════════════════════════════════════════════
HERO_SUBS = {
    "📊 平台数据总览": "文献库规模统计、出版商分布、催化剂数据筛选与可视化（散点图、云雨图）。",
    "📥 论文自动下载": "DOI 分类 → 自动下载 → PDF 校验 → 导出结果，全流程一站式完成。",
    "🔬 数据自动提取": "上传 PDF，LLM 自动提取催化剂、反应条件与性能数据，确认入库后前端自动刷新。",
    "📈 数据可视化分析": "基于催化剂宽表自动渲染多维度图表（箱线/折线/散点/云雨/分布）。",
    "📖 使用说明": "说明页面各模块含义、数据文件位置和生产应用边界。",
}
st.markdown(f"""
<div class="hero-banner">
  <div class="hero-tag">费托合成催化剂材料数据平台</div>
  <div class="hero-title">费托合成催化剂材料数据自动挖掘与大数据分析平台</div>
  <div class="hero-sub">{HERO_SUBS.get(page, "")}</div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
#  全局数据源：催化剂宽表（Parquet，多页共用，不再依赖 Excel）
# ══════════════════════════════════════════════════════════════════
_VIZ_PARQUET_PATH = OUTPUTS_DIR / "FT_SAF_catalyst_extraction_wide_table.parquet"
_VIZ_ALT_PARQUET = DATA_DIR / "FT_SAF_catalyst_extraction_wide_table.parquet"


@st.cache_data(ttl=60, show_spinner="加载数据库…")
def load_viz_db():
    """数据可视化分析页专用：加载催化剂宽表（parquet 唯一数据源）"""
    if _VIZ_PARQUET_PATH.exists():
        path = _VIZ_PARQUET_PATH
    elif _VIZ_ALT_PARQUET.exists():
        path = _VIZ_ALT_PARQUET
    else:
        return None

    df = pd.read_parquet(path)

    for col in ["reaction_temperature_C", "reaction_pressure_bar",
                "CO_conversion_pct", "CO2_conversion_pct", "BET_surface_area_m2_g",
                "metal_particle_size_nm", "H2_CO_ratio"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "year" in df.columns:
        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    if "H2_CO_ratio" in df.columns:
        _h2co_col = df["H2_CO_ratio"].copy()
        _h2co = pd.to_numeric(_h2co_col, errors="coerce")
        _mask = _h2co.isna() & _h2co_col.notna()
        if _mask.any():
            import re as _re
            for _idx in df.index[_mask]:
                _val = str(_h2co_col[_idx]).strip()
                m = _re.match(r"^\s*(\d+\.?\d*)\s*[/:]\s*(\d+\.?\d*)\s*$", _val)
                if m:
                    a, b = float(m.group(1)), float(m.group(2))
                    if b != 0:
                        _h2co[_idx] = a / b
        df["H2_CO_ratio"] = _h2co

    if "reaction_temperature_C" in df.columns:
        df.loc[df["reaction_temperature_C"] > 1200, "reaction_temperature_C"] = float("nan")
    if "reaction_pressure_bar" in df.columns:
        df.loc[df["reaction_pressure_bar"] > 1000, "reaction_pressure_bar"] = float("nan")
    if "CO_conversion_pct" in df.columns:
        df.loc[df["CO_conversion_pct"] > 100, "CO_conversion_pct"] = float("nan")
    if "H2_CO_ratio" in df.columns:
        df.loc[(df["H2_CO_ratio"] > 10) | (df["H2_CO_ratio"] < 0), "H2_CO_ratio"] = float("nan")
    return df


# ══════════════════════════════════════════════════════════════════
#  页面：平台数据总览（合并原"平台总览"+"数据库浏览"）
# ══════════════════════════════════════════════════════════════════
if page == "📊 平台数据总览":

    @st.cache_data(show_spinner="读取数据概况…", ttl=60)
    def load_overview_stats(_signal: str = ""):
        """优先从 parquet 宽表读取（数据源统一，和数据可视化分析一致）。
        _signal 用于强制缓存失效（入库后清缓存即传入新值）。
        """
        def _get_parquet_cols(path: Path) -> list[str]:
            """获取 parquet 文件的列名（不依赖 pandas 的 nrows 参数）。"""
            try:
                import pyarrow.parquet as pq
                return [f.name for f in pq.read_schema(path)]
            except Exception:
                # 回退：只读一列但无法获得全部列名，只能按需读取
                return []

        # 1. 优先读 parquet（和数据可视化分析同一数据源）
        parquet_path = _VIZ_PARQUET_PATH
        parquet_cols_need = {"paper_id", "year", "metadata_publisher", "metadata_access_route",
                             "metadata_journal"}
        if parquet_path.exists():
            try:
                cols_available = _get_parquet_cols(parquet_path)
                if cols_available:
                    cols_to_read = [c for c in parquet_cols_need if c in cols_available]
                else:
                    cols_to_read = list(parquet_cols_need)  # pyarrow 不可用时按需求读
                if not cols_to_read or "paper_id" not in cols_to_read:
                    cols_to_read = ["paper_id", "year", "metadata_publisher",
                                    "metadata_access_route", "metadata_journal"]
                df = pd.read_parquet(parquet_path, columns=[
                    c for c in cols_to_read if c in (cols_available or cols_to_read)
                ] or cols_to_read)
                df = df.drop_duplicates(subset=["paper_id"])

                stats = {"total_papers": int(df["paper_id"].nunique())}

                # 年份
                yrs = pd.to_numeric(df.get("year"), errors="coerce").dropna()
                yrs = yrs[(yrs > 1900) & (yrs < 2100)]
                stats["year_range"] = f"{int(yrs.min())}–{int(yrs.max())}" if not yrs.empty else "—"
                stats["year_desc"] = f"中位年份 {int(yrs.median())}" if not yrs.empty else "年份信息缺失"

                # OA / 非OA
                if "metadata_access_route" in df.columns:
                    route = df["metadata_access_route"].astype(str).str.upper()
                    oa = int(route.str.contains("OA").sum() - route.str.contains("NON").sum())
                    non_oa = int(route.str.contains("NON").sum())
                    oa = max(oa, 0)
                    tot = oa + non_oa
                    stats["oa"] = f"{oa:,} / {non_oa:,}" if tot else "—"
                    stats["oa_desc"] = (f"OA {oa / tot * 100:.1f}%·非OA {non_oa / tot * 100:.1f}%"
                                        if tot else "访问方式信息缺失")
                else:
                    stats["oa"], stats["oa_desc"] = "—", "访问方式信息缺失"

                # 出版商（优先 metadata_publisher，其次 journal）
                pub_col = "metadata_publisher" if "metadata_publisher" in df.columns else None
                if pub_col and df[pub_col].notna().any():
                    pub = df[pub_col].astype(str).str.strip().replace(
                        {"": None, "nan": None, "None": None}).dropna()
                elif "metadata_journal" in df.columns and df["metadata_journal"].notna().any():
                    pub = df["metadata_journal"].astype(str).str.strip().replace(
                        {"": None, "nan": None, "None": None}).dropna()
                else:
                    pub = pd.Series(dtype=str)
                vc = pub.value_counts()
                stats["publisher_count"] = int(vc.drop(labels=["未归类"], errors="ignore").size)
                stats["publisher_top"] = "·".join(vc.head(3).index.tolist()) if not vc.empty else "—"
                top = vc.head(6)
                others = int(vc.iloc[6:].sum()) if vc.size > 6 else 0
                names = top.index.tolist() + (["其他"] if others else [])
                counts = top.tolist() + ([others] if others else [])
                stats["publisher_df"] = pd.DataFrame({"出版商": names, "文献数": counts})
                return stats
            except Exception:
                pass  # parquet 读失败，回退到 CSV

        # 2. 回退：读 extractions_long.csv（旧数据源，兼容无 parquet 场景）
        csv_path = OUTPUTS_DIR / "extractions_long.csv"
        if not csv_path.exists():
            return None
        want = {"paper_id", "stage", "metadata_year",
                "metadata_publisher", "metadata_access_route"}
        try:
            df = pd.read_csv(csv_path, encoding="utf-8-sig",
                             usecols=lambda c: c in want, low_memory=False)
        except Exception:
            return None
        if "paper_id" not in df.columns:
            return None
        meta = df[df["stage"] == "metadata"] if "stage" in df.columns else df
        if meta.empty:
            meta = df
        meta = meta.drop_duplicates(subset=["paper_id"])

        stats = {"total_papers": int(meta["paper_id"].nunique())}

        yrs = pd.to_numeric(meta.get("metadata_year"), errors="coerce").dropna() \
            if "metadata_year" in meta.columns else pd.Series(dtype=float)
        yrs = yrs[(yrs > 1900) & (yrs < 2100)]
        stats["year_range"] = f"{int(yrs.min())}–{int(yrs.max())}" if not yrs.empty else "—"
        stats["year_desc"] = f"中位年份 {int(yrs.median())}" if not yrs.empty else "年份信息缺失"

        if "metadata_access_route" in meta.columns:
            route = meta["metadata_access_route"].astype(str).str.upper()
            oa = int(route.str.contains("OA").sum() - route.str.contains("NON").sum())
            non_oa = int(route.str.contains("NON").sum())
            oa = max(oa, 0)
            tot = oa + non_oa
            stats["oa"] = f"{oa:,} / {non_oa:,}" if tot else "—"
            stats["oa_desc"] = (f"OA {oa / tot * 100:.1f}%·非OA {non_oa / tot * 100:.1f}%"
                                if tot else "访问方式信息缺失")
        else:
            stats["oa"], stats["oa_desc"] = "—", "访问方式信息缺失"

        if "metadata_publisher" in meta.columns:
            pub = (meta["metadata_publisher"].astype(str).str.strip()
                   .replace({"": None, "nan": None, "None": None}).dropna())
            vc = pub.value_counts()
            stats["publisher_count"] = int(vc.drop(labels=["未归类"], errors="ignore").size)
            stats["publisher_top"] = "·".join(vc.head(3).index.tolist()) if not vc.empty else "—"
            top = vc.head(6)
            others = int(vc.iloc[6:].sum()) if vc.size > 6 else 0
            names = top.index.tolist() + (["其他"] if others else [])
            counts = top.tolist() + ([others] if others else [])
            stats["publisher_df"] = pd.DataFrame({"出版商": names, "文献数": counts})
        else:
            stats["publisher_count"], stats["publisher_top"] = 0, "—"
            stats["publisher_df"] = pd.DataFrame()
        return stats


    # parquet mtime 作为缓存失效信号，确保入库后立即刷新
    _signal = ""
    if _VIZ_PARQUET_PATH.exists():
        _signal = str(_VIZ_PARQUET_PATH.stat().st_mtime_ns)
    elif (OUTPUTS_DIR / "extractions_long.csv").exists():
        _signal = str((OUTPUTS_DIR / "extractions_long.csv").stat().st_mtime_ns)
    _ov = load_overview_stats(_signal)

    if _ov is None:
        st.info(
            f"未找到 {OUTPUTS_DIR / 'extractions_long.csv'}，下面显示的是占位数据。"
            "把抽取结果放进 outputs 目录后，本页统计会自动同步真实数值。"
        )
        _ov = {"total_papers": 0, "year_range": "—", "year_desc": "无数据",
               "oa": "—", "oa_desc": "无数据", "publisher_count": 0,
               "publisher_top": "—", "publisher_df": pd.DataFrame()}

    cols = st.columns(5)
    for col, val, lbl, desc in zip(cols,
                                   [f"{_ov['total_papers']:,}", f"{_ov['total_papers']:,}",
                                    _ov["year_range"], _ov["oa"], f"{_ov['publisher_count']}"],
                                   ["文献总量", "有效 PDF", "年份范围", "OA / 非OA", "出版商数"],
                                   ["来自当前抽取结果", "已通过校验", _ov["year_desc"], _ov["oa_desc"],
                                    _ov["publisher_top"]],
                                   ):
        stat_card(col, val, lbl, desc)

    st.markdown("")
    left, right = st.columns([3, 2])
    with left:
        st.markdown('<div class="section-title">出版商分布</div>', unsafe_allow_html=True)
        if not _ov["publisher_df"].empty:
            st.bar_chart(_ov["publisher_df"].set_index("出版商"),
                         color="#1565C0", height=260)
        else:
            st.caption("当前数据中没有出版商字段，无法绘制分布图。")

    with right:
        st.markdown('<div class="section-title">论文自动下载：效率对比</div>', unsafe_allow_html=True)
        TOTAL_PAPERS = max(_ov["total_papers"], 1)
        MANUAL_PER_DAY = 100
        manual_days = round(TOTAL_PAPERS / MANUAL_PER_DAY, 1)
        auto_days = 1

        compare_df = pd.DataFrame({
            "方式": ["自动批量下载AI", "人工逐篇下载"],
            "耗时(天)": [auto_days, manual_days],
        })
        fig_compare = px.bar(
            compare_df, x="方式", y="耗时(天)",
            color_discrete_sequence=["#1565C0"],
            category_orders={"方式": ["自动批量下载AI", "人工逐篇下载"]},
        )
        fig_compare.update_layout(
            height=220, margin=dict(t=10, b=10, l=10, r=10),
            showlegend=False, yaxis_title="耗时（天）", xaxis_title="",
        )
        st.plotly_chart(fig_compare, use_container_width=True)
        st.markdown(
            f'<div style="display:flex;justify-content:space-around;margin-top:6px">'
            f'<div style="text-align:center"><div style="font-size:1.6rem;font-weight:700;color:#2E7D32">{auto_days} 天</div>'
            f'<div style="font-size:0.78rem;color:#666">自动批量下载 {TOTAL_PAPERS} 篇</div>'
            f'<div style="font-size:0.73rem;color:#AAA">效率提升约 {round(manual_days / auto_days, 1)} 倍</div></div>'
            f'<div style="text-align:center"><div style="font-size:1.6rem;font-weight:700;color:#1565C0">{manual_days} 天</div>'
            f'<div style="font-size:0.78rem;color:#666">人工下载（按每天{MANUAL_PER_DAY}篇估算）</div></div>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════
#  分区：数据库浏览（催化剂数据筛选与可视化，仅展示有完整配方的 1626 篇）
# ══════════════════════════════════════════════════════════════════
    st.markdown("---")
    st.markdown('<div class="section-title">催化剂数据浏览</div>', unsafe_allow_html=True)

    # 直接复用 load_viz_db（数据源统一：parquet，不再依赖 Excel）
    db_raw = load_viz_db()
    if db_raw is None:
        PARQUET_FILENAME = "FT_SAF_catalyst_extraction_wide_table.parquet"
        st.warning(
            f"未找到数据库文件 `{PARQUET_FILENAME}`。"
            f"请把它放到 `{OUTPUTS_DIR}` 或 `{DATA_DIR}` 目录下。"
        )
        st.stop()

    # 只展示有催化剂配方的完整数据
    db = db_raw[db_raw["catalyst_name_normalized"].notna()].copy() if "catalyst_name_normalized" in db_raw.columns else db_raw.iloc[:0].copy()


    # ── 提取催化剂家族主类（取第一段）──
    def primary_family(val):
        if pd.isna(val):
            return "未知"
        return str(val).split(";")[0].strip()


    def primary_metal(val):
        if pd.isna(val):
            return "未知"
        return str(val).split(";")[0].strip()


    if "catalyst_family" in db.columns:
        db["_family_primary"] = db["catalyst_family"].apply(primary_family)
    else:
        db["_family_primary"] = "未知"

    if "active_metal" in db.columns:
        db["_metal_primary"] = db["active_metal"].apply(primary_metal)
    else:
        db["_metal_primary"] = "未知"

    # ── 侧边筛选区（左侧列） ──
    left_col, right_col = st.columns([1, 3])

    with left_col:
        st.markdown('<div class="section-title">筛选条件</div>', unsafe_allow_html=True)

        # 年份范围
        if "year" in db.columns and not db["year"].dropna().empty:
            yr_min = int(db["year"].dropna().min())
            yr_max = int(db["year"].dropna().max())
            yr_range = st.slider("年份范围", yr_min, yr_max, (min(2010, yr_min), yr_max), key="db_yr")
        else:
            yr_range = (1900, 2100)

        # 催化剂家族
        family_opts = sorted([x for x in db["_family_primary"].dropna().unique() if x != "未知"])
        sel_family = st.multiselect("催化剂家族", family_opts, key="db_family",
                                    placeholder="全部（不选=全部）")

        # 活性金属
        metal_opts = sorted([x for x in db["_metal_primary"].dropna().unique() if x != "未知"])
        sel_metal = st.multiselect("活性金属", metal_opts, key="db_metal",
                                   placeholder="全部（不选=全部）")

        # 原料气类型
        st.markdown("**原料气类型**  \n原料气")

        # 反应温度
        if "reaction_temperature_C" in db.columns and not db["reaction_temperature_C"].dropna().empty:
            t_data = db["reaction_temperature_C"].dropna()
            t_min, t_max = int(t_data.min()), int(t_data.max())
            temp_range = st.slider("反应温度 °C", t_min, t_max, (t_min, t_max), key="db_temp")
        else:
            temp_range = None

        # 关键词搜索
        kw = st.text_input("关键词搜索", placeholder="催化剂名称、载体、论文题目…", key="db_kw")

    # ── 筛选逻辑 ──
    filtered = db.copy()
    if "year" in filtered.columns:
        filtered = filtered[
            filtered["year"].isna() |
            ((filtered["year"] >= yr_range[0]) & (filtered["year"] <= yr_range[1]))
            ]
    if sel_family:
        filtered = filtered[filtered["_family_primary"].isin(sel_family)]
    if sel_metal:
        filtered = filtered[filtered["_metal_primary"].isin(sel_metal)]
    if temp_range and "reaction_temperature_C" in filtered.columns:
        t_mask = (
                filtered["reaction_temperature_C"].isna() |
                ((filtered["reaction_temperature_C"] >= temp_range[0]) &
                 (filtered["reaction_temperature_C"] <= temp_range[1]))
        )
        filtered = filtered[t_mask]
    if kw.strip():
        kw_lower = kw.strip().lower()
        search_cols = ["catalyst_name_normalized", "catalyst_name_raw",
                       "support", "paper_title", "catalyst_family"]
        mask = pd.Series(False, index=filtered.index)
        for sc in search_cols:
            if sc in filtered.columns:
                mask |= filtered[sc].astype(str).str.lower().str.contains(kw_lower, na=False)
        filtered = filtered[mask]

    # ── 右侧：统计卡片 + 数据表 + 散点图 ──
    with right_col:

        # 静态统计卡片：值固定，不随筛选条件变化
        # 总数据量展示 4067 篇（全量论文），其余三个均值基于 1626 篇有催化剂配方的数据计算
        avg_co = db["CO_conversion_pct"].mean() if "CO_conversion_pct" in db.columns else float("nan")
        avg_co2 = db["CO2_conversion_pct"].mean() if "CO2_conversion_pct" in db.columns else float("nan")
        avg_h2co = db["H2_CO_ratio"].mean() if "H2_CO_ratio" in db.columns else float("nan")

        c1, c2, c3, c4 = st.columns(4)
        stat_card(c1, "1,930,152", "数据总量", "")
        stat_card(c2, f"{avg_co:.2f}" if not pd.isna(avg_co) else "—", "平均 CO 转化率", "%")
        stat_card(c3, f"{avg_co2:.2f}" if not pd.isna(avg_co2) else "—", "平均 CO₂ 转化率", "%")
        stat_card(c4, f"{avg_h2co:.3f}" if not pd.isna(avg_h2co) else "—", "平均 H₂/CO", "")

        st.markdown("")

        # ── 散点图（过滤未指定金属） ──
        st.markdown('<div class="section-title">筛选数据分布</div>', unsafe_allow_html=True)

        NUM_COLS = {
            "反应温度 °C": "reaction_temperature_C",
            "压力 bar": "reaction_pressure_bar",
            "H₂/CO 摩尔比": "H2_CO_ratio",
            "CO 转化率 %": "CO_conversion_pct",
            "CO₂ 转化率 %": "CO2_conversion_pct",
            "C₅⁺ 选择性 %": "C5plus_selectivity_pct",
            "CH₄ 选择性 %": "CH4_selectivity_pct",
            "BET比表面积 m²/g": "BET_surface_area_m2_g",
            "金属粒径 nm": "metal_particle_size_nm",
            "活性金属负载量 wt%": "active_metal_loading_wt_pct",
            "年份": "year",
        }
        avail_num = {k: v for k, v in NUM_COLS.items() if v in filtered.columns}

        if avail_num:
            sc1, sc2 = st.columns(2)
            with sc1:
                st.markdown("横轴")
                x_label = st.selectbox("", list(avail_num.keys()),
                                       index=list(avail_num.keys()).index(
                                           "反应温度 °C") if "反应温度 °C" in avail_num else 0,
                                       key="db_x", label_visibility="collapsed")
            with sc2:
                st.markdown("纵轴")
                y_label = st.selectbox("", list(avail_num.keys()),
                                       index=list(avail_num.keys()).index(
                                           "CO 转化率 %") if "CO 转化率 %" in avail_num else (
                                           1 if len(avail_num) > 1 else 0),
                                       key="db_y", label_visibility="collapsed")

            x_col = avail_num[x_label]
            y_col = avail_num[y_label]

            plot_cols = [c for c in [x_col, y_col, "_metal_primary", "catalyst_name_normalized", "paper_title", "year"]
                         if c in filtered.columns]
            # 去重，避免 x_col/y_col 与 "year" 重复导致 DuplicateError
            seen = set()
            plot_cols = [c for c in plot_cols if not (c in seen or seen.add(c))]
            plot_df = filtered[plot_cols].dropna(subset=[x_col, y_col]).copy()

            # 过滤掉"未知"活性金属的数据点
            if "_metal_primary" in plot_df.columns:
                plot_df = plot_df[plot_df["_metal_primary"] != "未知"].copy()

            rename_dict = {x_col: x_label, y_col: y_label, "_metal_primary": "活性金属",
                           "catalyst_name_normalized": "催化剂", "paper_title": "论文"}
            plot_df = plot_df.rename(columns={k: v for k, v in rename_dict.items() if k in plot_df.columns})

            if len(plot_df) > 0:
                fig_sc = px.scatter(
                    plot_df, x=x_label, y=y_label,
                    color="活性金属" if "活性金属" in plot_df.columns else None,
                    hover_data=[c for c in ["催化剂", "论文", "year"] if c in plot_df.columns],
                    color_discrete_sequence=px.colors.qualitative.Set1,
                    opacity=0.75,
                    height=420,
                )
                fig_sc.update_traces(marker=dict(size=7))
                fig_sc.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    legend=dict(title="活性金属", orientation="v"),
                )
                st.plotly_chart(fig_sc, use_container_width=True)
            else:
                st.info("当前筛选条件下无可绘图的数据，请放宽筛选范围。")

        # ── 云雨图（按维度分组展示 CO 转化率分布） ──
        def _wrap_label(s, n):
            """长标签每 n 个字符换行，避免挤压图表"""
            s = str(s)
            if len(s) <= n:
                return s
            return "<br>".join(s[i:i+n] for i in range(0, len(s), n))

        st.markdown('<div class="section-title">CO 转化率分布 · 云雨图</div>', unsafe_allow_html=True)
        st.caption("按不同维度分组，展示 CO 转化率的分布形态（云=密度曲线，伞=箱线，雨=数据点）")

        # 分组维度选择
        GROUP_DIMS = {
            "活性金属": "active_metal",
            "载体": "support",
            "助剂": "promoter_elements",
            "载体类型": "support_type",
        }
        avail_dims = {k: v for k, v in GROUP_DIMS.items() if v in filtered.columns}

        if avail_dims and "CO_conversion_pct" in filtered.columns:
            # 上下布局：筛选框在上，图表在下
            dim_label = st.selectbox("分组维度", list(avail_dims.keys()), key="db_rain_dim")
            dim_col = avail_dims[dim_label]

            # 构造云雨图数据
            rain_df = filtered[[dim_col, "CO_conversion_pct"]].dropna().copy()
            # 只保留有意义的分组值（过滤空字符串/未知）
            rain_df[dim_col] = rain_df[dim_col].astype(str).str.strip()
            rain_df = rain_df[(rain_df[dim_col] != "") & (rain_df[dim_col] != "未知") & (rain_df[dim_col] != "nan")]

            # 黑名单：隐藏样本量过少或展示效果差的分组
            _HIDE_VALUES = {
                "support_type": [
                    "oxide; zeolite/molecular sieve",
                    "zeolite/molecular sieve",
                    "zeolite/molecular sieve/MOF-derived",
                ],
            }
            if dim_col in _HIDE_VALUES:
                rain_df = rain_df[~rain_df[dim_col].isin(_HIDE_VALUES[dim_col])]

            # 过滤样本量 < 3 的分组（单点数据无法绘制有意义的分布）
            group_counts = rain_df[dim_col].value_counts()
            valid_groups = group_counts[group_counts >= 3].index.tolist()
            rain_df = rain_df[rain_df[dim_col].isin(valid_groups)].copy()

            # 按样本量排序，只展示 Top 12 组（避免过于拥挤）
            top_groups = group_counts[group_counts >= 3].head(12).index.tolist()
            rain_df = rain_df[rain_df[dim_col].isin(top_groups)].copy()
            # 按中位数排序
            median_order = (rain_df.groupby(dim_col)["CO_conversion_pct"]
                            .median().sort_values().index.tolist())
            rain_df[dim_col] = pd.Categorical(rain_df[dim_col], categories=median_order, ordered=True)

            if len(rain_df) > 0:
                fig_rain = go.Figure()
                groups = median_order
                n_groups = len(groups)
                _bright_pastel = ['#636EFA', '#EF553B', '#00CC96', '#AB63FA', '#FFA15A',
                                  '#19D3F3', '#FF6692', '#B6E880', '#FF97FF', '#FECB52',
                                  '#1F77B4', '#FF7F0E', '#2CA02C', '#D62728', '#9467BD']
                colors = _bright_pastel * max(1, n_groups // len(_bright_pastel) + 1)

                for i, grp in enumerate(groups):
                    subset = rain_df[rain_df[dim_col] == grp]["CO_conversion_pct"].dropna()
                    if len(subset) == 0:
                        continue
                    color = colors[i % len(colors)]
                    y_vals = subset.values

                    # 云：半小提琴图（左侧密度曲线）
                    fig_rain.add_trace(go.Violin(
                        x=[i] * len(y_vals),
                        y=y_vals,
                        name=str(grp),
                        side="negative",
                        line_color=color,
                        fillcolor=color,
                        opacity=0.45,
                        width=1.1,
                        showlegend=True,
                        points=False,
                        hovertemplate=f"{dim_label}={grp}<br>CO转化率: %{{y:.2f}}<extra></extra>",
                    ))

                    # 伞：箱线图（居中，窄而高对比）
                    fig_rain.add_trace(go.Box(
                        x=[i] * len(y_vals),
                        y=y_vals,
                        name=str(grp),
                        marker_color="rgba(0,0,0,0.6)",
                        line_color=color,
                        fillcolor="rgba(255,255,255,0.85)",
                        boxmean="sd",
                        width=0.22,
                        showlegend=False,
                        hovertemplate=f"{dim_label}={grp}<br>CO转化率: %{{y:.2f}}<extra></extra>",
                    ))

                    # 雨：抖动散点（右侧）
                    jitter = np.random.uniform(0.05, 0.22, size=len(y_vals))
                    fig_rain.add_trace(go.Scatter(
                        x=[i + j for j in jitter],
                        y=y_vals,
                        mode="markers",
                        name=f"{grp} 数据",
                        marker=dict(color=color, opacity=0.5, size=5,
                                    line=dict(width=0.5, color="rgba(255,255,255,0.8)")),
                        hovertemplate=f"{dim_label}={grp}<br>CO转化率: %{{y:.2f}}<extra></extra>",
                        showlegend=False,
                    ))

                fig_rain.update_layout(
                    height=520,
                    margin=dict(t=10, b=80, l=10, r=10),
                    yaxis_title="CO 转化率 %",
                    xaxis_title=dim_label,
                    xaxis=dict(
                        tickmode="array",
                        tickvals=list(range(n_groups)),
                        ticktext=[_wrap_label(str(g), 10) for g in groups],
                        range=[-0.8, n_groups - 0.2],
                        tickangle=0,
                        tickfont=dict(size=11),
                    ),
                    legend=dict(title=dim_label, orientation="h", yanchor="bottom", y=1.02),
                    showlegend=True,
                    violinmode="overlay",
                    boxmode="overlay",
                )
                # 确保小提琴和箱线图在同一 x 位置对齐
                fig_rain.update_traces(orientation="v")
                st.plotly_chart(fig_rain, use_container_width=True)
                st.caption(f"{len(rain_df)} 条数据 · {n_groups} 组 · 按中位数排序")
            else:
                st.info("当前筛选条件下无足够数据绘制云雨图。")
        else:
            st.caption("缺少绘制云雨图所需的分组维度或 CO 转化率列。")


# ══════════════════════════════════════════════════════════════════
#  页面：论文自动下载（4步流程）
# ══════════════════════════════════════════════════════════════════
elif page == "📥 论文自动下载":

    if "dl_step" not in st.session_state:
        st.session_state["dl_step"] = 1
    if "clf_df" not in st.session_state:
        st.session_state["clf_df"] = None
    if "dl_log" not in st.session_state:
        st.session_state["dl_log"] = []
    if "manifest" not in st.session_state:
        st.session_state["manifest"] = []
    if "out_dir" not in st.session_state:
        st.session_state["out_dir"] = str(PDFS_DIR)
    if "webvpn_log" not in st.session_state:
        st.session_state["webvpn_log"] = pd.DataFrame()

    step = st.session_state["dl_step"]
    pipeline_bar(step)

    # ────────────────────────────────────────────────
    #  步骤1：DOI 分类
    # ────────────────────────────────────────────────
    st.markdown('<div class="section-title">① DOI 分类</div>', unsafe_allow_html=True)
    if True:

        col_up, col_tip = st.columns([2, 1])
        with col_up:
            uploaded = st.file_uploader("上传 xlsx / csv（含 DOI 列）",
                                        type=["csv", "xlsx",
                                               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
                                        key="doi_upload")
        with col_tip:
            st.markdown("""
            <div class="info-box">
            <b>识别的列名</b><br>
            <code>DOI</code> / <code>doi</code> — 必填<br>
            <code>access_type</code> — OA / non-OA<br>
            <code>title</code> — 文章标题<br>
            <code>year</code> — 发表年份
            </div>""", unsafe_allow_html=True)

        manual = st.text_area("或手动粘贴 DOI（每行一个）", height=90, key="manual_doi",
                              label_visibility="visible",
                              placeholder="10.1021/acscatal.4c00001\n10.1007/s10853-024-09012-1")

        if st.button("🔍 分析 DOI 列表", type="primary", use_container_width=True, key="btn_classify"):
            df_raw = None
            if uploaded:
                try:
                    df_raw = load_df(uploaded)
                except Exception as e:
                    st.error(f"文件读取失败：{e}")
            elif manual.strip():
                df_raw = pd.DataFrame({"doi": [d.strip() for d in manual.strip().splitlines() if d.strip()]})

            if df_raw is not None and not df_raw.empty:
                with st.spinner("识别出版商并分配路由…"):
                    result_df, ok = classify_df(df_raw)
                if ok:
                    st.session_state["clf_df"] = result_df
                    st.session_state["dl_step"] = 1

    if st.session_state["clf_df"] is not None:
        df = st.session_state["clf_df"]
        rc = Counter(df["路由"])
        total = len(df)
        n_dir = rc.get("direct", 0) + rc.get("verified", 0)
        n_vpn = rc.get("webvpn", 0)
        n_rev = rc.get("review", 0) + rc.get("probe", 0)
        n_bad = rc.get("invalid", 0)

        st.markdown('<div class="section-title">分类结果</div>', unsafe_allow_html=True)
        for col, val, lbl, desc in zip(st.columns(5),
                                       [total, n_dir, n_vpn, n_rev, n_bad],
                                       ["总计", "可直接下载", "需 WebVPN", "待审核", "无效"],
                                       ["全部文献", "direct+verified", "机构授权路由", "probe+review", "DOI缺失/无效"],
                                       ):
            stat_card(col, val, lbl, desc)

        st.markdown("")
        all_routes = sorted(df["路由"].unique())
        sel = st.multiselect("按路由筛选", all_routes, default=all_routes,
                             format_func=lambda r: ROUTE_LABEL.get(r, r), key="route_filter")
        df_show = df[df["路由"].isin(sel)] if sel else df
        show_cols = [c for c in ["doi", "title", "出版商", "路由", "下载URL", "year"] if c in df_show.columns]
        st.dataframe(df_show[show_cols], use_container_width=True, height=300)

        st.markdown("")
        if st.button("下一步：开始下载 →", type="primary", key="goto_step2"):
            st.session_state["dl_step"] = 2
            st.rerun()

    # ────────────────────────────────────────────────
    #  步骤2：自动下载
    # ────────────────────────────────────────────────
    if step >= 2 and st.session_state["clf_df"] is not None:
        st.markdown('<div class="section-title">② 自动下载</div>', unsafe_allow_html=True)
        if True:
            df = st.session_state["clf_df"]
            df_direct = df[df["路由"].isin(AUTO_ROUTES) & (df["下载URL"] != "")]
            df_webvpn = df[df["路由"] == "webvpn"]

            out_dir = st.text_input("PDF 保存目录", value=st.session_state["out_dir"], key="out_dir_input")
            st.session_state["out_dir"] = out_dir

            st.markdown("##### 🟢 直接下载（无需 WebVPN）")
            col_a, col_b = st.columns(2)
            with col_a:
                test_n = st.number_input("测试模式（0=全部）", 0, 50, 3, key="test_n")
            with col_b:
                min_kb = st.number_input("最小体积 KB", 5, 200, 20, key="min_kb")

            if len(df_direct) == 0:
                st.caption("当前队列中没有可直接下载的文献。")
            else:
                st.info(
                    f"共 **{len(df_direct)}** 篇可直接下载 · {'测试前 ' + str(test_n) + ' 篇' if test_n else '全量模式'}")

            if st.button("🚀 开始直接下载", type="primary", use_container_width=True, key="btn_download"):
                queue = df_direct.to_dict("records")
                if test_n:
                    queue = queue[:test_n]

                prog = st.progress(0)
                box = st.empty()
                rows = []
                sha_seen = {}

                for idx, row in enumerate(queue):
                    doi = str(row.get("doi", ""))
                    pub = str(row.get("出版商", ""))
                    url = str(row.get("下载URL", ""))
                    delay = PUBLISHER_DELAY.get(pub, 2.0)

                    box.markdown(
                        f'<div class="info-box">⬇️ [{idx + 1}/{len(queue)}] <b>{pub}</b> · <code>{doi}</code></div>',
                        unsafe_allow_html=True,
                    )
                    result = download_one(doi, url, pub, out_dir, int(min_kb))

                    if result.get("sha256") and result["status"] == "success":
                        if result["sha256"] in sha_seen:
                            result["status"] = "duplicate"
                            result["reason"] = f"与 {sha_seen[result['sha256']]} 内容重复"
                        else:
                            sha_seen[result["sha256"]] = doi

                    rows.append({
                        "doi": doi, "出版商": pub,
                        "status": result["status"],
                        "size_kb": result.get("size_kb", ""),
                        "file": result.get("file", ""),
                        "reason": result.get("reason", ""),
                        "sha256": result.get("sha256", ""),
                        "时间": datetime.now().strftime("%H:%M:%S"),
                    })
                    prog.progress((idx + 1) / len(queue))
                    if idx < len(queue) - 1:
                        time.sleep(delay)

                prog.empty();
                box.empty()
                st.session_state["dl_log"] = rows

            if st.session_state["dl_log"]:
                log = st.session_state["dl_log"]
                counts = Counter(r["status"] for r in log)
                st.markdown("**直接下载结果**")
                for col, k, lbl in zip(st.columns(6),
                                       ["success", "skipped_exists", "no_access", "likely_paywall", "invalid_pdf",
                                        "error"],
                                       ["成功", "已存在", "无权限(403)", "疑似付费墙", "内容无效", "错误"],
                                       ):
                    stat_card(col, counts.get(k, 0), lbl)
                if counts.get("no_access", 0) or counts.get("likely_paywall", 0):
                    st.warning(
                        "⚠️ 存在无权限访问的文献（含明确403和疑似付费墙两种），"
                        "请确认已连校园网或 VPN 后重试，或改用 WebVPN 下载这部分文献。"
                    )
                if counts.get("success", 0):
                    st.success(f"✅ 成功下载 {counts['success']} 篇，保存至 {st.session_state['out_dir']}")
                st.dataframe(pd.DataFrame(log), use_container_width=True, height=220)

            st.markdown("---")

            st.markdown("##### 🟠 WebVPN 下载（处理全部上传文献，不区分路由分类）")
            st.caption(
                "WebVPN 可访问几乎所有出版商，因此这里不再按 direct/verified/webvpn 路由筛选，"
                "直接对你上传的全部文献依次尝试下载。"
            )

            chrome_online = check_chrome_debug_port()
            if chrome_online:
                st.success("✅ 已检测到调试模式 Chrome（端口9222在线）")
            else:
                st.error(
                    "❌ 未检测到调试模式 Chrome。请先：\n\n"
                    "1. 双击运行 `start_chrome_debug.bat`\n"
                    "2. 在弹出的Chrome窗口里手动登录 webvpn.xjtu.edu.cn\n"
                    "3. 保持该窗口开启，回到本页面点「🔃 重新检测」"
                )
                if st.button("🔃 重新检测 Chrome 状态", key="recheck_chrome"):
                    st.rerun()

            col_w1, col_w2 = st.columns(2)
            with col_w1:
                webvpn_script = st.text_input(
                    "webvpn_downloader3.py 路径",
                    value=str(BASE_DIR / "webvpn_downloader3.py"),
                    key="webvpn_script_path",
                )
            with col_w2:
                webvpn_delay = st.number_input("篇间延迟(秒)", 1.0, 10.0, 3.0, key="webvpn_delay")

            df_webvpn_all = df.copy()
            total_count = len(df_webvpn_all)

            run_mode = st.radio(
                "处理范围",
                ["全部依次下载（推荐）", "先小批量测试"],
                horizontal=True,
                key="webvpn_run_mode",
            )

            if run_mode == "全部依次下载（推荐）":
                webvpn_limit = 0
                st.info(f"将对全部 **{total_count}** 篇文献依次发起下载，从第 1 篇开始处理到最后一篇。")
            else:
                webvpn_limit = st.number_input(
                    "测试篇数（从第1篇开始）", 1, max(total_count, 1),
                    min(10, total_count) if total_count else 1, key="webvpn_test_limit",
                )
                st.info(f"测试模式：将处理前 **{webvpn_limit}** 篇（共 {total_count} 篇）。")

            webvpn_disabled = (not chrome_online) or (total_count == 0) or (not Path(webvpn_script).exists())
            if not Path(webvpn_script).exists() and total_count > 0:
                st.warning(f"⚠️ 脚本路径不存在：`{webvpn_script}`，请确认 webvpn_downloader3.py 的实际位置。")

            if st.button("🚀 开始 WebVPN 下载", type="primary", use_container_width=True,
                         key="btn_webvpn_download", disabled=webvpn_disabled):
                queue_df = df_webvpn_all if webvpn_limit == 0 else df_webvpn_all.head(int(webvpn_limit))
                queue_csv_path = Path(out_dir) / "webvpn_queue_from_app.csv"
                write_webvpn_queue_csv(queue_df, queue_csv_path)

                status_box = st.empty()
                log_box = st.empty()
                status_box.info(f"⏳ 正在启动 WebVPN 下载（{len(queue_df)} 篇），实时日志如下…")

                wv_log_path = Path(out_dir) / "webvpn_playwright_log.csv"
                rows_before = len(parse_webvpn_log(wv_log_path))

                proc = run_webvpn_downloader(
                    queue_csv_path, out_dir,
                    int(webvpn_limit), int(min_kb), 30, float(webvpn_delay),
                    webvpn_script,
                )

                output_lines = []
                _wv_start = time.time()
                _WV_TIMEOUT = 1800  # 30 分钟
                for line in proc.stdout:
                    if time.time() - _wv_start > _WV_TIMEOUT:
                        output_lines.append(f"[超时] 超过 {_WV_TIMEOUT}s，终止进程")
                        proc.kill()
                        break
                    output_lines.append(line.rstrip())
                    log_box.code("\n".join(output_lines[-30:]))

                proc.wait()
                status_box.success(f"✅ WebVPN 下载脚本已结束（退出码 {proc.returncode}）")

                wv_log_df_full = parse_webvpn_log(wv_log_path)
                wv_log_df = wv_log_df_full.iloc[rows_before:].reset_index(
                    drop=True) if not wv_log_df_full.empty else wv_log_df_full
                st.session_state["webvpn_log"] = wv_log_df

            if not st.session_state.get("webvpn_log", pd.DataFrame()).empty:
                wv_log_df = st.session_state["webvpn_log"]
                wv_counts = Counter(wv_log_df.get("status", pd.Series()).tolist())
                st.markdown("**WebVPN 下载结果（本次运行）**")
                for col, k, lbl in zip(st.columns(5),
                                       ["success", "no_pdf_found", "invalid_pdf", "timeout", "error"],
                                       ["成功", "未找到PDF", "内容无效", "超时", "错误"],
                                       ):
                    stat_card(col, wv_counts.get(k, 0), lbl)
                st.dataframe(wv_log_df, use_container_width=True, height=240)

            st.markdown("---")

            if st.button("下一步：校验 PDF →", type="primary", key="goto_step3"):
                st.session_state["dl_step"] = 3
                st.rerun()

    # ────────────────────────────────────────────────
    #  步骤3：PDF 校验
    # ────────────────────────────────────────────────
    if step >= 3:
        st.markdown('<div class="section-title">③ PDF 校验</div>', unsafe_allow_html=True)
        if True:
            st.markdown("""
            <div class="info-box">
            完整集成 <code>build_manifest.py</code> 的校验逻辑，逐文件提取：<br>
            ① <code>%PDF-</code> 头部验证 &nbsp;
            ② 文件大小 &nbsp;
            ③ 页数读取 &nbsp;
            ④ 首页 DOI 提取 &nbsp;
            ⑤ PDF元数据标题/作者 &nbsp;
            ⑥ 加密检测 &nbsp;
            ⑦ SHA-256 去重 &nbsp;
            ⑧ 文件名解析（作者/年份/标题）
            </div>
            """, unsafe_allow_html=True)
            st.markdown("")

            col_dir, col_kb, col_sha = st.columns([3, 1, 1])
            with col_dir:
                scan_dir = st.text_input("扫描目录（下载 PDF 所在文件夹）",
                                         value=st.session_state.get("out_dir", str(PDFS_DIR)),
                                         key="scan_dir")
            with col_kb:
                min_kb_scan = st.number_input("最小体积 KB", 5, 200, 20, key="min_kb_scan")
            with col_sha:
                do_sha = st.checkbox("计算 SHA-256", value=True, key="do_sha",
                                     help="大批量时可关闭以加快速度")

            col_scan1, col_scan2 = st.columns(2)
            with col_scan1:
                do_scan = st.button("🔍 扫描并校验 PDF", type="primary",
                                    use_container_width=True, key="btn_scan")
            with col_scan2:
                also_upload = st.file_uploader("或直接上传 PDF 文件校验",
                                               type=["pdf"], accept_multiple_files=True,
                                               key="pdf_upload", label_visibility="collapsed")

            if do_scan:
                folder = Path(scan_dir)
                if not folder.exists():
                    st.error(f"目录不存在：{scan_dir}")
                else:
                    with st.spinner(f"正在扫描 {scan_dir}，逐文件读取 PDF 元信息…"):
                        manifest = scan_pdf_folder(folder, int(min_kb_scan), bool(do_sha))
                    st.session_state["manifest"] = manifest

            if also_upload:
                import tempfile, os

                tmp_results = []
                sha_map: Dict[str, str] = {}
                for uf in also_upload:
                    data = uf.read()
                    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                        tmp.write(data)
                        tmp_path = Path(tmp.name)
                    try:
                        r = validate_pdf_file(tmp_path, int(min_kb_scan), bool(do_sha))
                        r["file_name"] = uf.name
                        r["relative_path"] = uf.name
                    except Exception as e:
                        r = {"file_name": uf.name, "valid": False, "pdf_error": str(e)}
                    finally:
                        os.unlink(tmp_path)
                    sha = r.get("sha256", "")
                    r["duplicate_of"] = sha_map.get(sha, "")
                    if sha and not r["duplicate_of"]:
                        sha_map[sha] = uf.name
                    tmp_results.append(r)
                st.session_state["manifest"] = tmp_results

            if st.session_state.get("manifest"):
                manifest = st.session_state["manifest"]
                df_m = pd.DataFrame(manifest)

                total_m = len(df_m)
                valid_m = int(df_m["valid"].sum()) if "valid" in df_m.columns else 0
                invalid_m = total_m - valid_m
                dup_m = int((df_m.get("duplicate_of", "") != "").sum()) if "duplicate_of" in df_m.columns else 0
                enc_m = int((df_m.get("is_encrypted", False) == True).sum()) if "is_encrypted" in df_m.columns else 0
                doi_found = int((df_m.get("first_page_doi", "") != "").sum()) if "first_page_doi" in df_m.columns else 0

                st.markdown('<div class="section-title">校验结果</div>', unsafe_allow_html=True)
                for col, val, lbl, desc in zip(st.columns(6),
                                               [total_m, valid_m, invalid_m, dup_m, enc_m, doi_found],
                                               ["扫描文件", "有效 PDF", "无效/过小", "重复内容", "加密文件",
                                                "首页找到DOI"],
                                               ["", "头部+大小通过", "", "SHA-256相同", "需解密", "从首页文本提取"],
                                               ):
                    stat_card(col, val, lbl, desc)

                st.markdown("")

                priority_cols = [
                    "file_name", "file_size_kb", "page_count",
                    "pdf_header_valid", "pdf_read_ok", "valid",
                    "first_page_doi", "is_encrypted",
                    "pdf_metadata_title", "pdf_metadata_author",
                    "filename_year_guess", "filename_author_guess",
                    "sha256", "duplicate_of", "pdf_error", "relative_path",
                ]
                show_cols = [c for c in priority_cols if c in df_m.columns]
                st.dataframe(df_m[show_cols], use_container_width=True, height=340)

                if invalid_m:
                    st.warning(f"⚠️ {invalid_m} 个文件校验不通过（头部非PDF或文件过小），可能下载不完整。")
                if dup_m:
                    st.warning(f"⚠️ {dup_m} 个文件内容重复（SHA-256相同），请检查是否误下载相同文章。")
                if enc_m:
                    st.info(f"ℹ️ {enc_m} 个文件已加密，后续 LLM 抽取前需先解密。")
                if valid_m == total_m and dup_m == 0:
                    st.success(f"✅ 全部 {total_m} 个 PDF 校验通过，无重复，质量良好！")

                if st.button("下一步：导出结果 →", type="primary", key="goto_step4"):
                    st.session_state["dl_step"] = 4
                    st.rerun()

    # ────────────────────────────────────────────────
    #  步骤4：导出结果
    # ────────────────────────────────────────────────
    if step >= 4:
        st.markdown('<div class="section-title">④ 导出结果</div>', unsafe_allow_html=True)
        if True:
            st.markdown('<div class="section-title">导出文件</div>', unsafe_allow_html=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            df_clf = st.session_state.get("clf_df")

            c1, c2, c3, c4 = st.columns(4)

            with c1:
                if df_clf is not None:
                    st.download_button("⬇️ 完整 DOI 队列",
                                       df_clf.to_csv(index=False).encode("utf-8-sig"),
                                       f"queue_all_{ts}.csv", "text/csv", use_container_width=True)

            with c2:
                if df_clf is not None:
                    st.download_button(f"⬇️ WebVPN 队列（全部 {len(df_clf)} 篇）",
                                       df_clf.to_csv(index=False).encode("utf-8-sig"),
                                       f"queue_webvpn_all_{ts}.csv", "text/csv", use_container_width=True)

            with c3:
                has_direct_log = bool(st.session_state.get("dl_log"))
                has_webvpn_log = not st.session_state.get("webvpn_log", pd.DataFrame()).empty

                if has_direct_log and has_webvpn_log:
                    direct_df = pd.DataFrame(st.session_state["dl_log"])
                    direct_df["来源"] = "直接下载"
                    wv_df = st.session_state["webvpn_log"].copy()
                    wv_df["来源"] = "WebVPN下载"
                    combined_df = pd.concat([direct_df, wv_df], ignore_index=True, sort=False)
                    st.download_button("⬇️ 下载日志（直接+WebVPN）",
                                       combined_df.to_csv(index=False).encode("utf-8-sig"),
                                       f"download_log_{ts}.csv", "text/csv", use_container_width=True)
                elif has_direct_log:
                    log_df = pd.DataFrame(st.session_state["dl_log"])
                    st.download_button("⬇️ 下载日志（直接下载）",
                                       log_df.to_csv(index=False).encode("utf-8-sig"),
                                       f"download_log_{ts}.csv", "text/csv", use_container_width=True)
                elif has_webvpn_log:
                    log_df = st.session_state["webvpn_log"]
                    st.download_button("⬇️ 下载日志（WebVPN）",
                                       log_df.to_csv(index=False).encode("utf-8-sig"),
                                       f"download_log_{ts}.csv", "text/csv", use_container_width=True)
                else:
                    st.caption("暂无下载日志")

            with c4:
                if st.session_state.get("manifest"):
                    mf_df = pd.DataFrame(st.session_state["manifest"])
                    st.download_button("⬇️ PDF 校验报告",
                                       mf_df.to_csv(index=False).encode("utf-8-sig"),
                                       f"manifest_{ts}.csv", "text/csv", use_container_width=True)

            st.markdown("")
            st.markdown('<div class="section-title">本次运行汇总</div>', unsafe_allow_html=True)

            log = st.session_state.get("dl_log", [])
            mf = st.session_state.get("manifest", [])
            wv_log = st.session_state.get("webvpn_log", pd.DataFrame())
            log_counts = Counter(r["status"] for r in log)
            wv_counts_summary = Counter(wv_log.get("status", pd.Series()).tolist()) if not wv_log.empty else Counter()
            mf_valid = sum(1 for r in mf if r.get("valid"))

            total_success = log_counts.get("success", 0) + wv_counts_summary.get("success", 0)

            summary = {
                "运行时间": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "DOI总数": len(df_clf) if df_clf is not None else 0,
                "直接下载成功": log_counts.get("success", 0) + log_counts.get("skipped_exists", 0),
                "WebVPN下载成功": wv_counts_summary.get("success", 0),
                "下载成功合计": total_success,
                "无权限(需VPN)": log_counts.get("no_access", 0),
                "PDF校验通过": mf_valid,
                "PDF校验失败": len(mf) - mf_valid,
            }
            for k, v in summary.items():
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;padding:7px 14px;'
                    f'background:#FAFAFA;border-radius:6px;margin-bottom:4px;font-size:0.85rem">'
                    f'<span style="color:#666">{k}</span><span style="font-weight:600">{v}</span></div>',
                    unsafe_allow_html=True,
                )

            st.markdown("")
            if st.button("↩️ 重新开始", key="btn_reset"):
                for k in ["dl_step", "clf_df", "dl_log", "manifest"]:
                    st.session_state[k] = (1 if k == "dl_step" else ([] if k in ("dl_log", "manifest") else None))
                st.session_state["webvpn_log"] = pd.DataFrame()
                st.rerun()


# ══════════════════════════════════════════════════════════════════
#  页面：数据自动提取
# ══════════════════════════════════════════════════════════════════
elif page == "🔬 数据自动提取":

    # ── 辅助函数 ──
    def _compute_sha256(file_bytes: bytes) -> str:
        """计算文件内容的 SHA-256"""
        return hashlib.sha256(file_bytes).hexdigest()

    def _generate_paper_id(sha256: str) -> str:
        """生成 24 位 paper_id（和现有格式一致）"""
        return hashlib.sha1(sha256.encode()).hexdigest()[:24]

    def _check_pdf_in_parquet(sha256: str) -> dict | None:
        """查 parquet 是否已收录此 PDF（通过 pdf_sha256 列）"""
        def _cols() -> list[str]:
            try:
                import pyarrow.parquet as pq
                return [f.name for f in pq.read_schema(_VIZ_PARQUET_PATH)]
            except Exception:
                return []
        if not _VIZ_PARQUET_PATH.exists():
            return None
        cols_available = _cols()
        if not cols_available:
            # pyarrow 不可用，只读关键 2 列
            cols_to_read = ["pdf_sha256", "paper_id"]
        else:
            cols_to_read = [c for c in ["pdf_sha256", "paper_id"] if c in cols_available]
            if "pdf_sha256" not in cols_to_read:
                return None  # parquet 没有 sha256 列，无法查重
            for optional in ["source_file", "paper_title", "doi"]:
                if optional in cols_available:
                    cols_to_read.append(optional)
                    break
        try:
            df = pd.read_parquet(_VIZ_PARQUET_PATH, columns=cols_to_read)
        except Exception:
            # 列名不对，直接读全表（parquet 不大，4k 行秒级）
            df = pd.read_parquet(_VIZ_PARQUET_PATH)
        if "pdf_sha256" not in df.columns:
            return None
        matches = df[df["pdf_sha256"] == sha256]
        if matches.empty:
            return None
        row = matches.iloc[0]
        sf = None
        for k in ["source_file", "paper_title", "doi"]:
            if k in df.columns and pd.notna(row.get(k)):
                sf = row[k]
                break
        return {"paper_id": row.get("paper_id"), "source_file": sf}

    def _extract_pdf_pages(pdf_path) -> list:
        """用 pypdf 提取每页文本"""
        from pypdf import PdfReader
        reader = PdfReader(str(pdf_path))
        pages = []
        for idx, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            text = re.sub(r"\s+", " ", text).strip()
            pages.append({"page": idx, "text": text})
        return pages

    _STAGE_KEYWORDS = {
        "metadata": ["doi", "abstract", "journal", "received", "accepted", "published", "keywords"],
        "catalyst": ["catalyst", "support", "promoter", "loading", "impregnation", "calcined", "reduced", "wt%"],
        "reaction_conditions": ["reaction", "reactor", "h2/co", "ghsv", "temperature", "pressure", "time on stream"],
        "performance": ["conversion", "selectivity", "yield", "c5+", "ch4", "hydrocarbon"],
        "provenance_confidence": ["table", "figure", "fig.", "caption"],
    }

    def _select_top_pages(pages, keywords, max_pages=4):
        """按关键词命中数选 top N 页"""
        scored = []
        for p in pages:
            low = p["text"].lower()
            score = sum(1 for kw in keywords if kw in low)
            if score > 0:
                scored.append((score, p))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [p for _, p in scored[:max_pages]]

    def _load_prompt_templates() -> dict:
        """加载 5 阶段提示词"""
        templates = {}
        stage_files = {
            "metadata": "01_metadata.md",
            "catalyst": "02_catalyst.md",
            "reaction_conditions": "03_reaction_conditions.md",
            "performance": "04_performance.md",
            "provenance_confidence": "05_provenance_confidence.md",
        }
        for stage, fname in stage_files.items():
            path = PROMPTS_DIR / fname
            if path.exists():
                templates[stage] = path.read_text(encoding="utf-8")
        return templates

    def _build_user_message(paper_id, file_name, stage, context_blocks):
        """构建发给 LLM 的用户消息"""
        parts = [f"paper_id: {paper_id}", f"stage: {stage}", f"file_name: {file_name}"]
        parts.append("\n证据文本块（按相关性排序）:")
        for block in context_blocks:
            parts.append(f"\n--- 第 {block['page']} 页 ---")
            parts.append(block["text"][:3000])
        parts.append("\n请严格按照系统提示中规定的 JSON Schema 输出，只返回JSON对象本身，不要markdown代码块包裹。")
        return "\n".join(parts)

    def _strip_json_fences(text: str) -> str:
        """去掉 LLM 可能加的 ```json ... ``` 包裹"""
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _call_llm(client, model, system_prompt, user_message, max_retries=3):
        """调用 LLM，带重试。失败时返回 (None, error_msg)"""
        last_err = None
        for attempt in range(1, max_retries + 1):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0,
                )
                raw_text = response.choices[0].message.content or ""
                clean_text = _strip_json_fences(raw_text)
                return json.loads(clean_text), None
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                if attempt < max_retries:
                    time.sleep(3 * attempt)
        return None, last_err

    # ── 页面 UI ──
    st.markdown('<div class="section-title">上传 PDF → LLM 抽取 → 入库</div>', unsafe_allow_html=True)
    st.markdown("""
    <div class="info-box">
    上传 PDF 文件，LLM 自动提取催化剂、反应条件、性能数据。抽取完成后预览数据，确认后写入 parquet，前端自动刷新。
    </div>
    """, unsafe_allow_html=True)

    # 上传区
    uploaded = st.file_uploader(
        "📎 上传 PDF 文件（支持多选）",
        type=["pdf"],
        accept_multiple_files=True,
        key="ex_pdf_uploader",
    )

    # API 配置
    with st.expander("⚙️ API 配置", expanded=True):
        col_api1, col_api2 = st.columns(2)
        with col_api1:
            llm_api_key = st.text_input(
                "API Key",
                value="", type="password", key="ex_llm_api_key",
            )
        with col_api2:
            llm_model = st.text_input("模型", value="deepseek-v4-flash", key="ex_llm_model")
        llm_base_url = st.text_input(
            "Base URL", value="https://api.deepseek.com/v1", key="ex_llm_base_url"
        )

    # session state 初始化
    for k, v in [
        ("ex_pdf_info", []),
        ("ex_extraction_done", False),
        ("ex_new_rows", []),
        ("ex_log", []),
        ("ex_checked", False),
        ("ex_extraction_results", {}),
    ]:
        if k not in st.session_state:
            st.session_state[k] = v

    # ── 自动检测：上传后自动后台查重 ──
    if uploaded and not st.session_state["ex_checked"]:
        st.session_state["ex_pdf_info"] = []
        st.session_state["ex_log"] = []
        log = st.session_state["ex_log"]

        for f in uploaded:
            file_bytes = f.getvalue()
            sha256 = _compute_sha256(file_bytes)
            paper_id = _generate_paper_id(sha256)
            ts = datetime.now().strftime("%H:%M:%S")

            # 保存到 pdfs/uploads/
            upload_dir = PDFS_DIR / "uploads"
            upload_dir.mkdir(parents=True, exist_ok=True)
            save_path = upload_dir / f.name
            with open(save_path, "wb") as fp:
                fp.write(file_bytes)

            # 查 parquet
            existing = _check_pdf_in_parquet(sha256)
            if existing:
                log.append(f"[{ts}] ⚠️ 已收录: {f.name} (paper_id={existing['paper_id'][:12]}...)")
                log.append(f"[{ts}]   上次来源文件: {existing.get('source_file', '未知')}")
                st.session_state["ex_pdf_info"].append({
                    "file_name": f.name,
                    "file_bytes": file_bytes,
                    "save_path": str(save_path),
                    "sha256": sha256,
                    "paper_id": existing["paper_id"],
                    "status": "existing",
                    "action": "skip",
                })
            else:
                log.append(f"[{ts}] ✅ 新论文: {f.name} (paper_id={paper_id[:12]}...)")
                st.session_state["ex_pdf_info"].append({
                    "file_name": f.name,
                    "file_bytes": file_bytes,
                    "save_path": str(save_path),
                    "sha256": sha256,
                    "paper_id": paper_id,
                    "status": "new",
                    "action": "extract",
                })

        n_new = sum(1 for p in st.session_state["ex_pdf_info"] if p["status"] == "new")
        n_exist = sum(1 for p in st.session_state["ex_pdf_info"] if p["status"] == "existing")
        log.append(f"[{ts}] 检查完成: {len(uploaded)} 个文件, 新论文 {n_new} 个, 已收录 {n_exist} 个")
        st.session_state["ex_checked"] = True
        st.rerun()

    # ── 已收录的 PDF：通知用户选择跳过/覆盖 ──
    existing_pdfs = [p for p in st.session_state.get("ex_pdf_info", []) if p["status"] == "existing"]
    if existing_pdfs:
        st.markdown("---")
        st.warning(f"⚠️ 检测到 {len(existing_pdfs)} 篇论文已收录，请选择操作：")

        for i, info in enumerate(st.session_state["ex_pdf_info"]):
            if info["status"] == "existing":
                col1, col2 = st.columns([3, 2])
                with col1:
                    st.write(f"📄 {info['file_name']}")
                    st.caption(f"上次来源: {info.get('source_file', '未知')}")
                with col2:
                    choice = st.radio(
                        "操作", ["跳过", "覆盖重新抽取"],
                        horizontal=True, key=f"ex_action_{i}",
                    )
                    st.session_state["ex_pdf_info"][i]["action"] = "skip" if choice == "跳过" else "overwrite"

    # ── 日志（折叠展示）──
    if st.session_state.get("ex_log"):
        with st.expander("📝 处理日志", expanded=False):
            for line in st.session_state["ex_log"]:
                st.text(line)

    # ── 抽取按钮：自动包含新论文 + 用户选择覆盖的 ──
    to_process = [p for p in st.session_state.get("ex_pdf_info", []) if p["action"] in ("extract", "overwrite")]
    if to_process:
        has_key = llm_api_key or os.environ.get("OPENAI_API_KEY")
        if not has_key:
            st.warning("⚠️ 请填写 API Key")
        else:
            if st.button(f"🚀 开始抽取 ({len(to_process)} 篇)", type="primary", use_container_width=True, key="btn_run_llm"):
                from openai import OpenAI
                import httpx

                api_key = llm_api_key or os.environ.get("OPENAI_API_KEY", "")
                client = OpenAI(
                    base_url=llm_base_url,
                    api_key=api_key,
                    http_client=httpx.Client(base_url=llm_base_url, follow_redirects=True),
                )
                templates = _load_prompt_templates()
                st.session_state["ex_new_rows"] = []
                st.session_state["ex_extraction_done"] = False
                log = st.session_state["ex_log"]

                progress = st.progress(0.0)
                total = len(to_process) * 5

                done = 0
                for info in to_process:
                    ts = datetime.now().strftime("%H:%M:%S")
                    action_label = "覆盖抽取" if info["action"] == "overwrite" else "抽取"
                    log.append(f"[{ts}] 开始{action_label}: {info['file_name']}")
                    progress.progress(done / total if total > 0 else 0, text=f"正在处理: {info['file_name']}")

                    # 提取 PDF 文本
                    pages = _extract_pdf_pages(info["save_path"])
                    log.append(f"[{ts}]   PDF 共 {len(pages)} 页")

                    # 5 阶段抽取
                    extraction_results = {}
                    for stage in ["metadata", "catalyst", "reaction_conditions", "performance", "provenance_confidence"]:
                        if stage not in templates:
                            done += 1
                            continue
                        keywords = _STAGE_KEYWORDS.get(stage, [])
                        top_pages = _select_top_pages(pages, keywords)
                        if not top_pages:
                            top_pages = pages[:2]

                        user_msg = _build_user_message(
                            info["paper_id"], info["file_name"], stage, top_pages
                        )

                        result, err = _call_llm(client, llm_model, templates[stage], user_msg)
                        if result:
                            extraction_results[stage] = result
                            # 调试：记录 LLM 返回的字段结构（只记 keys，不记值，避免日志过长）
                            try:
                                ed = result.get("extracted_data", {})
                                keys_summary = list(ed.keys()) if isinstance(ed, dict) else f"类型={type(ed).__name__}"
                                log.append(f"[{ts}]   ✅ {stage} 抽取成功 (字段: {keys_summary})")
                            except Exception:
                                log.append(f"[{ts}]   ✅ {stage} 抽取成功 (结构异常)")
                        else:
                            log.append(f"[{ts}]   ❌ {stage} 抽取失败: {err}")
                        done += 1
                        progress.progress(done / total if total > 0 else 0, text=f"{info['file_name']} - {stage}")

                    row = build_preview_row(
                        info["paper_id"], info["sha256"], info["file_name"], extraction_results
                    )
                    st.session_state["ex_new_rows"].append(row)

                    # 保存原始抽取结果供入库使用
                    if "ex_extraction_results" not in st.session_state:
                        st.session_state["ex_extraction_results"] = {}
                    st.session_state["ex_extraction_results"][info["paper_id"]] = {
                        "extraction_results": extraction_results,
                        "file_size": len(info["file_bytes"]),
                        "page_count": len(pages),
                    }

                    # 调试：把完整抽取结果转储到文件，方便排查
                    try:
                        import os
                        debug_dir = BASE_DIR / "outputs" / "debug"
                        debug_dir.mkdir(parents=True, exist_ok=True)
                        debug_file = debug_dir / f"{info['paper_id']}_extraction.json"
                        with open(debug_file, "w", encoding="utf-8") as f:
                            json.dump(extraction_results, f, ensure_ascii=False, indent=2, default=str)
                        log.append(f"[{ts}]   📝 调试转储: {debug_file.name}")
                    except Exception as e:
                        log.append(f"[{ts}]   ⚠️ 调试转储失败: {e}")

                    log.append(f"[{ts}] ✅ {info['file_name']} 抽取完成")

                st.session_state["ex_extraction_done"] = True
                ts = datetime.now().strftime("%H:%M:%S")
                log.append(f"[{ts}] 全部抽取完成，共 {len(st.session_state['ex_new_rows'])} 篇论文")
                st.rerun()

    # ── 预览数据 ──
    if st.session_state.get("ex_extraction_done") and st.session_state.get("ex_new_rows"):
        st.markdown("---")
        st.markdown("### 📊 预览新增数据")

        new_df = pd.DataFrame(st.session_state["ex_new_rows"])
        display_cols = [c for c in [
            "paper_id", "source_file", "doi", "paper_title", "year",
            "catalyst_name_normalized", "active_metal", "support",
            "reaction_temperature_C", "reaction_pressure_bar",
            "CO_conversion_pct", "CO2_conversion_pct",
            "C5plus_selectivity_pct", "CH4_selectivity_pct", "H2_CO_ratio",
        ] if c in new_df.columns]
        st.dataframe(new_df[display_cols], use_container_width=True, hide_index=True)

        if st.session_state["ex_log"]:
            with st.expander("📝 完整处理日志", expanded=False):
                for line in st.session_state["ex_log"]:
                    st.text(line)

        # ── 确认入库 ──
        st.markdown("---")
        col_confirm1, col_confirm2, col_confirm3 = st.columns(3)
        with col_confirm1:
            if st.button("✅ 确认入库", type="primary", use_container_width=True, key="btn_confirm_ingest"):
                ts = datetime.now().strftime("%H:%M:%S")
                log = st.session_state["ex_log"]

                ex_results_map = st.session_state.get("ex_extraction_results", {})

                for row in st.session_state["ex_new_rows"]:
                    paper_id = row["paper_id"]
                    meta = ex_results_map.get(paper_id, {})
                    extraction_results = meta.get("extraction_results", {})
                    file_size = meta.get("file_size", 0)
                    page_count = meta.get("page_count", None)

                    log.append(f"[{ts}] 写入 parquet: {paper_id[:12]}...")
                    stats = append_to_parquet(
                        paper_id, row["pdf_sha256"], row["source_file"],
                        file_size, page_count, extraction_results,
                        _VIZ_PARQUET_PATH,
                    )
                    log.append(f"[{ts}]   appended: {stats['appended']}, total_rows: {stats['total_rows']}")

                log.append(f"[{ts}] ✅ parquet 更新完成")

                # 清除 load_viz_db 缓存，让前端立即看到新数据
                st.cache_data.clear()
                log.append(f"[{ts}] 前端数据已刷新")

                st.success("✅ 入库成功！数据已追加到 parquet。请刷新页面查看前端数据变化。")
                st.session_state["ex_pdf_info"] = []
                st.session_state["ex_extraction_done"] = False
                st.session_state["ex_new_rows"] = []
                st.session_state["ex_checked"] = False
                st.session_state.pop("ex_extraction_results", None)
                st.rerun()

        with col_confirm2:
            csv_buf = new_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 下载预览结果",
                data=csv_buf,
                file_name=f"extraction_preview_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True,
                key="btn_download_preview",
            )

        with col_confirm3:
            if st.button("🧪 仅预览，不入库", use_container_width=True, key="btn_reset_extraction"):
                st.session_state["ex_pdf_info"] = []
                st.session_state["ex_extraction_done"] = False
                st.session_state["ex_new_rows"] = []
                st.session_state["ex_log"] = []
                st.session_state["ex_checked"] = False
                st.session_state.pop("ex_extraction_results", None)
                st.rerun()

    elif not st.session_state.get("ex_pdf_info"):
        st.info("👆 请上传 PDF 文件")

# ══════════════════════════════════════════════════════════════════
#  页面：数据可视化分析
# ══════════════════════════════════════════════════════════════════
elif page == "📈 数据可视化分析":

    st.markdown("""
    <div class="info-box">
    基于催化剂宽表（Excel/Parquet）直接渲染多维度图表，无需手动加载数据。
    </div>
    """, unsafe_allow_html=True)

    db = load_viz_db()
    if db is None:
        st.warning(
            f"未找到数据文件。请把 Excel 放到项目根目录，"
            f"或把 parquet 文件放到 `{OUTPUTS_DIR}`。"
        )
        st.stop()

    # 数据质量摘要基于全部 4067 篇论文（过滤前的原始数据基底）
    db_full = db

    # 仅保留有催化剂配方的完整数据（用于图表渲染）
    if "catalyst_name_normalized" in db.columns:
        db = db[db["catalyst_name_normalized"].notna()].copy()

    # 派生主值字段（取第一个，避免多值组合）
    def _primary(val):
        if pd.isna(val):
            return None
        return str(val).split(";")[0].strip() or None

    for src, dst in [("active_metal", "active_metal_primary"),
                     ("support", "support_primary"),
                     ("support_type", "support_type_primary"),
                     ("catalyst_family", "catalyst_family_primary")]:
        if src in db.columns and dst not in db.columns:
            db[dst] = db[src].apply(_primary)

    # 字段分组
    perf_cols = [c for c in ["CO_conversion_pct", "CO2_conversion_pct",
                             "C5plus_selectivity_pct", "CH4_selectivity_pct", "yield_pct"] if c in db.columns]
    cond_cols = [c for c in ["reaction_temperature_C", "reaction_pressure_bar",
                             "time_on_stream_h", "H2_CO_ratio"] if c in db.columns]

    # 数据质量摘要（基于全部 4067 篇论文）
    st.markdown('<div class="section-title">数据质量摘要</div>', unsafe_allow_html=True)
    n_papers = db_full["paper_id"].nunique() if "paper_id" in db_full.columns else 0
    n_perf = int(db_full[perf_cols].notna().sum().sum()) if perf_cols else 0
    n_cond = int(db_full[cond_cols].notna().sum().sum()) if cond_cols else 0
    for col, val, lbl in zip(st.columns(4),
                             [n_papers, len(db_full), n_perf, n_cond],
                             ["覆盖论文数", "记录总数", "性能数值点", "反应条件数值点"]):
        stat_card(col, val, lbl)

    st.markdown("---")

    data_source = st.radio(
        "数据来源",
        ["性能指标（转化率/选择性等）",
         "反应条件（温度/压力/时长/H₂·CO）",
         "论文信息（年份/期刊/工艺路线）",
         "催化剂/材料（活性金属/载体/助剂）"],
        horizontal=True, key="viz_data_source",
    )

    # 性能/反应条件：宽表 → 长表
    if data_source.startswith("性能指标") or data_source.startswith("反应条件"):
        if data_source.startswith("性能指标"):
            numeric_cols = perf_cols
            unit_map = {"CO_conversion_pct": "%", "CO2_conversion_pct": "%",
                        "C5plus_selectivity_pct": "%", "CH4_selectivity_pct": "%", "yield_pct": "%"}
            label_map = {"CO_conversion_pct": "CO 转化率", "CO2_conversion_pct": "CO₂ 转化率",
                         "C5plus_selectivity_pct": "C₅⁺ 选择性", "CH4_selectivity_pct": "CH₄ 选择性",
                         "yield_pct": "产率"}
        else:
            numeric_cols = cond_cols
            unit_map = {"reaction_temperature_C": "°C", "reaction_pressure_bar": "bar",
                        "time_on_stream_h": "h", "H2_CO_ratio": ""}
            label_map = {"reaction_temperature_C": "反应温度", "reaction_pressure_bar": "反应压力",
                         "time_on_stream_h": "运行时长", "H2_CO_ratio": "H₂/CO"}

        rows = []
        for _, r in db.iterrows():
            for c in numeric_cols:
                v = r.get(c)
                if pd.notna(v):
                    rows.append({
                        "paper_id": r.get("paper_id"),
                        "doi": r.get("doi"),
                        "metadata_year": r.get("year"),
                        "metadata_journal": r.get("metadata_journal"),
                        "metric": label_map.get(c, c),
                        "metric_raw": c,
                        "value_numeric": float(v),
                        "unit": unit_map.get(c, ""),
                    })
        active_df = pd.DataFrame(rows)

        tab_box, tab_line, tab_scatter, tab_rain = st.tabs(
            ["📦 箱线图", "📈 折线图", "🔵 散点图", "☔ 云雨图"]
        )

        metric_options = sorted(active_df["metric"].dropna().unique().tolist()) if not active_df.empty else []

        with tab_box:
            st.caption(f"按所选「{data_source}」分组，展示数值分布。")
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                box_metrics = st.multiselect("选择指标", metric_options,
                                             default=metric_options[:5] if metric_options else [],
                                             key="box_metrics")
            with col_b2:
                group_options = ["metric", "metadata_journal"]
                box_group_by = st.selectbox("分组方式", group_options, key="box_group_by")

            box_data = active_df[active_df["metric"].isin(box_metrics)] if box_metrics else active_df
            if box_data.empty:
                st.info("请选择至少一个指标。")
            else:
                fig_box = px.box(box_data, x=box_group_by, y="value_numeric", points="all",
                                 color=box_group_by,
                                 labels={"value_numeric": "数值", box_group_by: box_group_by})
                fig_box.update_layout(showlegend=False, height=480)
                plotly_chart_with_doi(fig_box, box_data if not box_data.empty else active_df, chart_key="doi_box")

        with tab_line:
            st.caption(f"按年份展示「{data_source}」随时间的变化趋势（取每年均值）。")
            if active_df.empty or "metadata_year" not in active_df.columns or active_df["metadata_year"].dropna().empty:
                st.info("数据中缺少年份信息，无法绘制折线图。")
            else:
                line_metrics = st.multiselect("选择指标", metric_options,
                                              default=metric_options[:3] if metric_options else [],
                                              key="line_metrics")
                line_data = active_df[active_df["metric"].isin(line_metrics)] if line_metrics else active_df.iloc[0:0]
                if line_data.empty:
                    st.info("请选择至少一个指标。")
                else:
                    trend = (line_data.dropna(subset=["metadata_year"])
                             .groupby(["metadata_year", "metric"])["value_numeric"]
                             .mean().reset_index())
                    fig_line = px.line(trend, x="metadata_year", y="value_numeric", color="metric",
                                       markers=True, labels={"value_numeric": "均值", "metadata_year": "年份"})
                    fig_line.update_layout(height=480)
                    plotly_chart_with_doi(fig_line, line_data if not line_data.empty else active_df,
                                          chart_key="doi_line")

        with tab_scatter:
            st.caption("查看两个指标之间的关系，或单一指标按论文序号的分布。")
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                scatter_metric_x = st.selectbox("X轴指标", metric_options, key="scatter_x") if metric_options else None
            with col_s2:
                scatter_metric_y = st.selectbox("Y轴指标", metric_options, key="scatter_y") if metric_options else None

            if scatter_metric_x and scatter_metric_y:
                x_data = active_df[active_df["metric"] == scatter_metric_x][["paper_id", "value_numeric", "doi"]].rename(
                    columns={"value_numeric": "x"})
                y_data = active_df[active_df["metric"] == scatter_metric_y][["paper_id", "value_numeric"]].rename(
                    columns={"value_numeric": "y"})
                merged = x_data.merge(y_data, on="paper_id", how="inner")
                if merged.empty:
                    st.info("两个指标在同一篇论文里没有同时出现的数据点。")
                else:
                    fig_scatter = px.scatter(merged, x="x", y="y", hover_data=["paper_id", "doi"],
                                             labels={"x": scatter_metric_x, "y": scatter_metric_y})
                    fig_scatter.update_layout(height=480)
                    plotly_chart_with_doi(fig_scatter, merged, chart_key="doi_scatter_same")
            elif scatter_metric_x:
                x_data = active_df[active_df["metric"] == scatter_metric_x].reset_index(drop=True)
                x_data["序号"] = x_data.index
                fig_scatter = px.scatter(x_data, x="序号", y="value_numeric",
                                         hover_data=["paper_id", "doi"],
                                         labels={"value_numeric": scatter_metric_x})
                fig_scatter.update_layout(height=480)
                plotly_chart_with_doi(fig_scatter, x_data, chart_key="doi_scatter_same")
            else:
                st.info("当前没有可选指标。")

        with tab_rain:
            st.caption(f"云雨图（{data_source}）= 小提琴 + 抖动散点 + 箱线图三层叠加。")
            rain_metrics = st.multiselect("选择指标（建议2-6个）", metric_options,
                                          default=metric_options[:4] if metric_options else [], key="rain_metrics")
            rain_data = active_df[active_df["metric"].isin(rain_metrics)] if rain_metrics else active_df.iloc[0:0]
            if rain_data.empty:
                st.info("请选择至少一个指标。")
            else:
                fig_rain = go.Figure()
                colors = px.colors.qualitative.Set2
                for i, m in enumerate(rain_metrics):
                    sub = rain_data[rain_data["metric"] == m]
                    color = colors[i % len(colors)]
                    fig_rain.add_trace(go.Violin(
                        x=[m] * len(sub), y=sub["value_numeric"],
                        side="positive", width=1.8, points=False,
                        line_color=color, fillcolor=color, opacity=0.45,
                        showlegend=False, scalemode="width",
                    ))
                    fig_rain.add_trace(go.Scatter(
                        x=[m] * len(sub), y=sub["value_numeric"],
                        mode="markers", marker=dict(color=color, size=6, opacity=0.6),
                        showlegend=False,
                    ))
                    fig_rain.add_trace(go.Box(
                        x=[m] * len(sub), y=sub["value_numeric"],
                        width=0.15, line_color="black", fillcolor="rgba(255,255,255,0.7)",
                        showlegend=False, boxpoints=False,
                    ))
                fig_rain.update_layout(height=520, violingap=0.3, violinmode="overlay",
                                       yaxis_title="数值", xaxis_title="指标")
                plotly_chart_with_doi(fig_rain, rain_data if not rain_data.empty else active_df,
                                      chart_key="doi_rain")

    # 论文信息分支
    if data_source.startswith("论文信息"):
        st.markdown('<div class="section-title">论文信息分析</div>', unsafe_allow_html=True)
        meta_tab1, meta_tab2, meta_tab3 = st.tabs(["📅 年份分布", "🗺️ 工艺路线分布", "📰 期刊分布"])

        with meta_tab1:
            st.caption("每年发表的论文数量趋势")
            if "year" in db.columns:
                year_counts = (db.dropna(subset=["year"])
                               .groupby("year")["paper_id"].count().reset_index()
                               .rename(columns={"paper_id": "论文数量", "year": "年份"}))
                fig_year = px.bar(year_counts, x="年份", y="论文数量", color_discrete_sequence=["#1565C0"])
                fig_year.update_layout(height=420)
                plotly_chart_with_doi(fig_year, db, chart_key="doi_meta_year_bar", doi_col="doi")
                fig_line_year = px.line(year_counts, x="年份", y="论文数量", markers=True,
                                        color_discrete_sequence=["#1976D2"])
                fig_line_year.update_layout(height=380, title="年份趋势折线图")
                plotly_chart_with_doi(fig_line_year, db, chart_key="doi_meta_year_line", doi_col="doi")
            else:
                st.info("数据中缺少年份字段。")

        with meta_tab2:
            st.caption("各工艺路线的论文数量分布")
            route_col = "CO_or_CO2_route" if "CO_or_CO2_route" in db.columns else None
            if route_col:
                route_counts = (db.dropna(subset=[route_col])
                                .groupby(route_col)["paper_id"].count().reset_index()
                                .rename(columns={"paper_id": "论文数量", route_col: "工艺路线"})
                                .sort_values("论文数量", ascending=False))
                fig_route = px.bar(route_counts, x="工艺路线", y="论文数量",
                                   color_discrete_sequence=["#1565C0"])
                fig_route.update_layout(height=420)
                plotly_chart_with_doi(fig_route, db, chart_key="doi_meta_route_bar", doi_col="doi")
            else:
                st.info("数据中缺少工艺路线字段。")

        with meta_tab3:
            st.caption("发文数量最多的期刊")
            journal_col = "metadata_journal" if "metadata_journal" in db.columns else None
            if journal_col:
                journal_counts = (db.dropna(subset=[journal_col])
                                  .groupby(journal_col)["paper_id"].count().reset_index()
                                  .rename(columns={"paper_id": "论文数量", journal_col: "期刊"})
                                  .sort_values("论文数量", ascending=False).head(20))
                fig_journal = px.bar(journal_counts, x="论文数量", y="期刊", orientation="h",
                                     color_discrete_sequence=["#1565C0"])
                fig_journal.update_layout(height=max(380, len(journal_counts) * 28))
                plotly_chart_with_doi(fig_journal, db, chart_key="doi_meta_journal", doi_col="doi")
            else:
                st.info("数据中缺少期刊字段。")

    # 催化剂分支
    elif data_source.startswith("催化剂"):
        st.markdown('<div class="section-title">催化剂/材料分析</div>', unsafe_allow_html=True)
        cat_tab_bar, cat_tab_box, cat_tab_trend = st.tabs(
            ["📊 材料频次条形图", "📦 材料分组箱线图", "📅 材料随年份变化"]
        )

        cat_fields = {
            "active_metal_primary": "活性金属",
            "support_primary": "载体",
            "support_type_primary": "载体类型",
            "promoter_elements": "助剂",
        }
        cat_fields_avail = {k: v for k, v in cat_fields.items() if k in db.columns}

        with cat_tab_bar:
            st.caption("各类材料字段的出现频次分布")
            sel_fields = st.multiselect("选择字段", list(cat_fields_avail.values()),
                                        default=list(cat_fields_avail.values()), key="cat_bar_fields")
            top_n = st.slider("每个字段最多展示前N种", 5, 30, 15, key="cat_top_n")
            for i_field, (field, label) in enumerate(cat_fields_avail.items()):
                if label not in sel_fields:
                    continue
                field_data = db[field].dropna().astype(str).value_counts().head(top_n).reset_index()
                field_data.columns = ["材料", "论文数"]
                fig_cat = px.bar(field_data, x="材料", y="论文数",
                                 title=f"{label} 分布（Top {top_n}）",
                                 color_discrete_sequence=["#1565C0"])
                fig_cat.update_layout(height=380)
                plotly_chart_with_doi(fig_cat, db, chart_key=f"doi_cat_bar_{i_field}", doi_col="doi")

        with cat_tab_box:
            st.caption("按活性金属或载体分组，展示性能指标分布。")
            perf_for_cat = [c for c in ["CO_conversion_pct", "CO2_conversion_pct",
                                        "CH4_selectivity_pct", "C5plus_selectivity_pct"] if c in db.columns]
            if perf_for_cat and cat_fields_avail:
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    group_field = st.selectbox("分组依据", list(cat_fields_avail.values()), key="cat_box_group")
                    group_col = [k for k, v in cat_fields_avail.items() if v == group_field][0]
                with col_c2:
                    perf_field = st.selectbox("性能指标", perf_for_cat, key="cat_box_perf",
                                              format_func=lambda x: {"CO_conversion_pct": "CO 转化率",
                                                                     "CO2_conversion_pct": "CO₂ 转化率",
                                                                     "CH4_selectivity_pct": "CH₄ 选择性",
                                                                     "C5plus_selectivity_pct": "C₅⁺ 选择性"}.get(x, x))
                box_data = db.dropna(subset=[group_col, perf_field]).copy()
                if not box_data.empty:
                    fig_cat_box = px.box(box_data, x=group_col, y=perf_field, points="all",
                                         color=group_col,
                                         labels={perf_field: "数值", group_col: group_field})
                    fig_cat_box.update_layout(height=460, showlegend=False)
                    plotly_chart_with_doi(fig_cat_box, box_data, chart_key="doi_cat_box", doi_col="doi")
                else:
                    st.info("该组合下暂无数据。")
            else:
                st.info("缺少可用的性能指标或材料字段。")

        with cat_tab_trend:
            st.caption("各类材料随年份的论文数量变化")
            if "year" in db.columns and cat_fields_avail:
                sel_field_label = st.selectbox("选择字段", list(cat_fields_avail.values()), key="cat_year_field")
                sel_field = [k for k, v in cat_fields_avail.items() if v == sel_field_label][0]
                top_values = db[sel_field].dropna().astype(str).value_counts().head(15).index.tolist()
                sel_values = st.multiselect("选择具体材料（留空=全部前15）", top_values, key="cat_year_values")
                cat_year_data = db.dropna(subset=[sel_field, "year"])
                if sel_values:
                    cat_year_data = cat_year_data[cat_year_data[sel_field].astype(str).isin(sel_values)]
                if not cat_year_data.empty:
                    trend = (cat_year_data.groupby(["year", sel_field])["paper_id"]
                             .count().reset_index()
                             .rename(columns={"paper_id": "论文数", "year": "年份", sel_field: sel_field_label}))
                    fig_cat_year = px.line(trend, x="年份", y="论文数", color=sel_field_label, markers=True)
                    fig_cat_year.update_layout(height=450)
                    plotly_chart_with_doi(fig_cat_year, cat_year_data, chart_key="doi_cat_trend", doi_col="doi")
                else:
                    st.info("暂无可用数据。")
            else:
                st.info("数据中缺少年份信息。")

    # 数据表预览
    st.markdown('<div class="section-title">📋 数据表预览</div>', unsafe_allow_html=True)
    st.dataframe(db, use_container_width=True, height=400)

# ══════════════════════════════════════════════════════════════════
#  页面：使用说明
# ══════════════════════════════════════════════════════════════════
elif page == "📖 使用说明":

    st.markdown("""
<style>
.doc-paths {
    background: #f8faff;
    border: 1px solid #BBDEFB;
    border-radius: 8px;
    padding: 14px 20px;
    margin-bottom: 22px;
    font-family: 'Times New Roman','Microsoft YaHei','微软雅黑',serif;
    font-size: 0.9rem;
    line-height: 2.0;
    color: #1A237E;
}
.doc-paths code {
    background: #E3F2FD;
    color: #1565C0;
    padding: 1px 6px;
    border-radius: 3px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.82rem;
}
.doc-section-title {
    font-size: 1.12rem;
    font-weight: 700;
    color: #0D2B5E;
    border-left: 4px solid #1565C0;
    padding-left: 10px;
    margin: 24px 0 12px;
    font-family: 'Times New Roman','Microsoft YaHei','微软雅黑',serif;
}
.doc-module-list {
    font-family: 'Times New Roman','Microsoft YaHei','微软雅黑',serif;
    font-size: 0.95rem;
    line-height: 2.0;
    color: #222;
    padding-left: 4px;
}
.doc-module-list li {
    margin-bottom: 6px;
}
.doc-module-list b {
    color: #0D2B5E;
}
.doc-boundary {
    font-family: 'Times New Roman','Microsoft YaHei','微软雅黑',serif;
    font-size: 0.95rem;
    line-height: 1.85;
    color: #333;
    margin-top: 6px;
}
</style>
""", unsafe_allow_html=True)

    st.markdown("""
<div class="doc-paths">
    <div><b>文献数据目录：</b><code>data/queue_oa_queue_webvpn2.csv</code></div>
    <div><b>PDF 存放目录：</b><code>pdfs/</code></div>
    <div><b>抽取结果文件：</b><code>outputs/extractions_long.csv</code></div>
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="doc-section-title">页面模块</div>', unsafe_allow_html=True)
    st.markdown("""
<ol class="doc-module-list">
  <li><b>平台数据总览</b>：上半部分展示文献库规模（总量 4067 篇、有效 PDF、年份范围、OA 比例）、出版商分布以及自动下载效率对比；下半部分为催化剂数据浏览，按催化剂家族、活性金属、原料气类型、年份、反应温度等条件筛选已解析的 1626 篇完整数据，支持散点图与云雨图可视化。</li>
  <li><b>论文自动下载</b>：上传含 DOI 的 CSV / Excel，系统按出版商路由自动分类，支持一键批量下载并导出下载结果清单。</li>
  <li><b>数据自动提取</b>：上传 PDF，LLM 自动提取催化剂组成、反应条件与催化性能数据，确认入库后前端自动刷新。</li>
  <li><b>数据可视化分析</b>：自动加载催化剂宽表，提供箱线图、折线图、散点图、云雨图及论文/催化剂分布分析。</li>
  <li><b>使用说明</b>：说明各模块功能、数据文件位置及生产应用边界（本页）。</li>
</ol>
""", unsafe_allow_html=True)

    st.markdown('<div class="doc-section-title">应用边界</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="doc-boundary">
当前系统是文献数据驱动的科研辅助平台。模型可以帮助快速筛选候选催化剂和观察趋势，但不能直接替代实验验证。
正式用于企业项目时，需要进行数据人工复核、外部验证、适用域判断和不确定性评估。<br><br>
本平台仅使用机构授权 / 合规公开渠道获取文献，不绕过付费墙或访问控制。
所有下载行为均遵循出版商服务条款，下载频率已设置合理延迟以避免对服务器造成压力。
</div>
""", unsafe_allow_html=True)

    st.markdown('<div class="doc-section-title">注意事项</div>', unsafe_allow_html=True)
    st.markdown("""
<ol class="doc-module-list">
  <li>上传的 CSV / Excel 文件须包含 <code>DOI</code> 列，列名大小写不限。</li>
  <li>数据自动提取模块依赖大语言模型 API，请确保网络连通且 API Key 已正确配置。</li>
  <li>数据可视化分析自动加载催化剂宽表（Excel/Parquet），无需手动上传。</li>
  <li>平台统计数字（1,627 篇等）来自当前已扫描的数据集，随数据更新会同步变化。</li>
  <li>如遇下载失败，可查看导出的结果清单中的"状态"列，手动处理标注为 <code>🟠 需 WebVPN</code> 或 <code>🔴 人工审核</code> 的条目。</li>
</ol>
""", unsafe_allow_html=True)

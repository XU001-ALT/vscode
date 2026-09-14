"""
SAF 公共模块：出版商路由表、DOI 分类、PDF 校验等共享逻辑。
被 app27.py / downloader.py / webvpn_downloader3.py 共同引用，消除三份重复。
"""

from __future__ import annotations

import hashlib
import re


# ──────────────────────────────────────────────────────────────────────────────
#  出版商路由表（唯一真源）
# ──────────────────────────────────────────────────────────────────────────────

PUBLISHER_ROUTES: dict[str, tuple[str, str, str | None]] = {
    "10.1002": ("Wiley",            "webvpn",   "https://onlinelibrary.wiley.com/doi/pdfdirect/{doi}"),
    "10.1021": ("ACS",              "verified", "https://pubs.acs.org/doi/pdf/{doi}"),
    "10.1007": ("Springer Nature",  "verified", "https://link.springer.com/content/pdf/{doi}.pdf"),
    "10.1016": ("Elsevier",         "webvpn",   None),
    "10.1039": ("RSC",              "webvpn",   None),
    "10.3390": ("MDPI",             "direct",   "https://www.mdpi.com/{doi}/pdf"),
    "10.1080": ("Taylor & Francis", "probe",    None),
    "10.1038": ("Nature",           "direct",   "https://www.nature.com/articles/{suffix}.pdf"),
    "10.1126": ("Science",          "webvpn",   None),
    "10.1103": ("APS",              "direct",   "https://journals.aps.org/doi/{doi}"),
    "10.1149": ("IOP/ECS",          "webvpn",   None),
    "10.1515": ("De Gruyter",       "probe",    None),
    "10.1590": ("SciELO",           "direct",   None),
}

ROUTE_LABEL = {
    "direct": "🟢 直接下载",
    "verified": "🔵 已验证路由",
    "webvpn": "🟠 需 WebVPN",
    "probe": "🟡 出版商探针",
    "review": "🔴 人工审核",
    "invalid": "⚫ 无效 DOI",
}

# 只自动下载这两类路由
AUTO_ROUTES = {"direct", "verified"}

# 出版商限速（秒），避免触发反爬
PUBLISHER_DELAY: dict[str, float] = {
    "ACS":             3.0,
    "Springer Nature": 2.0,
    "MDPI":            1.5,
    "Nature":          2.0,
    "APS":             2.0,
}
DEFAULT_DELAY = 2.0

# 请求头（模拟浏览器，避免被拒绝）
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/pdf,application/octet-stream,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}


# ──────────────────────────────────────────────────────────────────────────────
#  核心函数
# ──────────────────────────────────────────────────────────────────────────────

def classify_doi(doi: str, access_type: str = "") -> dict:
    """根据 DOI 前缀分配路由和下载 URL。"""
    doi = doi.strip()
    if not doi or doi.lower() in ("nan", "none", ""):
        return {"route": "invalid", "publisher": "未知", "url": ""}

    prefix = ".".join(doi.split("/")[0].split(".")[:2]) if "/" in doi else ""
    if prefix not in PUBLISHER_ROUTES:
        return {"route": "review", "publisher": "低频/未知", "url": ""}

    publisher, route, tpl = PUBLISHER_ROUTES[prefix]

    # OA 文献降级为 direct 尝试
    if str(access_type).strip().upper() in ("OA", "OA_DOWNLOADABLE", "开放获取") and route == "webvpn":
        route = "direct"

    url = ""
    if tpl:
        suffix = doi.split("/")[-1] if "/" in doi else doi
        url = tpl.replace("{doi}", doi).replace("{suffix}", suffix)

    return {"route": route, "publisher": publisher, "url": url}


def safe_filename(doi: str) -> str:
    """把 DOI 转换为安全的文件名（sanitized_doi.pdf）。"""
    return re.sub(r'[\\/:*?"<>|]', "_", doi) + ".pdf"


def validate_pdf_bytes(data: bytes, min_kb: int = 20) -> dict:
    """校验下载内容是否为合法 PDF，返回详细诊断字典。"""
    ok_header = data[:5] == b"%PDF-"
    ok_size = len(data) > min_kb * 1024
    sha256 = hashlib.sha256(data).hexdigest()
    return {
        "valid": ok_header and ok_size,
        "header": ok_header,
        "size_kb": round(len(data) / 1024, 1),
        "sha256": sha256,
        "reason": (
            "" if (ok_header and ok_size)
            else ("非PDF内容" if not ok_header else f"文件过小({len(data) // 1024}KB<{min_kb}KB)")
        ),
    }

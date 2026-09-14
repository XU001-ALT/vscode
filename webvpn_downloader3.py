#!/usr/bin/env python
"""
webvpn_downloader.py
通过已登录的WebVPN Chrome会话，自动批量下载论文PDF。

v8 修复（借鉴 PowerShell 脚本思路）：
  - 深度检查页面中的 embed 和 iframe 元素，提取真实的 PDF 链接
  - 优先处理 Chrome PDF 查看器
  - 针对 Wiley 的 PDF format 按钮专项优化
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import time
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from saf_common import validate_pdf_bytes

WEBVPN_HOME = "https://webvpn.xjtu.edu.cn"


def normalize_doi(doi: str) -> str:
    doi = str(doi or "").strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi


def safe_filename(doi: str, title: str = "") -> str:
    base = title[:60] if title else doi
    base = re.sub(r'[\\/:*?"<>|]', "_", base)
    base = re.sub(r"\s+", "_", base)
    h = hashlib.sha256(doi.encode()).hexdigest()[:10]
    return f"{base}_{h}.pdf"


def validate_pdf(data: bytes, min_kb: int = 20) -> bool:
    return validate_pdf_bytes(data, min_kb)["valid"]


def load_queue(csv_path: Path, limit: int = 0) -> list[dict]:
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doi = normalize_doi(row.get("doi", ""))
            if not doi:
                continue
            rows.append({
                "doi": doi,
                "publisher": row.get("publisher_group", row.get("出版商", "")),
                "title": row.get("title", ""),
            })
    if limit and limit > 0:
        rows = rows[:limit]
    return rows


def write_log(log_path: Path, row: dict) -> None:
    is_new = not log_path.exists()
    with log_path.open("a", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["timestamp", "doi", "publisher", "status", "file_name", "size_kb", "note", "real_url"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def fetch_via_context(page_or_frame, url: str, timeout_ms: int) -> tuple[bytes | None, str]:
    """用浏览器的上下文（带WebVPN认证）请求URL，返回 (body, content-type)。"""
    try:
        main_page = page_or_frame.page if hasattr(page_or_frame, "page") else page_or_frame
        resp = main_page.context.request.get(url, timeout=timeout_ms)
        ctype = resp.headers.get("content-type", "").lower()
        body = resp.body()
        return body, ctype
    except Exception:
        return None, ""


def find_pdf_from_embed(target, timeout_ms: int = 30000) -> bytes | None:
    """
    在页面中查找 <embed> 或 <iframe> 元素，提取其 src 属性并尝试获取 PDF。
    这是处理 Wiley 等出版商把 PDF 嵌入页面的关键。
    """
    main_page = target.page if hasattr(target, "page") else target

    # 查找 embed 元素
    for selector in ["embed[type='application/pdf']", "embed[src*='.pdf']", "iframe[src*='.pdf']"]:
        try:
            elements = target.locator(selector).all()
            for el in elements:
                src = el.get_attribute("src")
                if not src:
                    continue
                # 拼接完整 URL
                if src.startswith("http"):
                    full_url = src
                else:
                    full_url = main_page.urljoin(src)
                body, ctype = fetch_via_context(target, full_url, timeout_ms)
                if body and "pdf" in ctype and validate_pdf(body):
                    return body
        except Exception:
            continue

    return None


def find_pdf_download(target, timeout_ms: int = 30000, _depth: int = 0) -> bytes | None:
    """
    在 target（Page 或 Frame）中寻找 PDF。
    策略：
      1. 检查当前 URL 的 Content-Type
      2. 检查页面中的 embed/iframe
      3. 点击 PDF 按钮
    递归深度不超过 3 层，防止无限弹页面。
    """
    if _depth > 3:
        return None
    main_page = target.page if hasattr(target, "page") else target

    # ---- 策略0：检查当前 URL 是否为 PDF ----
    if hasattr(target, "url") and target.url:
        body, ctype = fetch_via_context(target, target.url, timeout_ms)
        if body and "pdf" in ctype and validate_pdf(body):
            return body

    # ---- 策略1：检查 embed 和 iframe（Wiley 常见） ----
    pdf_bytes = find_pdf_from_embed(target, timeout_ms)
    if pdf_bytes:
        return pdf_bytes

    # ---- 策略2：尝试关闭弹窗 ----
    dismiss_patterns = [
        "text=/全部接受/i", "text=/Accept all/i", "text=/Accept All/i",
        "button:has-text('全部接受')", "[aria-label*='close' i]",
        "text=/^×$/", "text=/^✕$/",
    ]
    for pattern in dismiss_patterns:
        try:
            btn = target.locator(pattern).first
            if btn.count() > 0:
                btn.click(timeout=2000)
                time.sleep(0.5)
        except Exception:
            continue

    # ---- 策略3：直接提取页面上的 PDF 链接 ----
    try:
        links = target.locator("a[href]").all()
        for link in links:
            href = link.get_attribute("href")
            if not href:
                continue
            if re.search(r"\.pdf($|\?)|/pdf/", href, re.I):
                full_url = href if href.startswith("http") else main_page.urljoin(href)
                body, ctype = fetch_via_context(target, full_url, timeout_ms)
                if body and "pdf" in ctype and validate_pdf(body):
                    return body
    except Exception:
        pass

    # ---- 策略4：点击 PDF 按钮 ----
    pdf_link_patterns = [
        "text=/Download this article/i",
        "text=/Download PDF/i",
        "text=/View PDF/i",
        "text=/PDF format/i",
        "text=/^PDF$/i",
        "a:has-text('Download this article')",
        "a:has-text('PDF format')",
        "a:has-text('PDF')",
        "span:has-text('PDF format')",
        "span:has-text('PDF')",
        "div:has-text('PDF')",
        "[data-track-action*='pdf' i]",
        "a[href*='.pdf' i]",
        "a[href*='/pdf' i]",
        "button:has-text('PDF')",
        "[aria-label*='PDF' i]",
        "[aria-label*='Download' i]",
    ]

    for pattern in pdf_link_patterns:
        try:
            locator = target.locator(pattern).first
            if locator.count() == 0:
                continue

            locator.scroll_into_view_if_needed(timeout=2000)
            time.sleep(0.5)

            # 尝试点击，监听下载
            try:
                with main_page.expect_download(timeout=8000) as dl_info:
                    locator.click(timeout=5000, force=True)
                download = dl_info.value
                if download.path():
                    return Path(download.path()).read_bytes()
            except PWTimeout:
                # 下载超时，可能触发了新页面
                try:
                    with main_page.context.expect_page(timeout=10000) as page_info:
                        locator.click(timeout=5000, force=True)
                    new_page = page_info.value
                    new_page.wait_for_load_state("networkidle", timeout=timeout_ms)
                    # 新页面中递归查找
                    body, ctype = fetch_via_context(new_page, new_page.url, timeout_ms)
                    if body and "pdf" in ctype and validate_pdf(body):
                        return body
                    # 检查新页面中的 embed
                    inner_pdf = find_pdf_from_embed(new_page, timeout_ms)
                    if inner_pdf:
                        return inner_pdf
                    # 递归查找
                    inner_pdf2 = find_pdf_download(new_page, timeout_ms, _depth + 1)
                    if inner_pdf2:
                        return inner_pdf2
                except Exception:
                    continue
            except Exception:
                continue
        except Exception:
            continue

    return None


def download_one(context, page, doi: str, out_dir: Path, min_kb: int = 20,
                  timeout_ms: int = 30000, debug_dir: Path | None = None) -> dict:
    """处理单篇论文：在WebVPN搜索框输入URL，然后找PDF。"""
    target_url = f"https://doi.org/{doi}"
    new_page = None

    try:
        page.goto(WEBVPN_HOME, timeout=timeout_ms, wait_until="domcontentloaded")
        time.sleep(1)

        input_box = None
        for sel in [
            "input[placeholder*='网址']",
            "input[placeholder*='输入']",
            "input[type='text']",
            "input[type='url']",
        ]:
            try:
                box = page.locator(sel).first
                if box.count() > 0:
                    input_box = box
                    break
            except Exception:
                continue

        if input_box is None:
            return {"status": "error", "note": "未找到WebVPN搜索输入框", "real_url": page.url}

        input_box.fill(target_url)
        time.sleep(0.3)

        target = None
        real_url = ""
        try:
            with context.expect_page(timeout=10000) as new_page_info:
                input_box.press("Enter")
            new_page = new_page_info.value
            new_page.wait_for_load_state("networkidle", timeout=timeout_ms)
            time.sleep(3)
            target = new_page
            real_url = new_page.url
        except PWTimeout:
            page.wait_for_load_state("networkidle", timeout=timeout_ms)
            for f in page.frames:
                if f.url and "webvpn" not in f.url and f.url != "about:blank":
                    target = f
                    real_url = f.url
                    break
            if target is None:
                target = page
                real_url = page.url

        fname = safe_filename(doi)
        out_path = out_dir / fname

        pdf_bytes = find_pdf_download(target, timeout_ms)

        if pdf_bytes is None:
            shot_note = ""
            if debug_dir:
                try:
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    shot_path = debug_dir / f"debug_{doi.replace('/', '_')}.png"
                    target.screenshot(path=str(shot_path))
                    shot_note = f" 截图:{shot_path.name}"
                except Exception:
                    pass
            return {
                "status": "no_pdf_found",
                "note": f"未找到PDF下载入口{shot_note}",
                "real_url": real_url,
            }

        if not validate_pdf(pdf_bytes, min_kb):
            return {
                "status": "invalid_pdf",
                "note": f"PDF内容无效，大小{len(pdf_bytes)//1024}KB",
                "real_url": real_url,
            }

        out_path.write_bytes(pdf_bytes)
        return {
            "status": "success",
            "file_name": fname,
            "size_kb": round(len(pdf_bytes) / 1024, 1),
            "note": "成功获取PDF",
            "real_url": real_url,
        }

    except PWTimeout:
        return {"status": "timeout", "note": f"超时(>{timeout_ms}ms)", "real_url": page.url}
    except Exception as e:
        return {"status": "error", "note": str(e)[:150], "real_url": page.url}
    finally:
        if new_page is not None:
            try:
                new_page.close()
            except Exception:
                pass


def run(args: argparse.Namespace) -> None:
    queue_path = Path(args.queue)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "webvpn_playwright_log.csv"
    debug_dir = out_dir / "debug_screenshots" if args.debug else None

    queue = load_queue(queue_path, args.limit)
    limit_desc = "全部" if args.limit == 0 else f"{args.limit} 篇"
    print(f"\n{'='*60}")
    print(f"  WebVPN 自动下载（Playwright版 v8 - embed/iframe深度检查）")
    print(f"  队列：{len(queue)} 篇 (本次处理: {limit_desc})")
    print(f"  输出：{out_dir}")
    if debug_dir:
        print(f"  调试截图：{debug_dir}")
    print(f"{'='*60}\n")

    if not queue:
        print("队列为空，退出。")
        return

    with sync_playwright() as p:
        try:
            browser = p.chromium.connect_over_cdp("http://localhost:9222")
        except Exception as e:
            print(f"[错误] 无法连接到Chrome调试端口：{e}")
            print("请先用 启动Chrome调试模式 的脚本重新打开Chrome。")
            return

        context = browser.contexts[0] if browser.contexts else browser.new_context()
        page = context.pages[0] if context.pages else context.new_page()

        stats = {"success": 0, "no_pdf_found": 0, "invalid_pdf": 0, "timeout": 0, "error": 0}

        for i, item in enumerate(queue, 1):
            doi = item["doi"]
            publisher = item["publisher"]
            print(f"[{i:>4}/{len(queue)}] {publisher:<20} {doi}")

            result = download_one(context, page, doi, out_dir, args.min_kb,
                                  args.timeout * 1000, debug_dir)
            result["timestamp"] = datetime.now().isoformat()
            result["doi"] = doi
            result["publisher"] = publisher

            status = result["status"]
            stats[status] = stats.get(status, 0) + 1

            icon = {"success": "[成功]", "no_pdf_found": "[未找到PDF]", "invalid_pdf": "[无效PDF]",
                    "timeout": "[超时]", "error": "[错误]"}.get(status, "[?]")
            extra = f" {result.get('size_kb','')}KB" if result.get("size_kb") else ""
            note = result.get("note", "")[:90]
            real_url = result.get("real_url", "")[:90]
            print(f"        {icon} {status}{extra}  {note}")
            print(f"           真实页面: {real_url}")

            write_log(log_path, result)

            if i < len(queue):
                time.sleep(args.delay)

        print(f"\n{'='*60}")
        print(f"  完成！成功 {stats.get('success',0)} / {len(queue)}")
        for k, v in stats.items():
            if v:
                print(f"  {k}: {v}")
        print(f"  日志：{log_path}")
        print(f"{'='*60}\n")

        browser.close()


def main():
    parser = argparse.ArgumentParser(description="通过已登录WebVPN的Chrome自动批量下载PDF")
    parser.add_argument("--queue", required=True, help="队列CSV路径（含doi列）")
    parser.add_argument("--out-dir", required=True, help="PDF保存目录")
    parser.add_argument("--limit", type=int, default=5, help="本次处理篇数，0=处理全部")
    parser.add_argument("--min-kb", type=int, default=20, help="PDF最小有效体积KB")
    parser.add_argument("--timeout", type=int, default=30, help="单篇超时秒数")
    parser.add_argument("--delay", type=float, default=3.0, help="篇间延迟秒数")
    parser.add_argument("--debug", action="store_true", help="失败时自动截图")
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
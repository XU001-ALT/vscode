#!/usr/bin/env python
"""
SAF 文献自动下载脚本
针对 direct / verified 路由的文献，直接 HTTP 下载 PDF。
用法：
    python downloader.py --input queue_direct.csv --out-dir ./downloads
"""

from __future__ import annotations

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from saf_common import (
    PUBLISHER_ROUTES, AUTO_ROUTES, HEADERS, PUBLISHER_DELAY, DEFAULT_DELAY,
    classify_doi, safe_filename, validate_pdf_bytes,
)


def validate_pdf(data: bytes, min_kb: int = 20) -> dict:
    """向下兼容包装：saf_common.validate_pdf_bytes 的别名。"""
    return validate_pdf_bytes(data, min_kb)


def download_one(
    doi: str,
    url: str,
    publisher: str,
    out_dir: Path,
    min_kb: int = 20,
    timeout: int = 60,
) -> dict:
    """下载单篇文献，返回结果字典。"""
    filename  = safe_filename(doi, publisher)
    out_path  = out_dir / publisher.replace("/", "_") / filename
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 已存在且合法则跳过
    if out_path.exists() and out_path.stat().st_size > min_kb * 1024:
        existing = out_path.read_bytes()
        v = validate_pdf(existing, min_kb)
        if v["valid"]:
            return {
                "doi": doi, "status": "skipped_exists",
                "file": str(out_path), "sha256": v["sha256"],
                "size_kb": v["size_kb"], "reason": "文件已存在且有效",
            }

    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
    except requests.exceptions.Timeout:
        return {"doi": doi, "status": "timeout",  "file": "", "reason": f"请求超时({timeout}s)"}
    except requests.exceptions.ConnectionError as e:
        return {"doi": doi, "status": "conn_error","file": "", "reason": str(e)[:120]}
    except Exception as e:
        return {"doi": doi, "status": "error",     "file": "", "reason": str(e)[:120]}

    # HTTP 错误
    if resp.status_code in (401, 403):
        return {"doi": doi, "status": "no_access",
                "file": "", "reason": f"HTTP {resp.status_code} - 需要机构认证"}
    if resp.status_code in (404, 410):
        return {"doi": doi, "status": "not_found",
                "file": "", "reason": f"HTTP {resp.status_code} - 资源不存在"}
    if resp.status_code != 200:
        return {"doi": doi, "status": "http_error",
                "file": "", "reason": f"HTTP {resp.status_code}"}

    # 内容校验
    data = resp.content
    v = validate_pdf(data, min_kb)
    if not v["valid"]:
        return {"doi": doi, "status": "invalid_pdf",
                "file": "", "reason": v["reason"], "size_kb": v["size_kb"]}

    # 写入文件
    out_path.write_bytes(data)
    return {
        "doi":     doi,
        "status":  "success",
        "file":    str(out_path),
        "sha256":  v["sha256"],
        "size_kb": v["size_kb"],
        "reason":  "",
    }


def load_queue(csv_path: Path) -> list[dict]:
    """读取队列 CSV，兼容 app.py 导出格式和原始 xlsx 格式。"""
    rows = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # 统一列名
            doi = (row.get("doi") or row.get("DOI") or "").strip()
            access = (
                row.get("access_type") or
                row.get("access_classification") or
                row.get("prior_access_classification") or ""
            ).strip()
            route = (row.get("路由") or row.get("route") or "").strip()
            url   = (row.get("下载URL") or row.get("url") or "").strip()
            pub   = (row.get("出版商") or row.get("publisher") or "").strip()

            if not doi:
                continue

            # 如果没有路由信息，重新分类
            if not route:
                classified = classify_doi(doi, access)
                route = classified["route"]
                url   = classified["url"]
                pub   = classified["publisher"]

            rows.append({
                "doi": doi, "route": route,
                "url": url, "publisher": pub,
                "access_type": access,
            })
    return rows


# ──────────────────────────────────────────────────────────────────────────────
#  主流程
# ──────────────────────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    input_path = Path(args.input).resolve()
    out_dir    = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    log_path = out_dir / f"download_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    log_fields = ["doi", "publisher", "route", "url", "status", "file", "size_kb", "sha256", "reason", "timestamp"]

    print(f"\n{'='*60}")
    print(f"  SAF 文献自动下载脚本")
    print(f"  输入队列：{input_path.name}")
    print(f"  输出目录：{out_dir}")
    print(f"  最小 PDF：{args.min_kb} KB  超时：{args.timeout}s")
    print(f"{'='*60}\n")

    # 读取队列
    all_rows = load_queue(input_path)

    # 过滤：只下载 direct / verified 路由
    queue = [r for r in all_rows if r["route"] in AUTO_ROUTES and r["url"]]
    skipped_routes = [r for r in all_rows if r["route"] not in AUTO_ROUTES]

    print(f"队列总计：{len(all_rows)} 条")
    print(f"  ✅ 可自动下载（direct/verified）：{len(queue)} 条")
    print(f"  ⏭  跳过（webvpn/probe/review/invalid）：{len(skipped_routes)} 条\n")

    # 统计
    stats = {"success": 0, "skipped_exists": 0, "no_access": 0,
             "invalid_pdf": 0, "error": 0, "total": len(queue)}
    sha_seen: dict[str, str] = {}  # sha256 -> doi，去重

    # 小批量测试模式
    if args.test:
        queue = queue[:args.test]
        print(f"⚠️  测试模式：只处理前 {args.test} 条\n")

    with log_path.open("w", newline="", encoding="utf-8-sig") as log_f:
        writer = csv.DictWriter(log_f, fieldnames=log_fields, extrasaction="ignore")
        writer.writeheader()

        for idx, row in enumerate(queue, start=1):
            doi       = row["doi"]
            publisher = row["publisher"]
            url       = row["url"]
            delay     = PUBLISHER_DELAY.get(publisher, DEFAULT_DELAY)

            print(f"[{idx:>4}/{len(queue)}] {publisher:<18} {doi}")

            result = download_one(doi, url, publisher, out_dir, args.min_kb, args.timeout)

            # SHA-256 去重检查
            if result.get("sha256") and result["status"] == "success":
                if result["sha256"] in sha_seen:
                    result["status"] = "duplicate"
                    result["reason"] = f"内容与 {sha_seen[result['sha256']]} 重复"
                    print(f"       ⚠️  重复内容！与 {sha_seen[result['sha256']]} 相同")
                else:
                    sha_seen[result["sha256"]] = doi

            # 打印结果
            status_icon = {
                "success":        "✅",
                "skipped_exists": "⏭ ",
                "no_access":      "🔒",
                "not_found":      "❓",
                "invalid_pdf":    "❌",
                "timeout":        "⏱ ",
                "duplicate":      "♻️ ",
            }.get(result["status"], "⚠️ ")

            size_str = f"  {result.get('size_kb', '')} KB" if result.get("size_kb") else ""
            reason_str = f"  [{result.get('reason','')}]" if result.get("reason") else ""
            print(f"       {status_icon} {result['status']}{size_str}{reason_str}")

            # 统计
            bucket = result["status"] if result["status"] in stats else "error"
            stats[bucket] = stats.get(bucket, 0) + 1

            # 写日志
            writer.writerow({
                **row,
                **result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            log_f.flush()

            # 限速（最后一条不等）
            if idx < len(queue):
                time.sleep(delay)

    # 汇总
    print(f"\n{'='*60}")
    print(f"  下载完成")
    print(f"  成功：      {stats.get('success', 0)}")
    print(f"  已存在跳过：{stats.get('skipped_exists', 0)}")
    print(f"  无访问权限：{stats.get('no_access', 0)}")
    print(f"  内容无效：  {stats.get('invalid_pdf', 0)}")
    print(f"  重复内容：  {stats.get('duplicate', 0)}")
    print(f"  其他错误：  {stats.get('error', 0)}")
    print(f"  日志文件：  {log_path}")
    print(f"{'='*60}\n")

    # 写汇总 JSON
    summary = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "input": str(input_path),
        "out_dir": str(out_dir),
        "stats": stats,
        "skipped_route_count": len(skipped_routes),
        "skipped_routes": list({r["route"] for r in skipped_routes}),
    }
    summary_path = out_dir / "download_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"汇总报告：{summary_path}\n")


# ──────────────────────────────────────────────────────────────────────────────
#  命令行入口
# ──────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="SAF 文献自动下载脚本 — 仅处理 direct/verified 路由"
    )
    parser.add_argument(
        "--input", required=True,
        help="输入 CSV 文件路径（app.py 导出的队列，或含 DOI 列的原始 xlsx/csv）"
    )
    parser.add_argument(
        "--out-dir", default="./downloads",
        help="PDF 保存目录（默认 ./downloads）"
    )
    parser.add_argument(
        "--min-kb", type=int, default=20,
        help="PDF 最小体积 KB，低于此值视为无效（默认 20）"
    )
    parser.add_argument(
        "--timeout", type=int, default=60,
        help="单次请求超时秒数（默认 60）"
    )
    parser.add_argument(
        "--test", type=int, default=0,
        help="测试模式：只下载前 N 条（默认 0=全部）"
    )
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()

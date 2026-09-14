#!/usr/bin/env python
"""
run_llm_extraction.py
读取 prepare_prompt_packets.py 生成的 prompt packets (.jsonl)，
逐条发给 LLM，拿到结构化抽取结果，写出 extractions.jsonl。

这是第二阶段（自动抠取数据）流程中真正"调用大模型"的那一步，
衔接 prepare_prompt_packets.py（准备输入）和 qc_validate_extractions.py（校验输出）。

用法：
  python run_llm_extraction.py \
      --packets sample_prompt_packets.jsonl \
      --prompts-dir prompts \
      --out extractions.jsonl \
      --model gpt-4o-mini \
      --api-key sk-xxx \
      --base-url https://api.openai-proxy.org/v1

环境变量也可以提供 API Key（更安全，不会留在命令行历史里）：
  设置 OPENAI_API_KEY 后可以不传 --api-key
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ── 阶段 → 提示词文件 的映射，必须和 prepare_prompt_packets.py 里 PROMPT_FILES 保持一致 ──
STAGE_PROMPT_FILENAMES = {
    "metadata": "01_metadata.md",
    "catalyst": "02_catalyst.md",
    "reaction_conditions": "03_reaction_conditions.md",
    "performance": "04_performance.md",
    "provenance_confidence": "05_provenance_confidence.md",
}


def load_prompt_templates(prompts_dir: Path) -> dict[str, str]:
    """读取5个阶段的提示词模板全文，缓存起来避免重复读盘。"""
    templates = {}
    for stage, filename in STAGE_PROMPT_FILENAMES.items():
        path = prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少提示词文件: {path}")
        templates[stage] = path.read_text(encoding="utf-8")
    return templates


def build_user_message(packet: dict[str, Any]) -> str:
    """
    把一个 prompt packet（包含 context_blocks、metadata_prior 等）
    拼成发给LLM的用户消息正文。
    """
    parts = [
        f"paper_id: {packet.get('paper_id')}",
        f"stage: {packet.get('stage')}",
        f"file_name: {packet.get('file_name', '')}",
    ]

    prior = packet.get("metadata_prior") or {}
    if prior:
        parts.append("已知元数据线索（仅供参考，需用context_blocks中的证据确认）:")
        parts.append(json.dumps(prior, ensure_ascii=False, indent=2))

    parts.append("\n证据文本块（按相关性排序）:")
    for block in packet.get("context_blocks", []):
        parts.append(f"\n--- 第 {block.get('page')} 页 (相关度 {block.get('selection_score')}) ---")
        captions = block.get("captions") or []
        if captions:
            parts.append("表格/图注: " + " | ".join(captions))
        parts.append(block.get("text", "")[:3000])  # 防止单块过长

    parts.append(
        "\n请严格按照系统提示中规定的 JSON Schema 输出，"
        "只返回JSON对象本身，不要markdown代码块包裹，不要任何解释文字。"
    )
    return "\n".join(parts)


def strip_json_fences(text: str) -> str:
    """去掉LLM可能加的```json ... ```包裹，提取纯JSON文本。"""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def call_llm(
    client,
    model: str,
    system_prompt: str,
    user_message: str,
    max_retries: int = 3,
    retry_delay: float = 3.0,
) -> dict[str, Any] | None:
    """调用LLM，带重试。返回解析后的JSON dict，失败返回None。"""
    last_error = ""
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0,  # 抽取任务要确定性输出，不要发散
            )
            raw_text = response.choices[0].message.content or ""
            clean_text = strip_json_fences(raw_text)
            return json.loads(clean_text)
        except json.JSONDecodeError as exc:
            last_error = f"JSON解析失败: {exc}"
        except Exception as exc:  # noqa: BLE001 - 网络/限流/超时等都要重试
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < max_retries:
            time.sleep(retry_delay * attempt)  # 指数退避

    print(f"  [失败] 重试{max_retries}次后仍失败: {last_error}", file=sys.stderr)
    return None


def run(args: argparse.Namespace) -> dict[str, Any]:
    from openai import OpenAI
    import httpx

    api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError(
            "未提供 API Key。请用 --api-key 传入，"
            "或设置环境变量 OPENAI_API_KEY（更安全，推荐）。"
        )

    client = OpenAI(
        base_url=args.base_url,
        api_key=api_key,
        http_client=httpx.Client(base_url=args.base_url, follow_redirects=True),
    )

    prompts_dir = Path(args.prompts_dir)
    templates = load_prompt_templates(prompts_dir)

    packets_path = Path(args.packets)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with packets_path.open("r", encoding="utf-8") as f:
        all_packets = [json.loads(line) for line in f if line.strip()]

    if args.limit:
        all_packets = all_packets[: args.limit]

    stats = {"total": len(all_packets), "success": 0, "failed": 0, "skipped_no_template": 0}

    print(f"\n{'='*60}")
    print(f"  LLM 数据抽取")
    print(f"  任务包: {len(all_packets)} 条")
    print(f"  模型: {args.model}")
    print(f"  输出: {out_path}")
    print(f"{'='*60}\n")

    with out_path.open("w", encoding="utf-8") as out_handle:
        for i, packet in enumerate(all_packets, 1):
            stage = packet.get("stage", "")
            paper_id = packet.get("paper_id", "")

            if stage not in templates:
                stats["skipped_no_template"] += 1
                print(f"[{i:>4}/{len(all_packets)}] {paper_id} / {stage}  [跳过-无对应提示词]")
                continue

            print(f"[{i:>4}/{len(all_packets)}] {paper_id} / {stage}  正在抽取...")

            system_prompt = templates[stage]
            user_message = build_user_message(packet)

            result = call_llm(client, args.model, system_prompt, user_message)

            if result is None:
                stats["failed"] += 1
                error_record = {
                    "paper_id": paper_id,
                    "stage": stage,
                    "error": "llm_call_failed",
                }
                out_handle.write(json.dumps(error_record, ensure_ascii=False) + "\n")
                continue

            # 确保关键字段存在，方便后续 qc_validate_extractions.py 校验
            result.setdefault("paper_id", paper_id)
            result.setdefault("stage", stage)

            out_handle.write(json.dumps(result, ensure_ascii=False) + "\n")
            out_handle.flush()
            stats["success"] += 1

            if args.delay:
                time.sleep(args.delay)

    print(f"\n{'='*60}")
    print(f"  完成！成功 {stats['success']} / {stats['total']}")
    print(f"  失败: {stats['failed']}, 跳过: {stats['skipped_no_template']}")
    print(f"{'='*60}\n")

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="对prompt packets逐条调用LLM抽取结构化数据")
    parser.add_argument("--packets", required=True, help="prepare_prompt_packets.py生成的jsonl路径")
    parser.add_argument("--prompts-dir", required=True, help="存放5个阶段.md提示词的目录")
    parser.add_argument("--out", required=True, help="输出extractions.jsonl路径")
    parser.add_argument("--model", default="gpt-4o-mini", help="模型名称")
    parser.add_argument("--api-key", default="", help="API Key（也可用环境变量OPENAI_API_KEY）")
    parser.add_argument("--base-url", default="https://api.openai-proxy.org/v1", help="API代理地址")
    parser.add_argument("--limit", type=int, default=0, help="本次处理条数限制，0=全部")
    parser.add_argument("--delay", type=float, default=0.5, help="请求间隔秒数，避免限流")
    args = parser.parse_args()

    stats = run(args)
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""推荐排序与缺口检测（FR-007 / FR-010 / FR-011）。

``recommended`` 仅在「成功出图 + 数据点 ≥ 阈值 + 美观四项全过」时为真；
缺口（问答出图 < 3 或手动绘图 < 1）显式报出，绝不用低质量图表凑数。
"""
from __future__ import annotations

from . import settings as S

AESTHETIC_KEYS = ("no_label_overlap", "no_text_truncation", "axes_legend_complete", "theme_consistent")


def aesthetics_passed(report: dict | None) -> bool:
    if not report:
        return False
    return all(bool(report.get(k)) for k in AESTHETIC_KEYS)


def is_recommended(result: dict, min_data_points: int | None = None) -> bool:
    threshold = S.MIN_DATA_POINTS if min_data_points is None else int(min_data_points)
    return (result.get("verdict") == "chart_ok"
            and int(result.get("data_points") or 0) >= threshold
            and aesthetics_passed(result.get("aesthetics")))


def _sort_key(result: dict) -> tuple:
    """排序依据：数据点数 → 美观余量（交叠比越小越好）→ 图型多样性（按 type 名稳定排序）。"""
    report = result.get("aesthetics") or {}
    return (
        -int(result.get("data_points") or 0),
        float(report.get("max_overlap_ratio") or 0.0),
        str(result.get("chart_type") or "zzz"),
        str(result.get("id") or ""),
    )


def rank_results(results: list[dict], min_data_points: int | None = None) -> dict:
    """就地写入 ``recommended`` / ``rank``，返回 summary 与缺口报告。"""
    threshold = S.MIN_DATA_POINTS if min_data_points is None else int(min_data_points)
    recommended = [r for r in results if is_recommended(r, threshold)]
    recommended.sort(key=_sort_key)
    for r in results:
        r["recommended"] = False
        r["rank"] = 0
    for index, r in enumerate(recommended, start=1):
        r["recommended"] = True
        r["rank"] = index

    summary = {
        "total": len(results),
        "chart_ok": sum(1 for r in results if r.get("verdict") == "chart_ok"),
        "table_only": sum(1 for r in results if r.get("verdict") == "table_only"),
        "failed": sum(1 for r in results if r.get("verdict") == "failed"),
        "recommended": len(recommended),
        "manual_recommended": sum(1 for r in recommended if r.get("source") == "manual"),
    }

    issues: list[str] = []
    if summary["recommended"] - summary["manual_recommended"] < S.MIN_CHART_SHOTS:
        issues.append(
            f"insufficient_qualified_scenes: 合格问答出图仅 "
            f"{summary['recommended'] - summary['manual_recommended']} 个，需 ≥ {S.MIN_CHART_SHOTS}"
        )
    if summary["manual_recommended"] < S.MIN_MANUAL_SHOTS:
        issues.append(
            f"insufficient_manual_sources: 合格手动绘图仅 {summary['manual_recommended']} 个，"
            f"需 ≥ {S.MIN_MANUAL_SHOTS}"
        )
    return {"summary": summary, "issues": issues,
            "recommended_ids": [r["id"] for r in recommended]}


def suggestions(result: dict) -> list[str]:
    """对未通过判定的候选中给出可执行的改进建议（供 probe 报告使用）。"""
    tips: list[str] = []
    if result.get("verdict") == "table_only":
        if result.get("intent") == "data":
            tips.append("提问偏聚合统计（intent=data 只返回单行结果）；改为「分组 / 趋势 / 对比 / 分布」句式")
        else:
            tips.append("界面未渲染图表节点；换一个更适合可视化的维度（如按年份/类别分组）")
    elif result.get("verdict") == "failed":
        code = result.get("error_code")
        if code == "llm_auth":
            tips.append("服务端模型凭据不可用，请配置新的有效凭据后重试")
        elif code == "no_schema":
            tips.append("数据库表结构未就绪，等待后端完成 schema 加载")
        else:
            tips.append(f"该提问执行失败（error_code={code}），调整提问或先在界面上手动验证")
    elif result.get("verdict") == "chart_ok" and not result.get("recommended"):
        points = int(result.get("data_points") or 0)
        if points < S.MIN_DATA_POINTS:
            tips.append(f"数据点仅 {points} 个（< {S.MIN_DATA_POINTS}），换一个维度更多的字段做分组/对比")
        report = result.get("aesthetics") or {}
        if report.get("issues"):
            tips.append("排版问题：" + "；".join(str(i) for i in report["issues"][:2]))
    return tips

import pandas as pd
import streamlit as st
import plotly.express as px

_TITLE_MAP = {"line": "折线图", "bar": "柱状图", "scatter": "散点图", "pie": "饼图"}


def _safe_nunique(s: "pd.Series") -> int:
    """统计列唯一值数，兼容 jsonb/dict/list 等不可哈希值（转字符串后统计）。"""
    try:
        return int(s.nunique(dropna=True))
    except TypeError:
        return int(s.astype(str).nunique(dropna=True))


def _is_scalar_col(df: pd.DataFrame, col: str) -> bool:
    """列值是否全部为标量（不含 jsonb/dict/list，避免渲染成字符串）。"""
    try:
        return not bool(df[col].map(lambda v: isinstance(v, (dict, list))).any())
    except Exception:
        return True


def auto_pie_columns(df, max_categories: int = 15):
    """自动挑选饼图的分类列与占比列，无需用户手动指定。

    - 占比列：数值列（优先唯一值较多、有变化的列）
    - 分类列：标量列中唯一值数量适中（2 ~ max_categories）的列，文本优先
    - 返回 (分类列, 占比列)；两者必然不同列；无法组合时返回 None
    """
    if df is None or df.empty:
        return None

    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    if not numeric:
        return None

    numeric.sort(key=lambda c: (int(_safe_nunique(df[c]) <= 1), c))
    value_col = numeric[0]

    cands = []
    for c in df.columns:
        if c == value_col or not _is_scalar_col(df, c):
            continue
        n = _safe_nunique(df[c])
        if 2 <= n <= max_categories:
            is_numeric = pd.api.types.is_numeric_dtype(df[c])
            cands.append((int(is_numeric), n, c))

    if not cands:
        return None

    cands.sort()
    return cands[0][2], value_col


def _apply_layout(fig, title: str = ""):
    fig.update_layout(
        template="plotly_dark",
        title=dict(text=title, x=0.02, font=dict(size=16)),
        font=dict(family="Microsoft YaHei"),
        legend=dict(orientation="h", y=1.12, x=0.02),
        hoverlabel=dict(bgcolor="#1e293b", font=dict(family="Microsoft YaHei")),
        plot_bgcolor="rgba(20, 30, 60, 0.6)",
        paper_bgcolor="rgba(0, 0, 0, 0)",
        margin=dict(l=40, r=20, t=70, b=40),
    )
    return fig


def render_chart(df, chart_type='line', x=None, y=None, title: str = ""):
    if df is None:
        st.info('无数据可渲染')
        return

    cols = list(df.columns)
    if x is not None and x not in cols:
        x = None

    if chart_type == 'pie':
        y = y if y in cols else None
        if x is None or y is None:
            st.info('所选列不在当前结果集中，请重新选择')
            return
        fig = px.pie(df, names=x, values=y)
    else:
        y = [c for c in (y if isinstance(y, list) else [y]) if c in cols]
        if x is None or not y:
            st.info('所选列不在当前结果集中，请重新选择')
            return
        fig = px.line(df, x=x, y=y) if chart_type == 'line' else \
              px.bar(df, x=x, y=y) if chart_type == 'bar' else \
              px.scatter(df, x=x, y=y)
        fig.update_xaxes(gridcolor="rgba(148, 163, 184, 0.15)", zerolinecolor="rgba(148, 163, 184, 0.2)")
        fig.update_yaxes(gridcolor="rgba(148, 163, 184, 0.15)", zerolinecolor="rgba(148, 163, 184, 0.2)")
    _apply_layout(fig, title or _TITLE_MAP.get(chart_type, "图表"))
    st.plotly_chart(fig, use_container_width=True)

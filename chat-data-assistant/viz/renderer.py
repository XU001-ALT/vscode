import streamlit as st
import plotly.express as px

_TITLE_MAP = {"line": "折线图", "bar": "柱状图", "scatter": "散点图", "pie": "饼图"}


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

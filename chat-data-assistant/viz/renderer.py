import streamlit as st
import plotly.express as px


def render_chart(df, chart_type='line', x=None, y=None):
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
    st.plotly_chart(fig, use_container_width=True)

import streamlit as st
import plotly.express as px


def render_chart(df, chart_type='line', x=None, y=None):
    if df is None:
        st.info('无数据可渲染')
        return
    if chart_type == 'pie':
        fig = px.pie(df, names=x, values=y)
    else:
        fig = px.line(df, x=x, y=y) if chart_type == 'line' else \
              px.bar(df, x=x, y=y) if chart_type == 'bar' else \
              px.scatter(df, x=x, y=y)
    st.plotly_chart(fig, use_container_width=True)

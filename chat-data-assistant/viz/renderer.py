import streamlit as st
import plotly.express as px


def render_chart(df, chart_type='line', x=None, y=None):
    if df is None:
        st.info('无数据可渲染')
        return
    if chart_type == 'line':
        fig = px.line(df, x=x, y=y)
    elif chart_type == 'bar':
        fig = px.bar(df, x=x, y=y)
    elif chart_type == 'scatter':
        fig = px.scatter(df, x=x, y=y)
    elif chart_type == 'pie':
        fig = px.pie(df, names=x, values=y)
    else:
        fig = px.line(df, x=x, y=y)
    st.plotly_chart(fig, use_container_width=True)

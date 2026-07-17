import streamlit as st
import plotly.express as px


def render_chart(df, chart_type='line', x=None, y=None):
    if df is None:
        st.info('无数据可渲染')
        return
    if chart_type == 'line':
        st.line_chart(df.set_index(x)[y])
    else:
        fig = px.line(df, x=x, y=y)
        st.plotly_chart(fig)

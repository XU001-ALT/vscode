import streamlit as st
from viz.renderer import render_chart


def render():
    st.subheader("生成 SQL & 数据预览")
    last_sql = st.session_state.get('last_sql')
    df = st.session_state.get('last_df')

    left, right = st.columns(2)
    with left:
        st.markdown("**SQL 语句**")
        if last_sql:
            st.code(last_sql, language='sql')
        else:
            st.info("暂无生成的 SQL")

    with right:
        st.markdown("**数据预览**")
        if df is not None:
            st.dataframe(df.head(200))
        else:
            st.info("目前没有查询结果，发送查询以生成 SQL 并执行。")

    st.markdown("---")
    st.subheader("图表配置")
    if df is not None:
        cols = list(df.columns)
        chart_type = st.selectbox("图表类型", ["line", "bar", "scatter", "pie"], index=0, key="chart_type")
        x_col = st.selectbox("X 轴", cols, key="chart_x")
        y_cols = st.multiselect("Y 轴（可多选）", cols, default=[cols[1]] if len(cols) > 1 else [cols[0]], key="chart_y")
        if st.button("渲染图表"):
            if not x_col or not y_cols:
                st.warning("请选择 X 轴与至少一个 Y 轴列")
            else:
                render_chart(df, chart_type=chart_type, x=x_col, y=y_cols[0])
    else:
        st.info("要渲染图表，请先执行 SQL 并得到数据（见左侧）")

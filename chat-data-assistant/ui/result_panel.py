import streamlit as st
from viz.renderer import render_chart


def render():
    st.markdown('<p class="section-header">生成 SQL & 数据预览</p>', unsafe_allow_html=True)
    last_sql = st.session_state.get('last_sql')
    df = st.session_state.get('last_df')

    left, right = st.columns(2)
    with left:
        st.markdown('<p style="color: #38bdf8; font-weight: 600;">SQL 语句</p>', unsafe_allow_html=True)
        if last_sql:
            st.code(last_sql, language='sql')
        else:
            st.info("暂无生成的 SQL")

    with right:
        st.markdown('<p style="color: #38bdf8; font-weight: 600;">数据预览</p>', unsafe_allow_html=True)
        if df is not None:
            st.dataframe(df.head(200))
        else:
            st.info("目前没有查询结果，发送查询以生成 SQL 并执行。")

    st.markdown("---")
    st.markdown('<p class="section-header">图表配置</p>', unsafe_allow_html=True)
    if df is not None:
        cols = list(df.columns)
        chart_type = st.session_state.get('chart_type', 'line')

        if chart_type == 'pie':
            name_col = st.selectbox("分类列", cols, key="pie_names")
            value_col = st.selectbox("数值列", cols, key="pie_values")
            if name_col and value_col:
                render_chart(df, chart_type='pie', x=name_col, y=value_col)
        else:
            chart_type_label = {"line": "折线图", "bar": "柱状图", "scatter": "散点图"}.get(chart_type, "折线图")
            st.info(f"当前图表类型：{chart_type_label}")
            x_col = st.selectbox("X 轴", cols, key="chart_x")
            y_cols = st.multiselect("Y 轴（可多选）", cols, default=[cols[1]] if len(cols) > 1 else [cols[0]], key="chart_y")
            if x_col and y_cols:
                render_chart(df, chart_type=chart_type, x=x_col, y=y_cols[0])
    else:
        st.info("要渲染图表，请先执行 SQL 并得到数据（见左侧）")

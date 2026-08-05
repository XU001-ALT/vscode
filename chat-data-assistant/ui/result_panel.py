import pandas as pd
import streamlit as st
from viz.renderer import render_chart, auto_pie_columns


def _valid_columns(df: pd.DataFrame, cols: list) -> list:
    """过滤出当前结果集真实存在的列（防止 session_state 残留旧查询的列名）"""
    return [c for c in cols if c in df.columns]


def render():
    st.markdown('<p class="section-header">生成 SQL & 数据预览</p>', unsafe_allow_html=True)
    last_sql = st.session_state.get('last_sql')
    df = st.session_state.get('last_df')

    left, right = st.columns(2)
    with left:
        st.markdown('<p style="color: #60a5fa; font-weight: 600;">SQL 语句</p>', unsafe_allow_html=True)
        if last_sql:
            st.code(last_sql, language='sql')
        else:
            st.info("暂无生成的 SQL")

    with right:
        st.markdown('<p style="color: #60a5fa; font-weight: 600;">数据预览</p>', unsafe_allow_html=True)
        if df is not None:
            st.dataframe(df.head(200))
        else:
            st.info("目前没有查询结果，发送查询以生成 SQL 并执行。")

    st.markdown("---")
    st.markdown('<p class="section-header">图表配置</p>', unsafe_allow_html=True)
    if df is not None:
        cols = list(df.columns)
        # 结果集列变化时，清空图表控件状态，让默认值重新生效（防止切换查询后 Y 轴多选残留为空）
        if st.session_state.get('_chart_cols_key') != tuple(cols):
            for _k in ('chart_x', 'chart_y', 'chart_type_selector', 'use_auto_chart',
                       'pie_names', 'pie_values', 'chart_type'):
                st.session_state.pop(_k, None)
            st.session_state['_chart_cols_key'] = tuple(cols)
        rec = st.session_state.get('chart_recommendation') or {}
        # 每次新查询会生成新的 AI 推荐对象：识别到新对象时重置"使用 AI 推荐"为默认勾选，
        # 仅控件交互导致的 rerun（推荐对象未变）保留用户选择
        if st.session_state.get('_last_rec') is not rec:
            st.session_state.pop('use_auto_chart', None)
            st.session_state['_last_rec'] = rec

        # AI 自动推荐：基于用户问题推断图表类型与坐标轴（如"各材料占比"→饼图）
        rec_x = _valid_columns(df, [rec.get('x_col')]) if rec.get('x_col') else []
        rec_y = _valid_columns(df, [rec.get('y_col')]) if rec.get('y_col') else []
        use_auto = False
        if rec_x and rec_y:
            use_auto = st.checkbox("使用 AI 推荐的图表配置", value=True, key="use_auto_chart")
            if use_auto:
                if rec.get('reason'):
                    st.info(f"AI 推荐理由：{rec['reason']}")
                render_chart(df, chart_type=rec['chart_type'], x=rec_x[0], y=rec_y[0])
                st.caption(f"图表类型：{rec['chart_type']}，X 轴：{rec_x[0]}，Y 轴：{rec_y[0]}")
                return

        # 手动模式
        chart_options = {"折线图": "line", "柱状图": "bar", "散点图": "scatter", "饼图": "pie"}
        chart_label = st.radio(
            "图表类型（取消 AI 推荐后手动选择）",
            list(chart_options.keys()),
            horizontal=True,
            key="chart_type_selector",
        )
        chart_type = chart_options[chart_label]
        st.session_state['chart_type'] = chart_type

        if chart_type == 'pie':
            auto = auto_pie_columns(df)
            if auto:
                name_col, value_col = auto
                st.caption(f"自动识别：分类={name_col}，占比={value_col}")
                render_chart(df, chart_type='pie', x=name_col, y=value_col)
                return
            # 手动兜底：数值列选项剔除已选分类列，二者互斥，避免出现重复列
            name_col = st.selectbox("分类列", cols, key="pie_names")
            numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
            value_options = [c for c in numeric_cols if c != name_col]
            if not value_options:
                st.info("当前结果集中没有可用的数值列作为占比，请调整查询")
                return
            value_col = st.selectbox("数值列", value_options, key="pie_values")
            render_chart(df, chart_type='pie', x=name_col, y=value_col)
        else:
            chart_type_label = {"line": "折线图", "bar": "柱状图", "scatter": "散点图"}.get(chart_type, "折线图")
            st.info(f"当前图表类型：{chart_type_label}")
            x_col = st.selectbox("X 轴", cols, key="chart_x")
            numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
            y_options = [c for c in numeric_cols if c != x_col]
            if not y_options:
                st.info("当前结果集中没有可用的数值列，请调整查询")
                return
            if 'chart_y' not in st.session_state:
                st.session_state['chart_y'] = [y_options[0]]
            else:
                prev_y = st.session_state['chart_y']
                if any(c not in y_options for c in prev_y):
                    st.session_state['chart_y'] = [y_options[0]]
            y_cols = st.multiselect("Y 轴（可多选，仅数值列）", y_options, key="chart_y")
            y_cols = _valid_columns(df, y_cols)
            y_cols = [c for c in y_cols if c != x_col]
            if x_col and y_cols:
                render_chart(df, chart_type=chart_type, x=x_col, y=y_cols)
    else:
        st.info("要渲染图表，请先执行 SQL 并得到数据（见左侧）")

import pandas as pd
import streamlit as st
from viz.renderer import render_chart, auto_pie_columns
from core.translations import t


def _valid_columns(df: pd.DataFrame, cols: list) -> list:
    return [c for c in cols if c in df.columns]


def _render_chart_section(df: pd.DataFrame):
    cols = list(df.columns)
    if st.session_state.get('_chart_cols_key') != tuple(cols):
        for _k in ('chart_x', 'chart_y', 'chart_type_selector', 'use_auto_chart',
                   'pie_names', 'pie_values', 'chart_type'):
            st.session_state.pop(_k, None)
        st.session_state['_chart_cols_key'] = tuple(cols)
    rec = st.session_state.get('chart_recommendation') or {}
    if st.session_state.get('_rec_gen') != st.session_state.get('_seen_rec_gen'):
        st.session_state.pop('use_auto_chart', None)
        st.session_state['_seen_rec_gen'] = st.session_state.get('_rec_gen')

    rec_x = _valid_columns(df, [rec.get('x_col')]) if rec.get('x_col') else []
    rec_y = _valid_columns(df, [rec.get('y_col')]) if rec.get('y_col') else []
    use_auto = False
    if rec_x and rec_y:
        use_auto = st.checkbox(t("use_ai_rec"), value=True, key="use_auto_chart")
        if use_auto:
            if rec.get('reason'):
                st.info(t("ai_reason") + rec['reason'])
            render_chart(df, chart_type=rec['chart_type'], x=rec_x[0], y=rec_y[0])
            st.caption(t("chart_type_label") + rec['chart_type'] + "，" + t("x_axis") + rec_x[0] + "，" + t("y_axis") + rec_y[0])
            return

    chart_options = {t("line"): "line", t("bar"): "bar", t("scatter"): "scatter", t("pie"): "pie"}
    chart_label = st.radio(
        t("chart_type_manual"),
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
            st.caption(f"{t('auto_id')}：{t('category')}={name_col}，{t('val_label')}={value_col}")
            render_chart(df, chart_type='pie', x=name_col, y=value_col)
            return
        name_col = st.selectbox(t("category"), cols, key="pie_names")
        numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        value_options = [c for c in numeric_cols if c != name_col]
        if not value_options:
            st.info(t("no_numeric_pie"))
            return
        value_col = st.selectbox(t("value"), value_options, key="pie_values")
        render_chart(df, chart_type='pie', x=name_col, y=value_col)
    else:
        chart_type_label = {t("line"): t("line"), t("bar"): t("bar"), t("scatter"): t("scatter")}.get(chart_label, t("line"))
        st.info(t("current_chart") + chart_type_label)
        x_col = st.selectbox(t("x_axis").rstrip("："), cols, key="chart_x")
        numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        y_options = [c for c in numeric_cols if c != x_col]
        if not y_options:
            st.info(t("no_numeric"))
            return
        if 'chart_y' not in st.session_state:
            st.session_state['chart_y'] = [y_options[0]]
        else:
            prev_y = st.session_state['chart_y']
            if any(c not in y_options for c in prev_y):
                st.session_state['chart_y'] = [y_options[0]]
        y_cols = st.multiselect(t("y_axis_multi"), y_options, key="chart_y")
        y_cols = _valid_columns(df, y_cols)
        y_cols = [c for c in y_cols if c != x_col]
        if x_col and y_cols:
            render_chart(df, chart_type=chart_type, x=x_col, y=y_cols)


def render():
    # 语言切换后 tab label 变化，清除旧 key 防止 Streamlit 报错
    _cur_lang = st.session_state.get('lang', 'zh')
    _prev_lang = st.session_state.get('_prev_lang', 'zh')
    if _cur_lang != _prev_lang:
        st.session_state.pop('result_tabs', None)
        st.session_state['_prev_lang'] = _cur_lang

    st.markdown(f'<p class="section-header">{t("result_title")}</p>', unsafe_allow_html=True)
    df = st.session_state.get('last_df')

    tab_data, tab_chart = st.tabs(
        [t("tab_data"), t("tab_chart")],
        key="result_tabs",
    )

    with tab_data:
        if df is not None:
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                t("export_csv"), data=csv, file_name="query_result.csv",
                mime="text/csv", use_container_width=False,
            )
            st.dataframe(df)
        else:
            st.info(t("no_result"))

    with tab_chart:
        if df is not None:
            _render_chart_section(df)
        else:
            st.info(t("no_chart"))

import streamlit as st
from pathlib import Path
from core.translations import t


def render_home():
    """Home landing page. Only UI content is changed; application logic is untouched."""

    st.markdown(
        f"""
        <div class="cd-hero">
            <div class="cd-brand">chat-data</div>
            <h1>{t("home_title")}</h1>
            <p>{t("home_desc")}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Main introduction area - left: image, right: about
    left, right = st.columns([1, 1], gap="large")

    with left:
        asset = Path("assets/chat-data-home.png")
        if asset.exists():
            st.image(str(asset), use_container_width=True)
        else:
            st.markdown(
                """
                <div class="cd-card" style="height:100%;display:flex;align-items:center;justify-content:center;">
                    <div style="text-align:center;padding:35px 20px;">
                        <div style="font-size:64px;">◉</div>
                        <h2>chat-data</h2>
                        <p>AI Data Query Platform</p>
                        <p style="opacity:0.8;">Database · AI Query · Visualization</p>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with right:
        st.markdown("## About chat-data")
        st.markdown(
            """
            chat-data 是一个面向智能数据分析场景的 AI 数据查询平台，通过自然语言交互方式连接用户与数据库，帮助用户更加高效地探索、查询和分析数据。

            平台结合数据库结构理解、智能查询生成以及数据可视化能力，使用户无需编写复杂 SQL，即可完成从数据查询、结果获取到分析展示的完整流程。

            在 **Home** 页面，用户可以了解平台整体功能、使用流程以及运行环境要求；在 **AI Query** 页面，用户可以通过自然语言提出数据查询需求，系统将根据数据库信息生成查询结果，并提供数据展示与可视化分析；在 **Settings** 页面，用户可以完成平台运行所需的基础配置，包括 API 设置、数据库连接以及 Schema 信息管理。
            """
        )

    st.markdown("<br>", unsafe_allow_html=True)

    st.markdown(f"## {t('how_to_use')}")

    steps = [
        (t("step_config"), t("step_config_desc")),
        (t("step_query"), t("step_query_desc")),
        (t("step_analyze"), t("step_analyze_desc")),
    ]

    cols = st.columns(3)
    for index, (col, (title, desc)) in enumerate(zip(cols, steps), start=1):
        with col:
            st.markdown(
                f"""
                <div class="cd-card cd-step">
                    <div class="cd-number">0{index}</div>
                    <h3>{title}</h3>
                    <p>{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

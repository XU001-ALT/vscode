import streamlit as st
from pathlib import Path
from core.translations import t


def render_home():
    """Home landing page. Only UI content is changed; application logic is untouched."""

    st.markdown(
        f"""
        <div class="cd-hero" style="padding:2.5rem 2rem;">
            <div style="font-size:3.2rem;font-weight:700;color:white;letter-spacing:.05em;">{t("hero_slogan")}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    # Main introduction area - left: image, right: about
    left, right = st.columns([1, 1], gap="large")

    with left:
        asset = Path(__file__).resolve().parent.parent / "assets" / "chat-data-home.png"
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
        st.markdown(f"## {t('about_title')}")
        st.markdown(t("about_p1"))
        st.markdown(t("about_p2"))
        st.markdown(t("about_p3"))

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

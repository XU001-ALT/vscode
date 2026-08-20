
import streamlit as st


def render_home():
    st.markdown(
        """
        <div class="cd-card">
            <h1 style="color:white;">chat-data</h1>
            <h2 style="color:#93c5fd;">
            AI Data Query Platform
            </h2>
            <p style="color:#cbd5e1;font-size:1.05rem;">
            Intelligent natural language interface for database querying
            and visualization.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("## How to use")

    steps = [
        ("01  Configure", "Configure API, database and schema in Settings."),
        ("02  Query", "Ask questions about your data in AI Query."),
        ("03  Analyze", "Review returned data and visualizations."),
    ]

    cols = st.columns(3)

    for col, (title, desc) in zip(cols, steps):
        with col:
            st.markdown(
                f"""
                <div class="cd-card">
                    <h3 style="color:white;">{title}</h3>
                    <p style="color:#cbd5e1;">{desc}</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown(
        """
        <div class="cd-card">
            <h3 style="color:white;">Start with AI Query</h3>
            <p style="color:#cbd5e1;">
            Use natural language to explore your database.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

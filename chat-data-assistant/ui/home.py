import streamlit as st

def render_home():
    st.markdown("""
    <div class="cd-card">
    <h1 style="color:white;">chat-data</h1>
    <h2 style="color:#93c5fd;">AI Data Query Platform</h2>
    <p style="color:#cbd5e1;font-size:1.05rem;">
    Natural language interface for database query and visualization.
    </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## Before You Start")
    st.markdown("""
    <div class="cd-card">
    <h3 style="color:white;">Database Configuration Required</h3>
    <p style="color:#cbd5e1;">
    chat-data requires database connection and schema information before AI Query can be used.
    Please complete configuration in Settings first.
    </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## How to use")
    cols=st.columns(3)
    steps=[("01 Configure","Set API, database and schema in Settings."),("02 Query","Ask questions in AI Query."),("03 Analyze","Review data and charts.")]
    for c,(title,desc) in zip(cols,steps):
        with c:
            st.markdown(f"""
            <div class="cd-card">
            <h3 style="color:white;">{title}</h3>
            <p style="color:#cbd5e1;">{desc}</p>
            </div>
            """, unsafe_allow_html=True)

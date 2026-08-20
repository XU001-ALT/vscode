
"""chat-data UI theme."""

import streamlit as st


def apply_theme():
    st.markdown(
        """
        <style>
        :root {
            --cd-bg: #0b1020;
            --cd-card: rgba(18, 28, 55, .72);
            --cd-border: rgba(96,165,250,.35);
            --cd-text: #e8eefc;
            --cd-accent: #60a5fa;
        }

        .stApp,
        [data-testid="stAppViewContainer"] {
            background:
            radial-gradient(circle at top left, #172554 0%, transparent 35%),
            radial-gradient(circle at top right, #312e81 0%, transparent 30%),
            var(--cd-bg);
            color: var(--cd-text);
        }

        section[data-testid="stSidebar"] {
            background: rgba(7,12,28,.92);
            border-right: 1px solid var(--cd-border);
            min-width: 220px;
            max-width: 220px;
        }

        section[data-testid="stSidebar"] .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }

        .cd-card {
            background: var(--cd-card);
            border: 1px solid var(--cd-border);
            border-radius: 18px;
            padding: 18px;
            backdrop-filter: blur(12px);
        }

        .main-title {
            font-size: 1.55rem;
            font-weight: 700;
            color: white;
            padding: 12px 0;
        }

        .chat-title,
        .section-header {
            color: white !important;
            font-weight: 650;
        }

        .sidebar-title {
            font-size: 1rem;
            font-weight: 700;
            color: white;
        }

        div[data-testid="stTextInput"] input {
            background: rgba(15,23,42,.8);
            color: white;
            border-radius: 14px;
            border: 1px solid rgba(96,165,250,.4);
        }

        button[kind="primary"] {
            border-radius: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def card(title, body):
    st.markdown(f'''
    <div class="cd-card">
      <div class="section-header">{title}</div>
      <div>{body}</div>
    </div>
    ''', unsafe_allow_html=True)

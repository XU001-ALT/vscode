
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

        .cd-hero {
            padding: 3.5rem 2.5rem;
            text-align: center;
            border-radius: 24px;
            background: rgba(15, 23, 42, .55);
            border: 1px solid rgba(148,163,184,.25);
            margin-bottom: 1rem;
        }

        .cd-hero .cd-brand {
            font-size: 1.2rem;
            letter-spacing: .15em;
            color: #93c5fd;
            margin-bottom: 1rem;
        }

        .cd-hero h1 {
            font-size: 3rem;
            margin-bottom: .8rem;
            color: white;
        }

        .cd-hero p {
            color: #cbd5e1;
            font-size: 1.15rem;
        }

        .cd-step {
            min-height: 180px;
        }

        .cd-number {
            color: #60a5fa;
            font-size: 2rem;
            font-weight: 700;
        }

        .cd-entry {
            text-align: center;
        }

        /* 隐藏聊天消息的头像图标 */
        [data-testid="stChatMessageAvatar"] {
            display: none !important;
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

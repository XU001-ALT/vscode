import streamlit as st
from ui import render_sidebar, render_chat_panel, render_result_panel
from core import bootstrap

st.set_page_config(page_title="chat-data", page_icon=" H₂", layout="wide")

# 启动即后台自动连接数据库并拉取 schema，失败自动重试，用户无感
bootstrap.start()

st.markdown("""
<style>
    :root {
        --bg-color: #0e1424;
        --card-bg: rgba(20, 30, 60, 0.6);
        --border-color: #1d4ed8;
        --text-color: #e6ebff;
        --highlight-color: #fbbf24;
        --nav-bg: #0b1120;
        --accent-blue: #60a5fa;
    }

    /* 主背景 - 深海蓝 */
    .stApp, [data-testid="stAppViewContainer"] {
        background-color: var(--bg-color);
    }

    /* 侧边栏背景 */
    .stSidebar, section[data-testid="stSidebar"] {
        background-color: var(--nav-bg);
    }
    .stSidebar [data-testid="stMarkdown"] {
        color: var(--text-color);
    }

    /* 顶部 header */
    header {
        background-color: var(--nav-bg) !important;
        border-bottom: 1px solid #1e293b;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
    }
    header * {
        color: white !important;
    }

    /* 全局文字颜色 */
    .stMarkdown, .stMarkdown p, .stMarkdown li, label, .stLabel {
        color: var(--text-color) !important;
    }

    /* 标题和子标题 */
    h1, h2, h3, h4, h5, h6, [data-testid="stMarkdownContainer"] h1,
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3 {
        color: #fff !important;
    }

    /* 主标题 - 黑底白字横栏，固定在页面最顶部并横跨全宽（含侧边栏上方） */
    .main-title {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        width: 100%;
        height: 68px;
        line-height: 68px;
        padding: 0 20px;
        margin: 0;
        box-sizing: border-box;
        z-index: 999999;
        font-size: 1.6rem !important;
        font-weight: 700 !important;
        color: #ffffff;
        background: #000000;
        letter-spacing: 1px;
        text-align: center;
    }
    /* 顶栏下移到标题栏下方：既保留左上角「展开/收起侧边栏」的汉堡按钮，又不遮挡标题 */
    [data-testid="stHeader"] {
        position: fixed !important;
        top: 68px !important;
        left: 0 !important;
        right: 0 !important;
        background: transparent !important;
        border-bottom: none !important;
        box-shadow: none !important;
        z-index: 1000000 !important;
    }
    /* 整体内容区统一下移：黑底标题 68px 起 */
    [data-testid="stAppViewContainer"] {
        padding-top: 68px !important;
    }
    /* 布局容器：无外框，左右距界面边缘约 2mm（8px）；三个栏的边框自身构成整体边界 */
    [data-testid="stMainBlockContainer"] {
        max-width: none !important;
        min-height: calc(100vh - 76px);
        margin: 0 8px;
        padding: 0 !important;
        display: flex;
        flex-direction: column;
    }
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] {
        flex: 1;
        display: flex;
        flex-direction: column;
    }
    [data-testid="stMainBlockContainer"] > [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] {
        flex: 1;
        min-height: calc(100vh - 84px);
        align-items: stretch;
    }
    .main-title::before, .main-title::after {
        content: '';
        position: absolute;
        width: 12px;
        height: 12px;
        border: 2px solid var(--accent-blue);
    }
    .main-title::before { top: -1px; left: -1px; border-right: none; border-bottom: none; }
    .main-title::after { bottom: -1px; right: -1px; border-left: none; border-top: none; }

    /* Section 标题 - 卡片头风格 */
    .section-header {
        color: #fff !important;
        font-size: 1rem;
        font-weight: 600;
        text-align: center;
        padding: 10px 15px;
        background: rgba(30, 58, 138, 0.3);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        margin: 16px 0 12px 0;
    }

    /* 询问栏标题（与 section-header 同风格，但独立类名以便单独定位该栏） */
    .chat-title {
        color: #fff !important;
        font-size: 1rem;
        font-weight: 600;
        text-align: center;
        padding: 10px 15px;
        background: rgba(30, 58, 138, 0.3);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        margin: 0 0 12px 0;
    }

    /* 侧边栏标题 */
    .sidebar-title {
        color: #fff !important;
        font-size: 1.2rem;
        font-weight: 700;
        padding-bottom: 8px;
        border-bottom: 2px solid rgba(29, 78, 216, 0.4);
        margin-bottom: 16px;
    }

    .sidebar-section {
        color: var(--accent-blue) !important;
        font-size: 0.95rem;
        font-weight: 600;
        margin-top: 16px;
        margin-bottom: 8px;
    }

    /* 输入框标签 */
    label, .stLabel, [data-testid="stWidgetLabel"] {
        color: #94a3b8 !important;
        font-weight: 500;
    }

    /* 隐藏 deploy 按钮 */
    .stDeployButton {
        display: none;
    }

    /* 聊天输入框 */
    div[data-testid="stChatInput"],
    .stChatInput,
    textarea[aria-label="Chat input"] {
        border: 2px solid var(--border-color) !important;
        border-radius: 4px !important;
        background-color: var(--card-bg) !important;
        color: var(--text-color) !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.3);
        margin-bottom: 16px;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-color: var(--accent-blue) !important;
        box-shadow: 0 2px 12px rgba(96, 165, 250, 0.3);
    }

    /* 隐藏聊天气泡头像（红色人脸图标） */
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"] {
        display: none;
    }

    /* 聊天气泡 - 用户消息（卡片化） */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        background-color: rgba(30, 58, 138, 0.35);
        border: 1px solid rgba(29, 78, 216, 0.4);
        border-radius: 4px;
        padding: 12px;
        margin: 8px 0;
    }

    /* 聊天气泡 - 助手消息（卡片化） */
    [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
        background-color: var(--card-bg);
        border: 1px solid var(--border-color);
        border-radius: 4px;
        padding: 12px;
        margin: 8px 0;
    }

    /* 按钮样式 */
    .stButton > button {
        background-color: var(--accent-blue);
        color: #0b1120;
        border: none;
        border-radius: 4px;
        font-weight: 600;
    }
    .stButton > button:hover {
        background-color: #93c5fd;
    }

    /* 查询框旁「清空会话」按钮：窄列内拆两行（清空/会话），避免文字被截断 */
    .st-key-clear_session_btn button {
        font-size: 0.85rem;
        padding: 2px 6px;
        line-height: 1.3;
        white-space: normal;
    }

    /* 输入框和选择框 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    .stSelectbox > div > div,
    .stMultiSelect > div > div {
        background-color: var(--card-bg) !important;
        color: var(--text-color) !important;
        border-color: var(--border-color) !important;
    }

    /* 信息/警告/错误提示框 */
    .stAlert {
        background-color: var(--card-bg);
        border-color: var(--border-color);
        color: var(--text-color);
    }

    /* 代码块 */
    .stCode {
        background-color: var(--card-bg);
    }

    /* 数据表格 */
    .stDataFrame {
        background-color: var(--card-bg);
    }

    /* 分割线 */
    hr {
        border-color: rgba(29, 78, 216, 0.3);
    }

    /* 小标签/提示文字 */
    .small-label {
        color: #64748b;
        font-size: 0.85rem;
    }

    /* 数字高亮 - 琥珀金 */
    .highlight {
        color: var(--highlight-color);
        font-weight: bold;
        text-shadow: 0 0 10px rgba(251, 191, 36, 0.4);
    }

    /* ── 三栏布局：内部蓝边框独立区域（2px 亮蓝，边缘更清晰） ── */
    [data-testid="stColumn"]:has(.sidebar-title),
    [data-testid="stColumn"]:has(.chat-title),
    [data-testid="stColumn"]:has(.section-header) {
        border: 2px solid #3b82f6;
        border-radius: 4px;
        padding: 12px;
        background: var(--card-bg);
    }
    /* 三栏之间的间距压缩到约 6px（1~2 毫米），彼此贴近 */
    [data-testid="stMainBlockContainer"] [data-testid="stHorizontalBlock"]:has([data-testid="stColumn"]) {
        gap: 6px !important;
    }
    /* 左侧栏：其余内容均匀分布 */
    [data-testid="stColumn"]:has(.sidebar-title) {
        display: flex;
        flex-direction: column;
    }
    [data-testid="stColumn"]:has(.sidebar-title) > [data-testid="stVerticalBlock"] {
        flex: 1;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    /* 询问栏：对话在上，输入框固定在底部 */
    [data-testid="stColumn"]:has(.chat-title) {
        display: flex;
        flex-direction: column;
    }
    [data-testid="stColumn"]:has(.chat-title) > [data-testid="stVerticalBlock"] {
        flex: 1;
        display: flex;
        flex-direction: column;
    }
    [data-testid="stColumn"]:has(.chat-title) > [data-testid="stVerticalBlock"] > .st-key-query_box {
        margin-top: auto;
    }
    /* 询问栏的输入区（输入框 + 清空会话）整体包进蓝色边框 */
    .st-key-query_box {
        border: 2px solid #3b82f6 !important;
        border-radius: 4px;
        background: rgba(20, 30, 60, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# 顶部标题：黑底白字横栏；「清空会话」按钮已移至查询框旁（见 chat_panel）
st.markdown('<p class="main-title">智能绘图助手（chat-data）</p>', unsafe_allow_html=True)

# 后台连接成功后，把自动拉取的 Schema 同步进会话（不覆盖手动加载）
if not st.session_state.get('orm_schema'):
    boot = bootstrap.get_state()
    if boot.get('schema'):
        st.session_state['orm_schema'] = boot['schema']
        st.session_state['orm_schema_tables'] = boot['tables']

# 三栏布局：左侧栏 2 : 询问栏 2 : 结果栏 4，蓝边框分隔为独立区域
left_col, chat_col, result_col = st.columns([2, 2, 4], gap="small")
with left_col:
    render_sidebar()

with chat_col:
    render_chat_panel()

with result_col:
    render_result_panel()

if __name__ == '__main__':
    pass

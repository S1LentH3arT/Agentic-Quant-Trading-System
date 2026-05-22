import streamlit as st
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="Quant-Desk | 机构化量化中枢",
    page_icon="📈",
    layout="wide"
)

# Load Data Functions
def load_json():
    try:
        with open('TRADING_LOG.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"无法加载 TRADING_LOG.json: {e}")
        return {}

def load_knowledge():
    try:
        with open('KNOWLEDGE_BASE.md', 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        st.error(f"无法加载 KNOWLEDGE_BASE.md: {e}")
        return ""

# Initialize State
data = load_json()
knowledge = load_knowledge()

# Custom CSS for Professional Look
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1e222d; padding: 15px; border-radius: 10px; border: 1px solid #333; }
    .stDataFrame { border: 1px solid #333; }
    </style>
    """, unsafe_allow_html=True)

# Sidebar: System Status
st.sidebar.title("⚙️ 系统控制面板")
st.sidebar.markdown(f"**最后同步**: {data.get('last_updated', '未知')}")
if st.sidebar.button("🔄 同步本地数据库"):
    st.rerun()

st.sidebar.divider()
st.sidebar.subheader("🛡️ 风险指标")
mdd_limit = data.get('risk_metrics', {}).get('max_drawdown_limit', 0) * 100
st.sidebar.metric("MDD 阈值", f"{mdd_limit}%", delta_color="inverse")
st.sidebar.metric("当前回撤", f"{data.get('risk_metrics', {}).get('current_mdd', 0)}%", delta="-0.0%")

# Main Layout
st.title("📈 Quant-Desk | 机构化量化中枢")

# Row 1: Strategic Core
col1, col2 = st.columns([2, 1])
with col1:
    with st.expander("📜 最高指令集 (KNOWLEDGE_BASE)", expanded=False):
        st.markdown(knowledge)

with col2:
    st.subheader("🎯 今日重点监控")
    watch_list = data.get('portfolio', {}).get('watch_list', [])
    for item in watch_list:
        st.info(f"**{item['ticker']}** {item['name']} \n\n 属性: {item.get('beta', item.get('alpha', 'N/A'))} | 状态: {item['status']}")

st.divider()

# Row 2: Portfolio Management
st.subheader("💰 资本架构：双池模型")
p_col1, p_col2 = st.columns(2)

with p_col1:
    st.markdown("### 🏰 堡垒池 (Fortress Pool)")
    fortress = data.get('portfolio', {}).get('fortress_pool', [])
    if fortress:
        df_fort = pd.DataFrame(fortress)
        st.table(df_fort[['ticker', 'name', 'entry_price', 'role']])
    else:
        st.write("池子为空")

with p_col2:
    st.markdown("### 🏹 猎手池 (Hunter Pool)")
    hunter = data.get('portfolio', {}).get('hunter_pool', [])
    if hunter:
        df_hunt = pd.DataFrame(hunter)
        st.table(df_hunt[['ticker', 'name', 'entry_price', 'role']])
    else:
        st.write("池子为空")

# Row 3: Interaction Area
st.divider()
st.subheader("📨 碎片化情报输入 $\rightarrow$ 研判生成")
with st.container():
    user_input = st.text_area("输入碎片化情报 (例如: '美股AI大涨, 中信证券订单流异常')", placeholder="在这里输入您的碎片想法...")
    if st.button("🚀 生成量化研判单 (Ticket)"):
        if user_input:
            st.warning("⚠️ 本地 UI 仅作为展示。请将此内容发送给 Claude Agent 以激活【三层量化漏斗】分析。")
            st.markdown(f"**待处理素材**: `{user_input}`")
            st.markdown("---")
            st.markdown("**建议指令**: `读取 KNOWLEDGE_BASE.md 和 TRADING_LOG.json，针对以下素材生成交易单 Ticket: {user_input}`")
        else:
            st.error("请输入情报内容")

# Footer
st.caption(f"System Architecture: Asymmetry EV-Driven | Last modified: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

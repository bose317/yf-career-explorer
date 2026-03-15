import streamlit as st

st.set_page_config(page_title="YF Career Explorer", page_icon="⬛", layout="wide")

st.markdown("""
# YF Career Explorer
Three tools for Canadian labour market and career interest analysis.

Navigate using the sidebar:
- **Career Explorer** — NOC/CIP analysis, wages, skills (Statistics Canada data)
- **Holland Code Test** — RIASEC 48-question inventory + AI 5-layer analysis
- **Competence Comparison** — Side-by-side job competence for Holland × Career matches
""")

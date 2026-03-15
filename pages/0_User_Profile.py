"""Step 1 — User Profile
Collects basic information before entering the Career Explorer.
Saves to st.session_state["user_profile"].
"""
from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="Your Profile — Career Explorer",
    page_icon="⬛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS (own call) ────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"] > div,
.block-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #F8FAFC !important;
    color: #0F172A;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding: 0 !important; max-width: 100% !important; }

label { font-size: .8rem !important; font-weight: 600 !important; color: #334155 !important; }

div[data-testid="stTextInput"] input,
div[data-testid="stSelectbox"] > div > div {
    border-radius: 7px !important;
    border: 1.5px solid #E2E8F0 !important;
    font-size: .88rem !important;
}
div[data-testid="stRadio"] label { font-size: .85rem !important; font-weight: 500 !important; }

div[data-testid="stButton"] > button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: .88rem !important;
    border-radius: 7px !important;
    border: 1.5px solid #E2E8F0 !important;
    background: #fff !important;
    color: #0F172A !important;
    transition: all .15s ease !important;
}
div[data-testid="stButton"] > button[kind="primary"] {
    background: #0F172A !important;
    color: #fff !important;
    border-color: #0F172A !important;
}
div[data-testid="stButton"] > button[kind="primary"]:hover {
    background: #1E293B !important;
}
</style>
""", unsafe_allow_html=True)

# ── Build left-panel HTML as one complete string ──────────────
_features = [
    ("◎", "Occupations matched to your field"),
    ("◎", "Regional wage &amp; employment data"),
    ("◎", "Holland Code career alignment"),
    ("◎", "AI-powered competency gap advising"),
]
_feature_rows = ""
for _icon, _text in _features:
    _feature_rows += (
        "<div style='display:flex;align-items:center;gap:12px'>"
        "<span style='font-size:.8rem;color:#475569'>" + _icon + "</span>"
        "<span style='font-size:.82rem;color:#64748B'>" + _text + "</span>"
        "</div>"
    )

_left_panel = (
    "<div style='background:#0F172A;min-height:100vh;padding:64px 48px;"
    "box-sizing:border-box;display:flex;flex-direction:column;justify-content:center'>"

    "<div style='font-size:.62rem;font-weight:500;letter-spacing:.14em;"
    "color:#475569;text-transform:uppercase;margin-bottom:28px'>"
    "Step 01 of 04</div>"

    "<h2 style='font-size:2.6rem;font-weight:900;letter-spacing:-.04em;"
    "color:#F8FAFC;line-height:1.1;margin:0 0 20px'>"
    "Tell us<br>about<br>yourself.</h2>"

    "<p style='font-size:.9rem;color:#64748B;line-height:1.75;margin:0 0 44px'>"
    "A few details help us personalise your career analysis with "
    "relevant occupations, wages, and labour market data for your region.</p>"

    "<div style='display:flex;flex-direction:column;gap:14px'>"
    + _feature_rows +
    "</div></div>"
)

# ── Two-column layout ─────────────────────────────────────────
left, right = st.columns([1, 1.6], gap="large")

with left:
    st.markdown(_left_panel, unsafe_allow_html=True)

with right:
    # Padding wrapper — open + close in one call
    st.markdown(
        "<div style='padding:64px 48px 40px;min-height:100vh;box-sizing:border-box'>",
        unsafe_allow_html=True,
    )

    _prof = st.session_state.get("user_profile", {})

    st.markdown(
        "<h3 style='font-size:1.4rem;font-weight:800;letter-spacing:-.025em;"
        "color:#0F172A;margin:0 0 4px'>Your Profile</h3>"
        "<p style='font-size:.82rem;color:#94A3B8;margin:0 0 28px'>"
        "All fields optional — fill in what applies to you.</p>",
        unsafe_allow_html=True,
    )

    name = st.text_input("Name",
        value=_prof.get("name", ""),
        placeholder="e.g. Alex Chen")

    field_of_study = st.text_input("Field of Study / Program",
        value=_prof.get("field_of_study", ""),
        placeholder="e.g. Computer Science, Business Administration, Nursing…")

    EDUCATION_OPTIONS = [
        "Select…",
        "High School Diploma",
        "College Diploma (1–2 year)",
        "College Advanced Diploma (3 year)",
        "Bachelor's Degree",
        "Postgraduate Certificate",
        "Master's Degree",
        "Doctoral Degree",
        "Apprenticeship / Trades Certificate",
    ]
    _edu_idx = (EDUCATION_OPTIONS.index(_prof["education"])
                if _prof.get("education") in EDUCATION_OPTIONS else 0)
    education = st.selectbox("Education Level", EDUCATION_OPTIONS, index=_edu_idx)

    PROVINCES = [
        "Select…", "Canada (national)",
        "Alberta", "British Columbia", "Manitoba", "New Brunswick",
        "Newfoundland and Labrador", "Northwest Territories", "Nova Scotia",
        "Nunavut", "Ontario", "Prince Edward Island", "Quebec",
        "Saskatchewan", "Yukon",
    ]
    _prov_idx = (PROVINCES.index(_prof["province"])
                 if _prof.get("province") in PROVINCES else 0)
    province = st.selectbox("Province / Territory", PROVINCES, index=_prov_idx)

    STATUS_OPTIONS = [
        "Currently studying",
        "Recent graduate (within 2 years)",
        "Graduate (2+ years ago)",
        "Considering a career change",
    ]
    _status_idx = (STATUS_OPTIONS.index(_prof["study_status"])
                   if _prof.get("study_status") in STATUS_OPTIONS else 0)
    study_status = st.radio("Your current situation", STATUS_OPTIONS,
                            index=_status_idx, horizontal=False)

    st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)

    bc1, bc2, _ = st.columns([1.8, 1.2, 1])
    with bc1:
        if st.button("Continue to Career Explorer →", type="primary",
                     use_container_width=True):
            st.session_state["user_profile"] = {
                "name":           name.strip(),
                "field_of_study": field_of_study.strip(),
                "education":      education if education != "Select…" else "",
                "province":       province  if province  != "Select…" else "",
                "study_status":   study_status,
            }
            st.switch_page("pages/1_Career_Explorer.py")
    with bc2:
        if st.button("← Back to Home", use_container_width=True):
            st.switch_page("Home.py")

    st.markdown("</div>", unsafe_allow_html=True)

import streamlit as st

st.set_page_config(
    page_title="Career Explorer",
    page_icon="⬛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS (own call — no f-string needed) ──────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
section[data-testid="stMain"] > div,
.block-container {
    background: #0F172A !important;
    color: #F8FAFC;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    max-width: 100% !important;
}
/* Start button */
div[data-testid="stButton"] > button {
    font-family: 'Inter', sans-serif !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    border-radius: 8px !important;
    padding: 14px 0 !important;
    background: #F8FAFC !important;
    color: #0F172A !important;
    border: none !important;
    transition: all .2s ease !important;
    box-shadow: 0 4px 24px rgba(248,250,252,.18) !important;
}
div[data-testid="stButton"] > button:hover {
    background: #E2E8F0 !important;
    box-shadow: 0 8px 32px rgba(248,250,252,.24) !important;
}
</style>
""", unsafe_allow_html=True)

# ── Build steps HTML string ───────────────────────────────────
_STEPS = [
    ("01", "Your Profile",      "Field · Province · Level"),
    ("02", "Career Explorer",   "NOC · Wages · Skills"),
    ("03", "Holland Code Test", "RIASEC · AI Analysis"),
    ("04", "Competence Match",  "Gap Analysis · Advising"),
]
_cards = ""
for _n, _l, _s in _STEPS:
    _cards += (
        "<div style='flex:1;padding:14px 16px;"
        "border-right:1px solid rgba(255,255,255,.08);"
        "background:rgba(255,255,255,.03)'>"
        "<div style='font-size:.58rem;font-weight:500;letter-spacing:.12em;"
        "color:#475569;margin-bottom:5px'>" + _n + "</div>"
        "<div style='font-size:.8rem;font-weight:700;color:#CBD5E1;"
        "margin-bottom:2px'>" + _l + "</div>"
        "<div style='font-size:.68rem;color:#475569'>" + _s + "</div>"
        "</div>"
    )

# ── Hero HTML (separate call — plain string, no f-string) ─────
_hero = (
    "<div style='display:flex;flex-direction:column;align-items:center;"
    "padding:80px 24px 40px;box-sizing:border-box'>"

    # Badge
    "<div style='display:inline-flex;align-items:center;"
    "background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);"
    "border-radius:100px;padding:6px 18px;margin-bottom:44px'>"
    "<span style='font-size:.63rem;font-weight:500;letter-spacing:.14em;"
    "color:#94A3B8;text-transform:uppercase'>"
    "Canadian Labour Market · AI-Powered</span></div>"

    # Heading
    "<h1 style='font-size:clamp(3.2rem,8vw,6.5rem);font-weight:900;"
    "letter-spacing:-.045em;line-height:.95;color:#F8FAFC;"
    "text-align:center;margin:0 0 20px'>Career<br>Explorer</h1>"

    # Subtitle
    "<p style='font-size:clamp(.88rem,1.8vw,1.05rem);color:#64748B;"
    "text-align:center;max-width:480px;line-height:1.75;margin:0 0 56px'>"
    "Discover the right career path through your field of study, "
    "personal interests, and competency gap analysis — backed by "
    "Statistics Canada and Job Bank data.</p>"

    # Steps row
    "<div style='display:flex;border:1px solid rgba(255,255,255,.1);"
    "border-radius:10px;overflow:hidden;width:100%;max-width:640px;"
    "margin-bottom:52px'>"
    + _cards +
    "</div>"

    "</div>"
)
st.markdown(_hero, unsafe_allow_html=True)

# ── Start button ──────────────────────────────────────────────
_, btn_col, _ = st.columns([2.8, 1.6, 2.8])
with btn_col:
    if st.button("Get Started →", use_container_width=True):
        st.switch_page("pages/1_Career_Explorer.py")

# ── Footer ────────────────────────────────────────────────────
st.markdown(
    "<div style='text-align:center;padding:36px 0 28px;"
    "color:#334155;font-size:.7rem'>"
    "Data: Statistics Canada · Job Bank Canada · OaSIS &nbsp;·&nbsp; AI: Qwen3"
    "</div>",
    unsafe_allow_html=True,
)

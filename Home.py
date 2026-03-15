import streamlit as st

st.set_page_config(
    page_title="Career Explorer",
    page_icon="⬛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #0F172A;
    color: #F8FAFC;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding: 0 !important;
    max-width: 100% !important;
}

/* Primary button */
.stButton > button[kind="primary"] {
    font-family: 'Inter', sans-serif;
    font-weight: 700;
    font-size: 1rem;
    letter-spacing: .02em;
    border-radius: 8px;
    padding: 14px 40px;
    background: #F8FAFC;
    color: #0F172A;
    border: none;
    transition: all .2s ease;
    box-shadow: 0 4px 24px rgba(248,250,252,.15);
}
.stButton > button[kind="primary"]:hover {
    background: #E2E8F0;
    transform: translateY(-1px);
    box-shadow: 0 8px 32px rgba(248,250,252,.2);
}
</style>
""", unsafe_allow_html=True)

# ── Full-screen hero ──────────────────────────────────────────
st.markdown("""
<div style="
    min-height: 100vh;
    background: #0F172A;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 24px;
    box-sizing: border-box;
">
    <!-- Badge -->
    <div style="
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(255,255,255,.06);
        border: 1px solid rgba(255,255,255,.12);
        border-radius: 100px;
        padding: 6px 16px;
        margin-bottom: 40px;
    ">
        <span style="font-family:'JetBrains Mono',monospace;font-size:.65rem;
                     font-weight:500;letter-spacing:.14em;color:#94A3B8;
                     text-transform:uppercase">
            Canadian Labour Market · AI-Powered
        </span>
    </div>

    <!-- Main heading -->
    <h1 style="
        font-size: clamp(3rem, 8vw, 6rem);
        font-weight: 900;
        letter-spacing: -.04em;
        line-height: 1;
        color: #F8FAFC;
        text-align: center;
        margin: 0 0 16px;
    ">Career<br>Explorer</h1>

    <!-- Subtitle -->
    <p style="
        font-size: clamp(.95rem, 2vw, 1.15rem);
        font-weight: 400;
        color: #64748B;
        text-align: center;
        max-width: 520px;
        line-height: 1.7;
        margin: 0 0 56px;
    ">
        Discover the right career path through your field of study,
        personal interests, and competency gap analysis — backed by
        Statistics Canada and Job Bank data.
    </p>

    <!-- Steps row -->
    <div style="
        display: flex; gap: 0; margin-bottom: 56px;
        border: 1px solid rgba(255,255,255,.1);
        border-radius: 10px; overflow: hidden;
        width: 100%; max-width: 640px;
    ">
""", unsafe_allow_html=True)

for num, label, sub in [
    ("01", "Your Profile",       "Field · Province · Level"),
    ("02", "Career Explorer",    "NOC · Wages · Skills"),
    ("03", "Holland Code Test",  "RIASEC · AI Analysis"),
    ("04", "Competence Match",   "Gap Analysis · Advising"),
]:
    st.markdown(
        f"<div style='flex:1;padding:14px 16px;"
        f"border-right:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.03)'>"
        f"<div style='font-family:JetBrains Mono,monospace;font-size:.58rem;"
        f"font-weight:500;letter-spacing:.12em;color:#475569;margin-bottom:5px'>{num}</div>"
        f"<div style='font-size:.8rem;font-weight:700;color:#CBD5E1;margin-bottom:2px'>{label}</div>"
        f"<div style='font-size:.68rem;color:#475569'>{sub}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

st.markdown("</div>", unsafe_allow_html=True)

# ── Start button (centred) ────────────────────────────────────
_, btn_col, _ = st.columns([2.5, 2, 2.5])
with btn_col:
    if st.button("Get Started →", type="primary", use_container_width=True):
        st.switch_page("pages/0_User_Profile.py")

st.markdown("""
    <!-- Footer note -->
    <p style="margin-top:48px;font-size:.72rem;color:#334155;text-align:center">
        Data sources: Statistics Canada · Job Bank Canada · OaSIS &nbsp;·&nbsp;
        AI powered by Qwen3
    </p>
</div>
""", unsafe_allow_html=True)

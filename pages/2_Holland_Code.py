"""Holland Code Career Test — Streamlit app matching the local HTML design.

Run with:
    streamlit run holland_code_page.py
"""

from __future__ import annotations

import math
import re
import os
import time

import streamlit as st
import plotly.graph_objects as go

try:
    from openai import OpenAI as _OpenAI
    _HAS_OPENAI = True
except ImportError:
    _HAS_OPENAI = False

try:
    from oasis_client import fetch_oasis_matches, fetch_noc_unit_profile
    _HAS_OASIS = True
except Exception:
    _HAS_OASIS = False

# ── Page config ────────────────────────────────────────────────────
st.set_page_config(
    page_title="Holland Code Career Test",
    page_icon="⬛",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Global CSS — match local HTML design exactly ───────────────────
GLOBAL_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Hide Streamlit chrome ───────────────────────────── */
#MainMenu, footer, header { visibility: hidden !important; height: 0 !important; }
[data-testid="stToolbar"] { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }
[data-testid="stStatusWidget"] { display: none !important; }
.stDeployButton { display: none !important; }
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }

/* ── Base ─────────────────────────────────────────────── */
html, body, .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background: #FAFAFA !important;
    color: #111827 !important;
    -webkit-font-smoothing: antialiased;
}

/* ── Main container ───────────────────────────────────── */
.main .block-container {
    max-width: 720px !important;
    padding: 80px 24px 80px !important;
    margin: 0 auto !important;
}
@media (max-width: 600px) {
    .main .block-container { padding: 72px 16px 60px !important; }
}

/* ── Remove default element spacing ──────────────────── */
.stMarkdown p { margin: 0; }
div[data-testid="stVerticalBlock"] > div { gap: 0 !important; }

/* ── Primary button → black ───────────────────────────── */
.stButton > button[kind="primary"] {
    background: #111827 !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 13px 28px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,.18) !important;
    transition: all .18s ease !important;
    width: 100%;
}
.stButton > button[kind="primary"]:hover {
    background: #1F2937 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,.22) !important;
}

/* ── Secondary button → ghost ─────────────────────────── */
.stButton > button[kind="secondary"] {
    background: transparent !important;
    color: #6B7280 !important;
    border: 1.5px solid #E5E7EB !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    font-size: 0.9rem !important;
    padding: 13px 20px !important;
    transition: all .18s ease !important;
    width: 100%;
}
.stButton > button[kind="secondary"]:hover {
    background: #F9FAFB !important;
    color: #374151 !important;
    border-color: #D1D5DB !important;
}

/* ── Scale radio (5-option horizontal selector) ─────────── */
.stRadio,
.stRadio > div { margin-top: 0 !important; width: 100% !important; }
.stRadio [role="radiogroup"] {
    display: grid !important;
    grid-template-columns: repeat(5, 1fr) !important;
    gap: 6px !important;
    width: 100% !important;
    box-sizing: border-box !important;
}
.stRadio [role="radiogroup"] label {
    width: 100% !important;
    box-sizing: border-box !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-align: center !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 8px !important;
    padding: 10px 4px !important;
    margin: 0 !important;
    cursor: pointer !important;
    background: #fff !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.62rem !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
    transition: all .14s !important;
    overflow: hidden !important;
    position: relative !important;
}
/* Shrink the radio dot (keep input in DOM for clicks) */
.stRadio [role="radiogroup"] label > div:first-child {
    position: absolute !important;
    width: 1px !important;
    height: 1px !important;
    overflow: hidden !important;
    opacity: 0 !important;
}
/* Text container: fill width and center */
.stRadio [role="radiogroup"] label > div:last-child {
    width: 100% !important;
    text-align: center !important;
    font-size: 0.62rem !important;
    line-height: 1.25 !important;
}
/* Selected */
.stRadio [role="radiogroup"] label:has(input:checked) {
    background: #111827 !important;
    color: #fff !important;
    border-color: #111827 !important;
    font-weight: 600 !important;
}
.stRadio [role="radiogroup"] label:has(input:checked) p,
.stRadio [role="radiogroup"] label:has(input:checked) span,
.stRadio [role="radiogroup"] label:has(input:checked) div {
    color: #fff !important;
}
/* Hover (unselected) */
.stRadio [role="radiogroup"] label:not(:has(input:checked)):hover {
    background: #F9FAFB !important;
    color: #374151 !important;
    border-color: #D1D5DB !important;
}

/* ── Select / textarea ─────────────────────────────────── */
.stSelectbox > div > div,
.stTextArea > div > div > textarea {
    border: 1.5px solid #E5E7EB !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.88rem !important;
    background: #fff !important;
}
.stSelectbox > div > div:focus-within,
.stTextArea > div > div:focus-within { border-color: #6366F1 !important; }

/* ── Expander ──────────────────────────────────────────── */
[data-testid="stExpander"] {
    background: #fff !important;
    border: 1px solid #E5E7EB !important;
    border-radius: 16px !important;
    overflow: hidden !important;
}

/* ── Tabs ──────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px !important;
    background: #F3F4F6 !important;
    border-radius: 10px !important;
    padding: 4px !important;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    color: #6B7280 !important;
    background: transparent !important;
    padding: 8px 14px !important;
}
.stTabs [aria-selected="true"] {
    background: #fff !important;
    color: #111827 !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,.1) !important;
}

/* ── Spinner ───────────────────────────────────────────── */
.stSpinner { color: #111827 !important; }
</style>
"""
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

# ── Top navbar (injected HTML) ──────────────────────────────────────
NAVBAR = """
<style>
.hc-navbar {
    position: fixed; top: 0; left: 0; right: 0; z-index: 999;
    background: rgba(250,250,250,0.88);
    backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    border-bottom: 1px solid #E5E7EB;
    height: 56px;
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 24px;
}
.hc-navbar-brand {
    display: flex; align-items: center; gap: 10px;
    font-size: 0.9rem; font-weight: 600; color: #111827; letter-spacing: -0.01em;
}
.hc-navbar-tag {
    font-size: 0.72rem; font-weight: 500; color: #6B7280;
    background: #F3F4F6; border: 1px solid #E5E7EB;
    border-radius: 20px; padding: 3px 10px;
}
</style>
<div class="hc-navbar">
  <div class="hc-navbar-brand">
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#111827" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
      <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
    </svg>
    Holland Code
  </div>
  <span class="hc-navbar-tag">RIASEC Career Test</span>
</div>
"""
st.markdown(NAVBAR, unsafe_allow_html=True)

# ── Data ───────────────────────────────────────────────────────────
HOLLAND_TYPE_INFO = {
    "R": {"name":"Realistic",     "color":"#EF4444", "traits":"Practical, hands-on, physical, mechanical, tool-oriented", "description":"You prefer working with things — tools, machines, plants, or animals. You value practical, tangible results.", "careers":"Mechanic, Electrician, Engineer, Pilot, Carpenter, Forestry Technician"},
    "I": {"name":"Investigative", "color":"#3B82F6", "traits":"Analytical, curious, intellectual, scientific, methodical",  "description":"You enjoy researching, analyzing, and solving complex problems. You thrive on learning and discovery.",       "careers":"Scientist, Researcher, Doctor, Data Analyst, Economist, Pharmacist"},
    "A": {"name":"Artistic",      "color":"#A855F7", "traits":"Creative, expressive, original, imaginative, independent",  "description":"You value self-expression and creativity. You prefer unstructured environments where you can innovate.",    "careers":"Designer, Writer, Musician, Actor, Photographer, Art Director"},
    "S": {"name":"Social",        "color":"#10B981", "traits":"Helpful, empathetic, cooperative, patient, supportive",     "description":"You enjoy helping, teaching, counselling, and serving others. You are drawn to roles that make a difference.", "careers":"Teacher, Counsellor, Nurse, Social Worker, Therapist, HR Specialist"},
    "E": {"name":"Enterprising",  "color":"#F59E0B", "traits":"Ambitious, energetic, persuasive, competitive, confident",  "description":"You like leading, persuading, and managing. You enjoy taking risks and making things happen.",             "careers":"Manager, Entrepreneur, Sales Director, Lawyer, Real Estate Agent, Marketing Executive"},
    "C": {"name":"Conventional",  "color":"#6366F1", "traits":"Organized, detail-oriented, systematic, efficient, reliable","description":"You prefer structured environments with clear rules. You excel at organizing data and following procedures.", "careers":"Accountant, Auditor, Administrative Assistant, Bank Teller, Bookkeeper, Tax Preparer"},
}

RIASEC_ORDER = ["R","I","A","S","E","C"]

HOLLAND_QUESTIONS = {
    "R":["Test the quality of parts before shipment","Lay brick or tile","Work on an offshore oil-drilling rig","Assemble electronic parts","Operate a grinding machine in a factory","Fix a broken faucet","Assemble products in a factory","Install flooring in houses"],
    "I":["Study the structure of the human body","Study animal behavior","Do research on plants or animals","Develop a new medical treatment or procedure","Conduct biological research","Study whales and other types of marine life","Work in a biology lab","Make a map of the bottom of an ocean"],
    "A":["Conduct a musical choir","Direct a play","Design artwork for magazines","Write a song","Write books or plays","Play a musical instrument","Perform stunts for a movie or television show","Design sets for plays"],
    "S":["Give career guidance to people","Do volunteer work at a non-profit organization","Help people who have problems with drugs or alcohol","Teach an individual an exercise routine","Help people with family-related problems","Supervise the activities of children at a camp","Teach children how to read","Help elderly people with their daily activities"],
    "E":["Sell restaurant franchises to individuals","Sell merchandise at a department store","Manage the operations of a hotel","Operate a beauty salon or barber shop","Manage a department within a large company","Manage a clothing store","Sell houses","Run a toy store"],
    "C":["Generate the monthly payroll checks for an office","Inventory supplies using a hand-held computer","Use a computer program to generate customer bills","Maintain employee records","Compute and record statistical and other numerical data","Operate a calculator","Handle customers bank transactions","Keep shipping and receiving records"],
}

SCALE_LABELS = ["1 – Dislike","2 – Slightly","3 – Neutral","4 – Somewhat","5 – Enjoy"]

_TYPE_NAMES = {"R":"Realistic","I":"Investigative","A":"Artistic","S":"Social","E":"Enterprising","C":"Conventional"}

_ADJACENT_PAIRS = {frozenset(("R","I")),frozenset(("I","A")),frozenset(("A","S")),frozenset(("S","E")),frozenset(("E","C")),frozenset(("C","R"))}
_OPPOSITE_PAIRS = {frozenset(("R","S")),frozenset(("I","E")),frozenset(("A","C"))}
_HEX_ANGLES = {"R":-90,"I":-30,"A":30,"S":90,"E":150,"C":210}

_DIMENSION_DETAILS = {
    "R":{"tasks":"Operating tools, machinery, and equipment; outdoor physical work; hands-on repair and construction","env":"Factories, construction sites, labs, outdoors — emphasis on tangible, physical work","behavior":"Prefers concrete tasks with visible outcomes; values efficiency and practicality"},
    "I":{"tasks":"Research, analysis, experimentation, data interpretation, theoretical modelling","env":"Laboratories, research institutions, academia — emphasis on independent thinking and deep inquiry","behavior":"Highly curious; enjoys asking questions and solving complex problems; values evidence and logic"},
    "A":{"tasks":"Creative work, design, performance, writing, and visual arts","env":"Studios, theatres, design firms, freelance settings — emphasis on autonomy and creative freedom","behavior":"Pursues originality and aesthetic expression; dislikes repetitive rules; values personal voice"},
    "S":{"tasks":"Teaching, counselling, nursing, social services, and team collaboration","env":"Schools, hospitals, community organizations, non-profits — emphasis on human connection","behavior":"Attuned to others' needs; skilled at listening and communication; values cooperation"},
    "E":{"tasks":"Managing, selling, negotiating, entrepreneurship, and project leadership","env":"Companies, sales teams, executive roles, start-ups — emphasis on influence and results","behavior":"Enjoys leading and persuading; willing to take risks; pursues achievement and status"},
    "C":{"tasks":"Data entry, file management, financial accounting, and process execution","env":"Offices, financial institutions, administrative departments — emphasis on order and procedure","behavior":"Detail-oriented and precise; prefers structured, rule-governed work styles"},
}

_SYSTEM_PROMPT = """You are a rigorous Holland Code / RIASEC career interest assessment interpreter with deep expertise in the Canadian NOC (National Occupational Classification) system. Your task is not to predict destiny, but to clearly explain the interest structure and provide verifiable, actionable exploration suggestions grounded in real career data.

Global constraints:
1. Interest ≠ ability. Never make deterministic judgements.
2. Do not merely list job titles — explain core tasks, work environment, daily activities, and why each career fits the user's specific interest structure.
3. When scores are close, explicitly flag the uncertainty and note what needs further validation.
4. Language must be professional, clear, and measured. Avoid generic encouragement or filler phrases.
5. Output entirely in English.
6. Do not include any internal reasoning or thinking process — output only the final report.
7. Each layer must be detailed, specific, and substantive. Avoid vague generalisations.
8. All career direction discussions must draw on the provided NOC occupation data."""

# ── SVG icons ──────────────────────────────────────────────────────
_SVGS = {
    "R":'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    "I":'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    "A":'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    "S":'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "E":'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
    "C":'<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="9" x2="9" y2="21"/><line x1="15" y1="9" x2="15" y2="21"/></svg>',
}

def _icon(letter, size=24, color=None):
    c = color or HOLLAND_TYPE_INFO[letter]["color"]
    return _SVGS[letter].format(s=size, c=c)

# ── Helpers ────────────────────────────────────────────────────────
def _scroll_top():
    st.components.v1.html("<script>window.parent.document.querySelector('section.main').scrollTo(0,0);</script>", height=0)

def _spacer(px=16):
    st.markdown(f'<div style="height:{px}px"></div>', unsafe_allow_html=True)

def _eyebrow(text):
    st.markdown(f'<div style="font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin-bottom:10px">{text}</div>', unsafe_allow_html=True)

def _footer():
    st.markdown('<div style="text-align:center;font-size:.75rem;color:#9CA3AF;padding-top:24px;margin-top:20px;border-top:1px solid #F3F4F6">Holland Code Career Test &nbsp;·&nbsp; RIASEC Model &nbsp;·&nbsp; For reference purposes only</div>', unsafe_allow_html=True)

def _progress_dots(step):
    dots_html = '<div style="display:flex;align-items:center;gap:6px;margin-bottom:12px">'
    for i in range(6):
        if i < step - 1:
            bg = "#111827"
        elif i == step - 1:
            bg = "#6B7280"
        else:
            bg = "#E5E7EB"
        dots_html += f'<div style="height:4px;flex:1;border-radius:2px;background:{bg};transition:background .35s"></div>'
    dots_html += '</div>'
    step_names = {1:"Realistic",2:"Investigative",3:"Artistic",4:"Social",5:"Enterprising",6:"Conventional"}
    dots_html += f'<div style="display:flex;justify-content:space-between;font-size:.78rem;color:#9CA3AF;font-weight:500;margin-bottom:28px"><span style="color:#374151;font-weight:600">{step_names[step]}</span><span>Step {step} of 6</span></div>'
    st.markdown(dots_html, unsafe_allow_html=True)

# ── Rule engine ────────────────────────────────────────────────────
def _compute_rule_outputs(scores):
    ranked = sorted(RIASEC_ORDER, key=lambda t: scores[t], reverse=True)
    top3 = ranked[:3]
    gap_12 = scores[ranked[0]] - scores[ranked[1]]
    gap_23 = scores[ranked[1]] - scores[ranked[2]]
    gap_top3 = scores[ranked[0]] - scores[ranked[2]]
    gap_hl = scores[ranked[0]] - scores[ranked[5]]
    if gap_12 >= 1.0 and gap_top3 >= 1.5:
        stype, sdesc = "Concentrated", "Primary interest is highly prominent; career direction is relatively clear"
    elif gap_top3 <= 0.6:
        stype, sdesc = "Balanced", "Top three scores are very close, indicating broad and exploratory interests"
    elif gap_12 <= 0.3 and gap_23 >= 0.8:
        stype, sdesc = "Dual-Core", "First two scores are close and both prominent — two equally strong interest anchors"
    elif gap_hl <= 1.0:
        stype, sdesc = "Dispersed", "Scores are relatively uniform; interests not yet clearly differentiated"
    else:
        stype, sdesc = "Gradient", "Interests show a gradual decreasing pattern from primary to lower-ranked types"
    complements, tensions = [], []
    for i in range(len(top3)):
        for j in range(i+1, len(top3)):
            pair = frozenset((top3[i], top3[j]))
            if pair in _ADJACENT_PAIRS:
                complements.append(f"{_TYPE_NAMES[top3[i]]} and {_TYPE_NAMES[top3[j]]} are adjacent — mutually reinforcing")
            elif pair in _OPPOSITE_PAIRS:
                tensions.append(f"{_TYPE_NAMES[top3[i]]} and {_TYPE_NAMES[top3[j]]} are opposites — potential internal tension")
    certainties, uncertainties = [], []
    if gap_12 >= 1.0:
        certainties.append(f"Primary interest ({_TYPE_NAMES[ranked[0]]}) is clearly dominant")
    else:
        uncertainties.append(f"Gap between 1st and 2nd is small ({gap_12:.1f}); needs further validation")
    if gap_23 <= 0.3:
        uncertainties.append(f"2nd and 3rd interests are very close ({gap_23:.1f}); ranking may shift by context")
    else:
        certainties.append("Top-3 code ordering is relatively stable")
    return {
        "sorted_types":[{"type":t,"name":_TYPE_NAMES[t],"score":round(scores[t],2)} for t in ranked],
        "top3":top3,"top3_names":[_TYPE_NAMES[t] for t in top3],
        "gaps":{"gap_1_2":round(gap_12,2),"gap_2_3":round(gap_23,2),"gap_top3_max":round(gap_top3,2),"gap_high_low":round(gap_hl,2)},
        "structure_type":stype,"structure_desc":sdesc,
        "complements":complements,"tensions":tensions,"certainties":certainties,"uncertainties":uncertainties,
    }

def _build_prompt(scores, rule, noc_data, stage, scenario, background):
    scores_str = " / ".join(f"{_TYPE_NAMES[t]}={scores[t]:.2f}" for t in RIASEC_ORDER)
    top3_str = "".join(rule["top3"])
    dim_block = ""
    for t in RIASEC_ORDER:
        d = _DIMENSION_DETAILS[t]
        dim_block += f"  - {_TYPE_NAMES[t]}: tasks={d['tasks']}; env={d['env']}; behavior={d['behavior']}\n"
    noc_block = ""
    if noc_data and noc_data.get("success") and noc_data.get("matches"):
        noc_block = f"\n[OaSIS Matched NOC Occupations]\nTop-3 code {top3_str}:\n\n"
        for i,m in enumerate(noc_data["matches"],1):
            code,title = m["code"],m["title"]
            noc_block += f"{i}. NOC {code} — {title}\n"
            desc = noc_data.get("descriptions",{}).get(code)
            if desc:
                if desc.get("example_titles"): noc_block += f"   Titles: {', '.join(desc['example_titles'])}\n"
                if desc.get("main_duties"):
                    noc_block += "   Duties:\n"
                    for d2 in desc["main_duties"]: noc_block += f"     - {d2}\n"
            noc_block += "\n"
    else:
        noc_block = "\n[NOC Data]\nNo occupation data. Provide general Holland Code career analysis.\n"
    return f"""Generate a five-layer deep interpretation report.

[Data]
- Scores (out of 5.0): {scores_str}
- Top-3 code: {top3_str}
- Stage: {stage}
- Context: {scenario}
- Background: {background or 'None'}

[Dimensions]
{dim_block}
[Rule Analysis]
- Ranking: {' > '.join(f"{d['name']}({d['score']})" for d in rule['sorted_types'])}
- Gaps: 1st–2nd={rule['gaps']['gap_1_2']}, 2nd–3rd={rule['gaps']['gap_2_3']}, H–L={rule['gaps']['gap_high_low']}
- Structure: {rule['structure_type']} — {rule['structure_desc']}
- Complements: {'; '.join(rule['complements']) or 'None'}
- Tensions: {'; '.join(rule['tensions']) or 'None'}
{noc_block}
Use ## Layer N: headings. Be detailed and substantive.

## Layer 1: Six Dimensions Explained
For each of 6 types, explain score meaning, task preferences, environment, behavioural patterns. High scorers: 3-5 sentences. End with synthesising paragraph.

## Layer 2: Top-3 Code Combination
Overall portrait of the combination. Role of each (Primary/Secondary/Tertiary). 2-3 activating situations. 4-8 career directions with NOC data.

## Layer 3: Score Structure & Gap Analysis
Explain structure type with actual numbers. List certainties and uncertainties. Impact on major selection, career strategy, decision timeline.

## Layer 4: Consistency & Internal Tensions
Hexagon positional analysis. Complementary relationships with concrete examples. Tension dynamics and positive innovation potential. 3-4 environment-design recommendations.

## Layer 5: Career Mapping & Action Plan
### Best Fit (High Alignment): 3-5 directions with NOC code, duties, fit explanation, study paths
### Worth Exploring: 2-3 directions with potential analysis
### Too Early to Commit: 1-2 directions
### 30-90 Day Plan: Days 1-30 / 31-60 / 61-90 with 3 actions each
### 3 Mini-Experiments: goal, steps, expected outcome, success criterion"""

def _get_api_config():
    try:
        base_url = st.secrets.get("QWEN_BASE_URL","http://113.108.105.54:3000/v1")
        api_key  = st.secrets.get("QWEN_API_KEY","9e7d5b627e4ac73da50e5c1182a81b02bd43e34e16992c49b0ccc968ae4ad9b2")
    except Exception:
        base_url = os.environ.get("QWEN_BASE_URL","http://113.108.105.54:3000/v1")
        api_key  = os.environ.get("QWEN_API_KEY","9e7d5b627e4ac73da50e5c1182a81b02bd43e34e16992c49b0ccc968ae4ad9b2")
    return base_url, api_key

def _qwen_stream(scores, rule, noc_data, stage, scenario, background):
    base_url, api_key = _get_api_config()
    client = _OpenAI(base_url=base_url, api_key=api_key)
    prompt = _build_prompt(scores, rule, noc_data, stage, scenario, background)
    stream = client.chat.completions.create(
        model="Qwen/Qwen3-32B", max_tokens=8000, stream=True,
        messages=[{"role":"system","content":_SYSTEM_PROMPT},{"role":"user","content":prompt}],
        extra_body={"chat_template_kwargs":{"enable_thinking":False}},
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

def _parse_layers(text):
    parts = re.split(r'(?=##\s*Layer\s*\d)', text, flags=re.IGNORECASE)
    layers = [""] * 5
    for i in range(5):
        m = next((p for p in parts if re.match(rf'##\s*Layer\s*{i+1}', p, re.IGNORECASE)), None)
        if m: layers[i] = m.strip()
    return layers

def _hex_pt(letter, radius, cx, cy):
    rad = math.radians(_HEX_ANGLES[letter])
    return cx + radius*math.cos(rad), cy + radius*math.sin(rad)

def _build_hex_svg(size, top3, scores, show_labels=False):
    cx = cy = size/2; R = size*0.36
    hex_pts = " ".join(f"{_hex_pt(t,R,cx,cy)[0]:.1f},{_hex_pt(t,R,cx,cy)[1]:.1f}" for t in RIASEC_ORDER)
    score_pts = " ".join(f"{_hex_pt(t,R*min(scores.get(t,0),5)/5,cx,cy)[0]:.1f},{_hex_pt(t,R*min(scores.get(t,0),5)/5,cx,cy)[1]:.1f}" for t in RIASEC_ORDER)
    lines = ""
    for i in range(len(top3)):
        for j in range(i+1,len(top3)):
            a,b=top3[i],top3[j]; x1,y1=_hex_pt(a,R,cx,cy); x2,y2=_hex_pt(b,R,cx,cy)
            pair=frozenset((a,b))
            if pair in _ADJACENT_PAIRS: lines+=f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#10B981" stroke-width="2" stroke-opacity="0.7"/>'
            elif pair in _OPPOSITE_PAIRS: lines+=f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#F59E0B" stroke-width="1.5" stroke-dasharray="4,3" stroke-opacity="0.8"/>'
            else: lines+=f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#9CA3AF" stroke-width="1" stroke-opacity="0.4"/>'
    nodes=""
    for t in RIASEC_ORDER:
        x,y=_hex_pt(t,R,cx,cy); is_top=t in top3; color=HOLLAND_TYPE_INFO[t]["color"]; r_dot=11 if is_top else 6
        nodes+=f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r_dot}" fill="{color if is_top else "#E5E7EB"}" stroke="{(color+"50") if is_top else "#D1D5DB"}" stroke-width="2"/>'
        if is_top: nodes+=f'<text x="{x:.1f}" y="{y+1:.1f}" text-anchor="middle" dominant-baseline="middle" fill="white" font-size="9" font-weight="700" font-family="Inter,sans-serif">{t}</text>'
        if show_labels:
            lx,ly=_hex_pt(t,R+22,cx,cy); fc=color if is_top else "#9CA3AF"; fw="700" if is_top else "500"; fs=10 if is_top else 9
            nodes+=f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="{fc}" font-size="{fs}" font-weight="{fw}" font-family="Inter,sans-serif">{HOLLAND_TYPE_INFO[t]["name"]}</text>'
    return (f'<div style="display:flex;justify-content:center">'
            f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">'
            f'<polygon points="{hex_pts}" fill="none" stroke="#E5E7EB" stroke-width="1.5"/>'
            f'<polygon points="{score_pts}" fill="rgba(99,102,241,0.08)" stroke="#6366F1" stroke-width="1.5" stroke-opacity="0.6"/>'
            f'{lines}{nodes}</svg></div>')

def _radar_chart(scores):
    names = [HOLLAND_TYPE_INFO[t]["name"] for t in RIASEC_ORDER]
    vals  = [scores[t] for t in RIASEC_ORDER]
    fig = go.Figure(go.Scatterpolar(
        r=vals+[vals[0]], theta=names+[names[0]], fill="toself",
        fillcolor="rgba(17,24,39,0.05)",
        line=dict(color="#111827", width=2),
        marker=dict(size=8, color=[HOLLAND_TYPE_INFO[t]["color"] for t in RIASEC_ORDER]+[HOLLAND_TYPE_INFO["R"]["color"]], line=dict(width=2,color="white")),
        hovertemplate="%{theta}: %{r:.1f}/5<extra></extra>",
    ))
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter,sans-serif", size=12, color="#374151"),
        margin=dict(l=40,r=40,t=20,b=20), height=400,
        polar=dict(
            radialaxis=dict(visible=True,range=[0,5],gridcolor="rgba(229,231,235,0.8)",tickvals=[1,2,3,4,5],tickfont=dict(size=10,color="#D1D5DB"),tickmode="array"),
            angularaxis=dict(gridcolor="rgba(229,231,235,0.8)"),
            bgcolor="rgba(0,0,0,0)",
        ),
    )
    return fig

# ── Scale selector widget ───────────────────────────────────────────
def _scale_selector(key, q_num, question):
    """Render a question card with a horizontal radio scale."""
    # Initialize default
    if f"_ans_{key}" not in st.session_state:
        st.session_state[f"_ans_{key}"] = 3
    # Question label
    st.markdown(
        f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:14px;overflow:hidden;margin-bottom:10px">'
        f'<div style="padding:14px 18px 13px;font-size:1rem;font-weight:500;color:#111827;line-height:1.55;'
        f'display:flex;align-items:flex-start;gap:12px;border-bottom:1px solid #F3F4F6">'
        f'<span style="display:inline-flex;align-items:center;justify-content:center;min-width:20px;height:20px;'
        f'border-radius:5px;background:#F3F4F6;color:#6B7280;font-size:.68rem;font-weight:700;flex-shrink:0">{q_num}</span>'
        f'{question}</div></div>',
        unsafe_allow_html=True,
    )
    st.radio(
        label="",
        options=[1, 2, 3, 4, 5],
        format_func=lambda x: SCALE_LABELS[x - 1],
        horizontal=True,
        key=f"_ans_{key}",
        label_visibility="collapsed",
    )

# ── Landing page ───────────────────────────────────────────────────
def _render_landing():
    _scroll_top()

    # Hero
    st.markdown(
        '<div style="padding:16px 0 48px">'
        '<div style="width:52px;height:52px;background:#111827;border-radius:14px;display:flex;align-items:center;justify-content:center;margin-bottom:24px">'
        '<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>'
        '</div>'
        '<div style="font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin-bottom:10px">Career Personality Assessment</div>'
        '<h1 style="font-size:2.4rem;font-weight:700;color:#111827;letter-spacing:-.04em;line-height:1.15;margin-bottom:14px">Discover Your<br>Holland Code</h1>'
        '<p style="font-size:1rem;color:#6B7280;max-width:500px;line-height:1.7;margin-bottom:32px">Find career paths that align with your natural interests and strengths through the RIASEC personality framework.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        if st.button("Begin Assessment", type="primary", use_container_width=True, key="land_start"):
            st.session_state["_step"] = 1
            st.session_state["_answers"] = {}
            st.rerun()

    st.markdown(
        '<div style="display:flex;align-items:center;gap:20px;margin-top:20px;margin-bottom:48px">'
        '<span style="display:flex;align-items:center;gap:7px;font-size:.82rem;color:#9CA3AF;font-weight:500">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>48 questions</span>'
        '<span style="display:flex;align-items:center;gap:7px;font-size:.82rem;color:#9CA3AF;font-weight:500">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>~5 minutes</span>'
        '<span style="display:flex;align-items:center;gap:7px;font-size:.82rem;color:#9CA3AF;font-weight:500">'
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/></svg>No sign-up</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # Type grid
    st.markdown('<div style="font-size:.75rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:#9CA3AF;margin-bottom:16px">Six Personality Types</div>', unsafe_allow_html=True)
    cols = st.columns(3, gap="small")
    for idx, t in enumerate(RIASEC_ORDER):
        info = HOLLAND_TYPE_INFO[t]
        with cols[idx % 3]:
            traits_short = ", ".join(info["traits"].split(", ")[:3])
            st.markdown(
                f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:14px;padding:20px 16px 16px;margin-bottom:10px;transition:box-shadow .2s">'
                f'<div style="width:38px;height:38px;border-radius:10px;background:{info["color"]}12;display:flex;align-items:center;justify-content:center;margin-bottom:12px">{_icon(t,20,info["color"])}</div>'
                f'<div style="font-size:.78rem;font-weight:700;color:{info["color"]};letter-spacing:.04em;margin-bottom:2px">{t}</div>'
                f'<div style="font-size:.88rem;font-weight:600;color:#111827;margin-bottom:6px">{info["name"]}</div>'
                f'<div style="font-size:.72rem;color:#9CA3AF;line-height:1.45">{traits_short}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    _footer()

# ── Quiz page ──────────────────────────────────────────────────────
def _render_quiz(step):
    _scroll_top()
    t = RIASEC_ORDER[step-1]
    info = HOLLAND_TYPE_INFO[t]
    qs = HOLLAND_QUESTIONS[t]

    _progress_dots(step)

    # Quiz hero card
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:18px;margin-bottom:28px;padding:22px 24px;background:#fff;border:1px solid #E5E7EB;border-radius:16px">'
        f'<div style="width:52px;height:52px;border-radius:14px;background:{info["color"]}12;display:flex;align-items:center;justify-content:center;flex-shrink:0">{_icon(t,26,info["color"])}</div>'
        f'<div><div style="font-size:1.2rem;font-weight:700;color:#111827;letter-spacing:-.02em">{info["name"]}</div>'
        f'<div style="font-size:.83rem;color:#9CA3AF;margin-top:3px">Rate how much you\'d enjoy each activity — 1 (Dislike) to 5 (Enjoy)</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Questions with custom scale
    answers = st.session_state.get("_answers", {})
    for i, q in enumerate(qs):
        key = f"{t}_{i}"
        if f"_ans_{key}" not in st.session_state:
            st.session_state[f"_ans_{key}"] = answers.get(key, 3)
        q_num = (step-1)*8 + i + 1
        _scale_selector(key, q_num, q)
        _spacer(2)

    _spacer(8)
    col_back, col_next = st.columns(2, gap="small")
    with col_back:
        label = "← Back" if step > 1 else "← Home"
        if st.button(label, use_container_width=True, key="q_back"):
            if step > 1:
                st.session_state["_step"] = step - 1
            else:
                st.session_state["_step"] = 0
                st.session_state["_answers"] = {}
            st.rerun()
    with col_next:
        label = "View Results →" if step == 6 else "Continue →"
        if st.button(label, type="primary", use_container_width=True, key="q_next"):
            # Save answers
            ans = st.session_state.get("_answers", {})
            for i in range(8):
                k = f"{t}_{i}"
                ans[k] = st.session_state.get(f"_ans_{k}", 3)
            st.session_state["_answers"] = ans
            if step < 6:
                st.session_state["_step"] = step + 1
            else:
                st.session_state["_step"] = 7
            st.rerun()

# ── Results page ───────────────────────────────────────────────────
def _render_results():
    _scroll_top()
    answers = st.session_state.get("_answers", {})
    scores = {}
    for t in RIASEC_ORDER:
        vals = [answers.get(f"{t}_{i}", 3) for i in range(8)]
        scores[t] = sum(vals)/len(vals)
    ranked = sorted(RIASEC_ORDER, key=lambda t: scores[t], reverse=True)
    top3 = ranked[:3]
    code = "".join(top3)
    st.session_state["_scores"] = scores
    st.session_state["_top3"] = top3

    # Hero
    st.markdown(
        f'<div style="padding:8px 0 32px">'
        f'<div style="font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#6B7280;margin-bottom:10px">Your Results</div>'
        f'<h1 style="font-size:2rem;font-weight:700;letter-spacing:-.03em;color:#111827;margin-bottom:6px">Holland Code: <span style="letter-spacing:.05em">{code}</span></h1>'
        f'<p style="font-size:.9rem;color:#9CA3AF">Based on your responses across 48 activities</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Code chips
    chips_html = '<div style="background:#fff;border:1px solid #E5E7EB;border-radius:20px;padding:28px 24px;margin-bottom:28px;text-align:center"><div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin-bottom:20px">Your Personality Code</div><div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap">'
    for t in top3:
        info = HOLLAND_TYPE_INFO[t]
        chips_html += (f'<div style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:18px 22px;border-radius:16px;min-width:88px;background:{info["color"]}0d;border:1.5px solid {info["color"]}35">'
                       f'{_icon(t,24,info["color"])}'
                       f'<div style="font-size:1.6rem;font-weight:700;color:{info["color"]};line-height:1">{t}</div>'
                       f'<div style="font-size:.7rem;font-weight:600;color:#9CA3AF">{info["name"]}</div>'
                       f'</div>')
    chips_html += '</div></div>'
    st.markdown(chips_html, unsafe_allow_html=True)

    # Radar chart
    st.markdown('<div style="background:#fff;border:1px solid #E5E7EB;border-radius:20px;padding:24px;margin-bottom:28px">', unsafe_allow_html=True)
    st.plotly_chart(_radar_chart(scores), use_container_width=True, config={"displayModeBar":False})
    st.markdown('</div>', unsafe_allow_html=True)

    # Deep Analysis CTA
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1e1b4b 0%,#312e81 100%);border-radius:20px;padding:28px;margin-bottom:28px;color:#fff">'
        '<div style="font-size:1.1rem;font-weight:700;margin-bottom:8px">Ready for Deep Analysis?</div>'
        '<div style="font-size:.83rem;opacity:.75;line-height:1.6;margin-bottom:20px">Get a 5-layer AI-powered interpretation — dimensions, code identity, score structure, internal tensions, and career mapping grounded in real NOC data.</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    col_d1, col_d2, col_d3 = st.columns([1,2,1])
    with col_d2:
        if st.button("Deep Analysis →", type="primary", use_container_width=True, key="r_deep"):
            for k in ["_rule","_oasis","_ai_layers","_ai_gen","_ctx_stage","_ctx_scenario","_ctx_bg"]:
                st.session_state.pop(k, None)
            st.session_state["_step"] = 8
            st.rerun()

    # Top 3 cards
    st.markdown('<div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin:8px 0 14px">Your Top 3 Types</div>', unsafe_allow_html=True)
    for rank, t in enumerate(top3, 1):
        info = HOLLAND_TYPE_INFO[t]
        traits_list = "".join(f'<span style="font-size:.71rem;font-weight:500;color:#6B7280;background:#F9FAFB;border:1px solid #E5E7EB;border-radius:6px;padding:3px 9px;margin:2px">{tr.strip()}</span>' for tr in info["traits"].split(","))
        st.markdown(
            f'<div style="background:#fff;border:1px solid #E5E7EB;border-left:3px solid {info["color"]};border-radius:16px;padding:22px;margin-bottom:12px">'
            f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:12px">'
            f'<div style="width:44px;height:44px;border-radius:12px;background:{info["color"]}12;display:flex;align-items:center;justify-content:center;flex-shrink:0">{_icon(t,22,info["color"])}</div>'
            f'<div><div style="font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:{info["color"]}">#{rank} Match</div>'
            f'<div style="font-size:1rem;font-weight:700;color:#111827">{info["name"]}</div></div>'
            f'<div style="font-size:1.15rem;font-weight:700;color:{info["color"]};margin-left:auto">{scores[t]:.1f}<span style="font-size:.73rem;font-weight:400;color:#9CA3AF">/5</span></div>'
            f'</div>'
            f'<div style="font-size:.845rem;color:#4B5563;line-height:1.65;margin-bottom:10px">{info["description"]}</div>'
            f'<div style="display:flex;flex-wrap:wrap;gap:6px">{traits_list}</div>'
            f'<div style="margin-top:10px;font-size:.78rem;color:#9CA3AF"><strong style="color:#6B7280">Careers:</strong> {info["careers"]}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Score breakdown
    with st.expander("All Six Scores"):
        for t in RIASEC_ORDER:
            info = HOLLAND_TYPE_INFO[t]; pct = int((scores[t]/5)*100)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #F9FAFB">'
                f'<div style="width:28px;height:28px;border-radius:7px;background:{info["color"]}10;display:flex;align-items:center;justify-content:center">{_icon(t,14,info["color"])}</div>'
                f'<div style="font-size:.82rem;font-weight:600;color:#374151;min-width:105px">{info["name"]}</div>'
                f'<div style="flex:1;height:5px;background:#F3F4F6;border-radius:3px;overflow:hidden"><div style="width:{pct}%;height:100%;background:{info["color"]};border-radius:3px"></div></div>'
                f'<div style="font-size:.82rem;font-weight:700;color:{info["color"]};min-width:32px;text-align:right">{scores[t]:.1f}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    _spacer(16)
    col_ret, _ = st.columns(2)
    with col_ret:
        if st.button("↺  Retake Test", use_container_width=True, key="r_retake"):
            st.session_state["_step"] = 0
            st.session_state["_answers"] = {}
            st.rerun()
    _footer()

# ── Context page (step 8) ─────────────────────────────────────────
def _render_context():
    _scroll_top()
    st.markdown(
        '<div style="padding:8px 0 28px">'
        '<div style="font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin-bottom:10px">Deep Analysis</div>'
        '<h1 style="font-size:1.85rem;font-weight:700;color:#111827;letter-spacing:-.03em;line-height:1.25;margin-bottom:10px">Personalise Your Report</h1>'
        '<p style="font-size:.95rem;color:#6B7280;line-height:1.65">Help the AI tailor the analysis to your situation.</p>'
        '</div>',
        unsafe_allow_html=True,
    )

    stage_opts = ["High School","University / Post-secondary","Early Career (0–3 yrs)","Mid Career (3–10 yrs)","Career Transition","Other"]
    saved_stage = st.session_state.get("_ctx_stage","University / Post-secondary")
    stage = st.selectbox("Current Stage", stage_opts, index=stage_opts.index(saved_stage) if saved_stage in stage_opts else 1)
    st.session_state["_ctx_stage"] = stage

    scen_opts = ["Career Exploration","Major / Programme Selection","Job Search","Career Change","Graduate School Planning","Personal Development"]
    saved_scen = st.session_state.get("_ctx_scenario","Career Exploration")
    scenario = st.radio("Application Context", scen_opts, index=scen_opts.index(saved_scen) if saved_scen in scen_opts else 0)
    st.session_state["_ctx_scenario"] = scenario

    background = st.text_area(
        "Background (optional)",
        value=st.session_state.get("_ctx_bg",""),
        placeholder="Current major, relevant experience, or specific questions…",
        height=100,
    )
    st.session_state["_ctx_bg"] = background

    _spacer(16)
    col_back, col_go = st.columns(2)
    with col_back:
        if st.button("← Back to Results", use_container_width=True, key="ctx_back"):
            st.session_state["_step"] = 7; st.rerun()
    with col_go:
        if st.button("Start Analysis →", type="primary", use_container_width=True, key="ctx_go"):
            st.session_state["_step"] = 9; st.rerun()

# ── Analysis page (step 9) ────────────────────────────────────────
def _render_analysis():
    _scroll_top()
    scores = st.session_state.get("_scores", {})
    top3   = st.session_state.get("_top3", [])
    stage      = st.session_state.get("_ctx_stage","University / Post-secondary")
    scenario   = st.session_state.get("_ctx_scenario","Career Exploration")
    background = st.session_state.get("_ctx_bg","")

    if not scores:
        st.error("No data found. Please complete the test first.")
        if st.button("← Go to Test"): st.session_state["_step"]=0; st.rerun()
        return

    if "_rule" not in st.session_state:
        st.session_state["_rule"] = _compute_rule_outputs(scores)
    rule = st.session_state["_rule"]

    if "_oasis" not in st.session_state:
        with st.spinner("Fetching occupation data…"):
            if _HAS_OASIS and top3:
                names = [_TYPE_NAMES[t] for t in top3]
                try:
                    oasis = fetch_oasis_matches(names[0], names[1], names[2])
                    if oasis.get("success"):
                        descs = {}
                        for m in oasis.get("matches",[])[:8]:
                            try:
                                p = fetch_noc_unit_profile(m["code"])
                                if p.get("title"): descs[m["code"]] = {"title":p["title"],"example_titles":p.get("example_titles",[])[:5],"main_duties":p.get("main_duties",[])[:4],"employment_requirements":p.get("employment_requirements",[])[:3]}
                            except: pass
                        st.session_state["_oasis"] = {**oasis,"descriptions":descs}
                    else: st.session_state["_oasis"] = {"success":False,"matches":[]}
                except Exception as e: st.session_state["_oasis"] = {"success":False,"matches":[],"error":str(e)}
            else: st.session_state["_oasis"] = {"success":False,"matches":[]}
    oasis = st.session_state["_oasis"]

    # Header
    code_str = "".join(top3)
    st.markdown(
        f'<div style="margin-bottom:24px">'
        f'<div style="font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin-bottom:6px">Deep Analysis</div>'
        f'<div style="font-size:1.8rem;font-weight:700;color:#111827;letter-spacing:-.03em">Holland Code: {code_str}</div>'
        f'<div style="font-size:.85rem;color:#6B7280;margin-top:4px">{stage} · {scenario}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    ai_layers = st.session_state.get("_ai_layers", [""]*5)
    tabs = st.tabs(["1 · Dimensions","2 · Code Identity","3 · Structure","4 · Relationships","5 · Career Map"])

    # Tab 0
    with tabs[0]:
        st.markdown('<div style="background:#fff;border:1px solid #E5E7EB;border-radius:16px;padding:22px;margin:12px 0">', unsafe_allow_html=True)
        st.markdown('<div style="font-size:.68rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#9CA3AF;margin-bottom:14px">Dimension Scores</div>', unsafe_allow_html=True)
        for row in rule["sorted_types"]:
            t,name,score = row["type"],row["name"],row["score"]
            color = HOLLAND_TYPE_INFO[t]["color"]; pct=int((score/5)*100); is_top=t in top3
            st.markdown(f'<div style="display:flex;align-items:center;gap:10px;padding:6px 0"><span style="min-width:20px;font-size:.82rem;font-weight:{"700" if is_top else "500"};color:{color}">{t}</span><span style="min-width:100px;font-size:.8rem;font-weight:{"600" if is_top else "400"};color:#374151">{name}</span><div style="flex:1;height:8px;background:#F3F4F6;border-radius:4px;overflow:hidden"><div style="width:{pct}%;height:100%;background:{color};border-radius:4px"></div></div><span style="min-width:36px;text-align:right;font-size:.82rem;font-weight:700;color:{color}">{score:.2f}</span></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if ai_layers[0]: st.divider(); st.markdown(ai_layers[0])

    # Tab 1
    with tabs[1]:
        ranks = ["Primary","Secondary","Tertiary"]
        cols = st.columns(3)
        for i,t in enumerate(top3):
            info=HOLLAND_TYPE_INFO[t]
            with cols[i]:
                st.markdown(f'<div style="text-align:center;padding:20px 12px;background:{info["color"]}0d;border:1.5px solid {info["color"]}35;border-radius:14px;margin:12px 0"><div style="font-size:2.8rem;font-weight:800;color:{info["color"]};line-height:1">{t}</div><div style="font-size:.72rem;font-weight:600;color:{info["color"]};margin-top:4px;text-transform:uppercase">{info["name"]}</div><div style="font-size:.68rem;color:#9CA3AF;margin-top:2px">{ranks[i]}</div></div>', unsafe_allow_html=True)
        trait_html="".join(f'<span style="font-size:.75rem;padding:4px 11px;border-radius:20px;border:1.5px solid {HOLLAND_TYPE_INFO[t]["color"]}40;background:{HOLLAND_TYPE_INFO[t]["color"]}0a;color:{HOLLAND_TYPE_INFO[t]["color"]};margin:3px">{tr.strip()}</span>' for t in top3 for tr in HOLLAND_TYPE_INFO[t]["traits"].split(",")[:2])
        st.markdown(f'<div style="display:flex;flex-wrap:wrap;margin:14px 0">{trait_html}</div>', unsafe_allow_html=True)
        st.markdown(_build_hex_svg(200, top3, scores, False), unsafe_allow_html=True)
        if ai_layers[1]: st.divider(); st.markdown(ai_layers[1])

    # Tab 2
    with tabs[2]:
        color_map={"Concentrated":"#15803D","Balanced":"#0369A1","Dual-Core":"#7C3AED","Dispersed":"#B45309","Gradient":"#374151"}
        bg_map={"Concentrated":"#F0FDF4","Balanced":"#F0F9FF","Dual-Core":"#F5F3FF","Dispersed":"#FFFBEB","Gradient":"#F9FAFB"}
        bd_map={"Concentrated":"#BBF7D0","Balanced":"#BAE6FD","Dual-Core":"#DDD6FE","Dispersed":"#FDE68A","Gradient":"#E5E7EB"}
        stype=rule["structure_type"]
        st.markdown(f'<div style="display:inline-flex;align-items:center;font-size:.9rem;font-weight:700;padding:10px 18px;border-radius:10px;margin:12px 0 8px;background:{bg_map.get(stype,"#F9FAFB")};color:{color_map.get(stype,"#374151")};border:1.5px solid {bd_map.get(stype,"#E5E7EB")}">{stype}</div>', unsafe_allow_html=True)
        st.caption(rule["structure_desc"])
        for label,val in [("1st → 2nd",rule["gaps"]["gap_1_2"]),("2nd → 3rd",rule["gaps"]["gap_2_3"]),("Highest → Lowest",rule["gaps"]["gap_high_low"])]:
            pct=min(100,int((val/4)*100))
            st.markdown(f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px"><span style="min-width:130px;font-size:.75rem;color:#6B7280">{label}</span><div style="flex:1;height:6px;background:#F3F4F6;border-radius:3px;overflow:hidden"><div style="width:{pct}%;height:100%;background:#6366F1;border-radius:3px"></div></div><span style="min-width:36px;font-size:.75rem;font-weight:700;color:#6366F1;text-align:right">{val:.2f}</span></div>', unsafe_allow_html=True)
        if rule["certainties"]:
            st.markdown('<div style="font-size:.72rem;font-weight:700;color:#9CA3AF;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 8px">Certainties</div>', unsafe_allow_html=True)
            for c in rule["certainties"]: st.markdown(f'<div style="display:flex;align-items:flex-start;gap:8px;font-size:.82rem;color:#374151;margin-bottom:6px"><span style="width:7px;height:7px;border-radius:50%;background:#10B981;flex-shrink:0;margin-top:5px"></span>{c}</div>', unsafe_allow_html=True)
        if rule["uncertainties"]:
            st.markdown('<div style="font-size:.72rem;font-weight:700;color:#9CA3AF;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 8px">Uncertainties</div>', unsafe_allow_html=True)
            for u in rule["uncertainties"]: st.markdown(f'<div style="display:flex;align-items:flex-start;gap:8px;font-size:.82rem;color:#374151;margin-bottom:6px"><span style="width:7px;height:7px;border-radius:50%;background:#F59E0B;flex-shrink:0;margin-top:5px"></span>{u}</div>', unsafe_allow_html=True)
        if ai_layers[2]: st.divider(); st.markdown(ai_layers[2])

    # Tab 3
    with tabs[3]:
        st.markdown(_build_hex_svg(280, top3, scores, True), unsafe_allow_html=True)
        if rule["complements"]:
            st.markdown('<div style="font-size:.72rem;font-weight:700;color:#9CA3AF;text-transform:uppercase;letter-spacing:.06em;margin:16px 0 8px">Complementary Pairs</div>', unsafe_allow_html=True)
            for c in rule["complements"]: st.markdown(f'<div style="display:flex;align-items:flex-start;gap:8px;font-size:.82rem;color:#374151;margin-bottom:6px"><span style="width:7px;height:7px;border-radius:50%;background:#10B981;flex-shrink:0;margin-top:5px"></span>{c}</div>', unsafe_allow_html=True)
        if rule["tensions"]:
            st.markdown('<div style="font-size:.72rem;font-weight:700;color:#9CA3AF;text-transform:uppercase;letter-spacing:.06em;margin:14px 0 8px">Tension Pairs</div>', unsafe_allow_html=True)
            for t_item in rule["tensions"]: st.markdown(f'<div style="display:flex;align-items:flex-start;gap:8px;font-size:.82rem;color:#374151;margin-bottom:6px"><span style="width:7px;height:7px;border-radius:50%;background:#F59E0B;flex-shrink:0;margin-top:5px"></span>{t_item}</div>', unsafe_allow_html=True)
        if not rule["complements"] and not rule["tensions"]: st.info("No strong pairs identified among your top-3 types.")
        if ai_layers[3]: st.divider(); st.markdown(ai_layers[3])

    # Tab 4
    with tabs[4]:
        if oasis.get("success") and oasis.get("matches"):
            for m in oasis["matches"][:6]:
                code,title=m["code"],m["title"]; desc=oasis.get("descriptions",{}).get(code,{}); duty=(desc.get("main_duties") or [""])[0]
                duty_html = f'<div style="font-size:.8rem;color:#6B7280;line-height:1.55">{duty}</div>' if duty else ""
                mb = "6px" if duty else "0"
                st.markdown(f'<div style="background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:16px 18px;margin-bottom:10px"><div style="display:flex;align-items:center;gap:10px;margin-bottom:{mb}"><span style="font-size:.68rem;font-weight:700;padding:3px 8px;border-radius:6px;background:#F0F9FF;color:#0369A1;border:1px solid #BAE6FD">NOC {code}</span><span style="font-size:.9rem;font-weight:700;color:#111827">{title}</span></div>{duty_html}</div>', unsafe_allow_html=True)
        else:
            st.info("Occupation data unavailable. The AI interpretation covers career directions in detail.")
        if ai_layers[4]: st.divider(); st.markdown(ai_layers[4])

        # ── Write Holland results to session_state for Competence Comparison ──
        _matches = oasis.get("matches", []) if oasis.get("success") else []
        st.session_state["holland"] = {
            "best":  [{"code": m["code"], "title": m["title"]} for m in _matches[:3]],
            "worth": [{"code": m["code"], "title": m["title"]} for m in _matches[3:6]],
        }

        # ── Navigate to Competence Comparison ─────────────────
        st.divider()
        st.markdown(
            "<div style='background:#0F172A;border-radius:12px;padding:24px 28px;margin-top:8px'>"
            "<div style='font-size:.65rem;font-weight:700;letter-spacing:.1em;"
            "text-transform:uppercase;color:#475569;margin-bottom:8px'>Next Step</div>"
            "<div style='font-size:1.05rem;font-weight:800;color:#F8FAFC;margin-bottom:8px'>"
            "Compare Competencies</div>"
            "<div style='font-size:.82rem;color:#64748B;line-height:1.65;margin-bottom:0'>"
            "Your Holland Code career matches are saved. Cross-reference them with your "
            "Career Explorer occupations — skills, knowledge, and work-style gaps, "
            "plus an AI advising report.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        _, _btn_c, _ = st.columns([1, 2, 1])
        with _btn_c:
            if st.button("Go to Competence Comparison →", type="primary",
                         use_container_width=True, key="to_comparison"):
                st.switch_page("pages/3_Competence_Comparison.py")

    # AI generation
    st.divider()
    if st.session_state.get("_ai_gen"):
        if not _HAS_OPENAI:
            st.error("openai package not installed.")
            del st.session_state["_ai_gen"]
        else:
            st.markdown(
                "<div style='font-size:.72rem;font-weight:600;letter-spacing:.08em;"
                "text-transform:uppercase;color:#9CA3AF;margin-bottom:14px'>"
                "AI Interpretation</div>",
                unsafe_allow_html=True,
            )
            _pb = st.progress(0, text="Initialising…")
            try:
                # Phases keyed by elapsed seconds (estimated ~45 s for full report)
                _PHASES = [
                    ( 0, "Analysing your RIASEC profile…"),
                    ( 8, "Identifying personality dimensions…"),
                    (16, "Mapping Holland Code structure…"),
                    (25, "Exploring career relationships…"),
                    (33, "Building career map & action plan…"),
                    (40, "Finalising interpretation…"),
                ]
                _EST_SECONDS = 50   # generous upper bound
                _buf: list = []
                _t0 = time.time()
                _last_ui = _t0     # throttle: update UI at most ~3× per second

                for _chunk in _qwen_stream(scores, rule, oasis, stage, scenario, background):
                    _buf.append(_chunk)
                    _now = time.time()
                    if _now - _last_ui >= 0.35:
                        _elapsed = _now - _t0
                        _pct = min(_elapsed / _EST_SECONDS, 0.95)
                        _msg = _PHASES[0][1]
                        for _sec, _m in _PHASES:
                            if _elapsed >= _sec:
                                _msg = _m
                        _pb.progress(_pct, text=_msg)
                        _last_ui = _now

                _pb.progress(1.0, text="Done — loading results…")
                _report = "".join(_buf)
                st.session_state["_ai_layers"] = _parse_layers(_report)
                del st.session_state["_ai_gen"]
                st.rerun()
            except Exception as e:
                _pb.empty()
                st.error(f"AI generation failed: {e}")
                del st.session_state["_ai_gen"]
    elif not st.session_state.get("_ai_layers"):
        col1,col2,col3 = st.columns([1,2,1])
        with col2:
            if _HAS_OPENAI:
                if st.button("Generate AI Interpretation", type="primary", use_container_width=True, key="gen_ai"):
                    st.session_state["_ai_gen"] = True; st.rerun()
            else:
                st.warning("Install openai: `pip install openai`")

    st.divider()
    col_back, col_ret = st.columns(2)
    with col_back:
        if st.button("← Back to Results", use_container_width=True, key="an_back"):
            st.session_state["_step"]=7; st.rerun()
    with col_ret:
        if st.button("Retake Test", use_container_width=True, key="an_retake"):
            for k in list(st.session_state.keys()):
                if any(k.startswith(p) for p in ["_step","_ans","_answers","_scores","_top3","_rule","_oasis","_ai","_ctx"]):
                    del st.session_state[k]
            st.session_state["_step"]=0; st.rerun()

# ── Router ─────────────────────────────────────────────────────────
def main():
    step = st.session_state.get("_step", 0)
    if   step == 0: _render_landing()
    elif step == 7: _render_results()
    elif step == 8: _render_context()
    elif step == 9: _render_analysis()
    else:           _render_quiz(step)

if __name__ == "__main__":
    main()

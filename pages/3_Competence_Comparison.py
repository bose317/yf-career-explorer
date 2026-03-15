"""Standalone Competence Comparison page — port 8503.

Wizard pages:
  Page 0 — Step 1: NOC Overlap Analysis
  Page 1 — Step 2: Deep Competence Comparison (item-by-item match table)
  Page 2 — Step 3: Sorted Gap Analysis (table + charts)
  Page 3 — Step 4: AI Advising Report (charts + personalised report)
"""
from __future__ import annotations

import json
import os
import re

import streamlit as st
import plotly.graph_objects as go

from oasis_client import (
    fetch_jobbank_skills,
    fetch_noc_description,
    fetch_noc_unit_profile,
)
from processors import fetch_noc_gender_breakdown

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG & GLOBAL CSS
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Competence Comparison — Holland × Career Explorer",
    page_icon="⬛",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,wght@0,300;0,400;0,500;0,600;0,700;0,800;0,900;1,400&family=JetBrains+Mono:wght@400;500&display=swap');

/* Reset & base */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #FAFAFA;
    color: #0F172A;
}
#MainMenu, footer, header { visibility: hidden; }
.block-container {
    padding-top: 2.5rem;
    padding-bottom: 5rem;
    max-width: 1180px;
}

/* Buttons */
.stButton > button {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: .8rem;
    letter-spacing: .01em;
    border-radius: 6px;
    transition: all .15s ease;
}
.stButton > button[kind="primary"] {
    background: #0F172A;
    border: 1.5px solid #0F172A;
    color: #fff;
}
.stButton > button[kind="primary"]:hover {
    background: #1E293B;
}
.stButton > button:not([kind="primary"]) {
    background: #fff;
    border: 1.5px solid #CBD5E1;
    color: #0F172A;
}
.stButton > button:not([kind="primary"]):hover {
    border-color: #94A3B8;
    background: #F8FAFC;
}

/* Link buttons */
.stLinkButton > a {
    font-family: 'Inter', sans-serif;
    font-weight: 600;
    font-size: .78rem;
    border-radius: 6px;
    border: 1.5px solid #E2E8F0;
    color: #334155 !important;
    background: #fff;
    transition: all .15s ease;
}
.stLinkButton > a:hover {
    border-color: #94A3B8;
    background: #F8FAFC;
    color: #0F172A !important;
}

/* Expander */
details summary {
    font-size: .8rem;
    font-weight: 600;
    color: #475569;
    cursor: pointer;
}

/* Plotly charts — transparent bg */
.js-plotly-plot .plotly { background: transparent !important; }

/* Mono numbers */
.mono { font-family: 'JetBrains Mono', monospace; }

/* Divider */
hr { border: none; border-top: 1px solid #E2E8F0; margin: 24px 0; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# SESSION DATA
# Try session state first (multi-page app), then fall back to file
# ─────────────────────────────────────────────────────────────
_holland = st.session_state.get("holland", {})
_career  = st.session_state.get("career",  {})

# Fallback: file (for local single-app use)
if not _holland or not _career:
    try:
        with open("/tmp/yf_session.json") as _sf:
            _fs = json.load(_sf)
        if not _holland: _holland = _fs.get("holland", {})
        if not _career:  _career  = _fs.get("career",  {})
    except Exception:
        pass

_best_list  = _holland.get("best",  [])
_worth_list = _holland.get("worth", [])
best_codes   = [m["code"] for m in _best_list]
worth_codes  = [m["code"] for m in _worth_list]
best_titles  = {m["code"]: m["title"] for m in _best_list}
worth_titles = {m["code"]: m["title"] for m in _worth_list}

all_field_nocs: list = _career.get("all_field_nocs", [])
selected_nocs:  list = _career.get("selected_nocs",  [])
geo:             str = _career.get("geo",      "Canada")
cip_code:        str = _career.get("cip_code", "")
cip_name:        str = _career.get("cip_name", "")

# ─────────────────────────────────────────────────────────────
# WIZARD STATE
# ─────────────────────────────────────────────────────────────
_page: int = st.session_state.get("compare_page", 0)

# ─────────────────────────────────────────────────────────────
# STEPPER
# ─────────────────────────────────────────────────────────────
_STEPS = [
    ("01", "Occupation Overlap"),
    ("02", "Competence Match"),
    ("03", "Gap Analysis"),
    ("04", "AI Advising"),
]

_stepper = (
    "<div style='display:flex;align-items:stretch;gap:0;"
    "border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;"
    "margin-bottom:28px;background:#fff'>"
)
for _si, (_num, _label) in enumerate(_STEPS):
    _active   = _si == _page
    _complete = _si < _page
    if _active:
        _bg, _num_clr, _lbl_clr, _sep = "#0F172A", "#94A3B8", "#FFFFFF", "none"
    elif _complete:
        _bg, _num_clr, _lbl_clr, _sep = "#F1F5F9", "#94A3B8", "#0F172A", "1px solid #E2E8F0"
    else:
        _bg, _num_clr, _lbl_clr, _sep = "#FFFFFF", "#CBD5E1", "#94A3B8", "1px solid #E2E8F0"
    _check = "✓ " if _complete else ""
    _stepper += (
        f"<div style='flex:1;background:{_bg};padding:12px 16px;"
        f"border-right:{_sep};cursor:default'>"
        f"<div style='font-family:JetBrains Mono,monospace;font-size:.62rem;"
        f"font-weight:500;color:{_num_clr};letter-spacing:.12em;margin-bottom:3px'>"
        f"{_check}{_num}</div>"
        f"<div style='font-size:.75rem;font-weight:700;color:{_lbl_clr};"
        f"letter-spacing:.01em'>{_label}</div>"
        f"</div>"
    )
_stepper += "</div>"
st.markdown(_stepper, unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────
# PAGE HEADER
# ─────────────────────────────────────────────────────────────
_PAGE_META = [
    ("Occupation Overlap Analysis",
     "Holland Code best-fit careers vs. your field-of-study occupations."),
    ("Deep Competence Comparison",
     "Item-by-item match across Skills, Work Styles, and Knowledge."),
    ("Competency Gap Analysis",
     "All items ranked by gap magnitude — largest mismatches first."),
    ("AI Advising Report",
     "Personalised career advising with charts, grounded in your competency data."),
]
_ptitle, _psub = _PAGE_META[_page]

st.markdown(
    f"<div style='margin-bottom:4px'>"
    f"<span style='font-family:JetBrains Mono,monospace;font-size:.62rem;"
    f"font-weight:500;letter-spacing:.14em;color:#94A3B8;text-transform:uppercase'>"
    f"Holland Code × Career Explorer</span></div>"
    f"<h1 style='font-size:1.7rem;font-weight:800;letter-spacing:-.035em;"
    f"color:#0F172A;margin:0 0 6px'>{_ptitle}</h1>"
    f"<p style='font-size:.85rem;color:#64748B;margin:0 0 20px'>{_psub}</p>",
    unsafe_allow_html=True,
)

if not best_codes and not worth_codes:
    st.warning(
        "No Holland Code NOC data found. Complete the **Holland Code Test** in the sidebar, "
        "then return here."
    )
    st.stop()

st.divider()

# ─────────────────────────────────────────────────────────────
# DESIGN TOKENS & SHARED HELPERS
# ─────────────────────────────────────────────────────────────
# Score colour maps (same logic, refined palette)
_C5 = {5:"#DC2626", 4:"#EA580C", 3:"#D97706", 2:"#64748B", 1:"#94A3B8", 0:"#CBD5E1"}
_C3 = {3:"#DC2626", 2:"#64748B", 1:"#94A3B8", 0:"#CBD5E1"}

def _score_bar(avg: float, mx: int, clr: str) -> str:
    pct = avg / mx * 100
    return (
        f"<div style='display:flex;align-items:center;gap:7px'>"
        f"<div style='flex:1;background:#F1F5F9;border-radius:2px;height:7px;"
        f"overflow:hidden;min-width:56px'>"
        f"<div style='width:{pct:.1f}%;height:100%;background:{clr};border-radius:2px'></div>"
        f"</div>"
        f"<span style='font-family:JetBrains Mono,monospace;font-size:.75rem;"
        f"font-weight:500;color:{clr};min-width:26px;text-align:right'>{avg:.1f}</span>"
        f"</div>"
    )

def _match_tuple(norm: float) -> tuple:
    if   norm <= 0.10: return "#16A34A", "Strong",   "■■■■■"
    elif norm <= 0.20: return "#65A30D", "Good",     "■■■■□"
    elif norm <= 0.35: return "#D97706", "Moderate", "■■■□□"
    elif norm <= 0.50: return "#EA580C", "Weak",     "■■□□□"
    else:              return "#DC2626", "Low",      "■□□□□"

def _match_cell(norm: float) -> str:
    clr, label, blocks = _match_tuple(norm)
    return (
        f"<div style='text-align:center'>"
        f"<span style='font-size:.7rem;color:{clr};letter-spacing:2px'>{blocks}</span>"
        f"<div style='font-size:.65rem;font-weight:700;color:{clr};"
        f"letter-spacing:.04em;margin-top:2px'>{label}</div>"
        f"</div>"
    )

_MATCH_LEGEND = (
    "<div style='display:flex;flex-wrap:wrap;gap:0 20px;margin-bottom:16px'>"
    + "".join(
        f"<span style='display:inline-flex;align-items:center;gap:5px;"
        f"font-size:.7rem;color:#64748B'>"
        f"<span style='color:{c};font-size:.72rem;letter-spacing:1.5px'>{d}</span>"
        f"{l}</span>"
        for c, d, l in [
            ("#16A34A","■■■■■","Strong ≤10%"),
            ("#65A30D","■■■■□","Good ≤20%"),
            ("#D97706","■■■□□","Moderate ≤35%"),
            ("#EA580C","■■□□□","Weak ≤50%"),
            ("#DC2626","■□□□□","Low >50%"),
        ]
    )
    + "</div>"
)

def _section_label(text: str, sub: str = "") -> str:
    return (
        f"<div style='margin:0 0 8px'>"
        f"<span style='font-family:JetBrains Mono,monospace;font-size:.62rem;"
        f"font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:#94A3B8'>"
        f"{text}</span>"
        + (f"<span style='font-size:.75rem;color:#94A3B8;margin-left:8px'>{sub}</span>" if sub else "")
        + "</div>"
    )

def _pill(code: str, name: str) -> str:
    """Neutral dark pill for NOC codes."""
    return (
        f"<span style='display:inline-flex;align-items:center;gap:5px;"
        f"background:#F8FAFC;border:1px solid #E2E8F0;border-radius:4px;"
        f"padding:3px 9px;margin:3px;font-size:.72rem;color:#334155'>"
        f"<span style='font-family:JetBrains Mono,monospace;font-size:.62rem;"
        f"color:#94A3B8'>{code}</span>{name}</span>"
    )

def _tag(text: str, variant: str = "default") -> str:
    styles = {
        "default": "background:#F1F5F9;color:#475569;border:1px solid #E2E8F0",
        "match":   "background:#F0FDF4;color:#15803D;border:1px solid #BBF7D0",
        "select":  "background:#EFF6FF;color:#1D4ED8;border:1px solid #BFDBFE",
        "section": "background:#F8FAFC;color:#64748B;border:1px solid #E2E8F0",
    }
    st_css = styles.get(variant, styles["default"])
    return (
        f"<span style='{st_css};border-radius:4px;padding:2px 8px;"
        f"font-size:.65rem;font-weight:600;letter-spacing:.03em'>{text}</span>"
    )

def _get_qwen_creds() -> tuple:
    try:
        return st.secrets["QWEN_BASE_URL"], st.secrets["QWEN_API_KEY"]
    except Exception:
        pass
    return "", ""

def _strip_think(text: str) -> str:
    """Remove <think>…</think> blocks from model output."""
    return re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()

def _nav(back_page: int | None, next_page: int | None,
         next_label: str = "Next →", back_label: str = "← Back"):
    st.divider()
    cols = st.columns([1.4, 2, 5])
    if back_page is not None:
        with cols[0]:
            if st.button(back_label, use_container_width=True):
                st.session_state["compare_page"] = back_page
                st.rerun()
    if next_page is not None:
        with cols[1]:
            if st.button(next_label, type="primary", use_container_width=True):
                st.session_state["compare_page"] = next_page
                st.rerun()

# ─── Comparison table (shared by Step 2) ─────────────────────
def _cmp_table(section_key: str, section_title: str, level_label: str,
               cm: dict, mx: int, holland_nocs: list, career_nocs: list,
               all_skills: dict, collector: list):
    st.markdown(
        f"<div style='margin:20px 0 4px'>{_section_label(section_title, level_label)}</div>",
        unsafe_allow_html=True,
    )

    all_names: list = []
    seen: set = set()
    for noc_list in (holland_nocs, career_nocs):
        for n in noc_list:
            for item in all_skills.get(n["code"], {}).get(section_key, []):
                if item["name"] not in seen:
                    seen.add(item["name"])
                    all_names.append(item["name"])

    if not all_names:
        st.caption(f"No {section_title.lower()} data available.")
        st.divider()
        return

    def _gavg(noc_list, name):
        sc = []
        for n in noc_list:
            for item in all_skills.get(n["code"], {}).get(section_key, []):
                if item["name"] == name and item["level"] and item["level"][0].isdigit():
                    sc.append(int(item["level"][0])); break
        return sum(sc) / len(sc) if sc else None

    # Table CSS
    TH = ("background:#0F172A;color:#94A3B8;padding:8px 12px;font-size:.68rem;"
          "font-weight:600;letter-spacing:.06em;text-transform:uppercase;text-align:")
    TD = "padding:6px 12px;border-bottom:1px solid #F1F5F9;vertical-align:middle;"

    col_defs = (
        "<colgroup>"
        "<col style='width:200px'/><col style='width:155px'/>"
        "<col style='width:155px'/><col style='width:115px'/>"
        "</colgroup>"
    )
    thead = (
        f"<thead><tr>"
        f"<th style='{TH}left;border-right:1px solid #1E293B'>{level_label}</th>"
        f"<th style='{TH}center;border-right:1px solid #1E293B'>"
        f"Career Explorer Avg<br><span style='font-size:.58rem;color:#64748B;font-weight:400'>"
        f"({len(career_nocs)} NOCs)</span></th>"
        f"<th style='{TH}center;border-right:1px solid #1E293B'>"
        f"Holland Code Avg<br><span style='font-size:.58rem;color:#64748B;font-weight:400'>"
        f"({len(holland_nocs)} NOCs)</span></th>"
        f"<th style='{TH}center'>Match</th>"
        f"</tr></thead>"
    )

    rows = ""
    for name in all_names:
        ca = _gavg(career_nocs,  name)
        ha = _gavg(holland_nocs, name)
        if ha is None:
            ha = 0.0
        if ca is not None:
            g = abs(ca - ha) / mx
            mc, ml, md = _match_tuple(g)
            collector.append({
                "section": section_title, "name": name,
                "career_avg": ca, "holland_avg": ha,
                "norm_gap": g, "match_label": ml,
                "match_dots": md, "match_clr": mc, "mx": mx,
            })

        c_cell = (
            _score_bar(ca, mx, cm.get(round(ca), "#94A3B8"))
            if ca is not None
            else "<span style='color:#CBD5E1;font-size:.72rem'>—</span>"
        )
        h_cell = _score_bar(ha, mx, cm.get(round(ha), "#94A3B8"))
        m_cell = (
            _match_cell(abs(ca - ha) / mx)
            if ca is not None
            else "<span style='color:#CBD5E1;font-size:.72rem'>—</span>"
        )

        # Alternate row bg
        bg = "#FFFFFF" if len(rows) % 2 == 0 else "#FAFAFA"
        rows += (
            f"<tr style='background:{bg}'>"
            f"<td style='{TD}border-right:1px solid #F1F5F9;font-size:.8rem;"
            f"font-weight:500;color:#1E293B;white-space:nowrap'>{name}</td>"
            f"<td style='{TD}border-right:1px solid #F1F5F9;background:#FAFEFF'>{c_cell}</td>"
            f"<td style='{TD}border-right:1px solid #F1F5F9;background:#F7FBF7'>{h_cell}</td>"
            f"<td style='{TD}'>{m_cell}</td>"
            f"</tr>"
        )

    st.markdown(
        f"<div style='border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;"
        f"box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:4px'>"
        f"<table style='width:100%;border-collapse:collapse;table-layout:fixed'>"
        f"{col_defs}{thead}<tbody>{rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div style='margin-bottom:24px'>{_MATCH_LEGEND}</div>", unsafe_allow_html=True)


# ═════════════════════════════════════════════════════════════
# PAGE 0 — STEP 1: NOC OVERLAP
# ═════════════════════════════════════════════════════════════
if _page == 0:
    field_codes = {n["code"] for n in all_field_nocs if n.get("code")}
    sel_codes   = {n["code"] for n in selected_nocs  if n.get("code")}

    # ── Section A ─────────────────────────────────────────────
    st.markdown(
        f"<div style='margin-bottom:8px'>{_section_label('A', 'Holland Best Fit  ×  Field-of-Study Occupations')}</div>",
        unsafe_allow_html=True,
    )
    if not all_field_nocs:
        st.info("Career Explorer data not found. Open **Career Explorer** in the sidebar, complete your analysis, then return.")
        field_overlap: set = set()
    else:
        field_overlap = set(best_codes) & field_codes
        if field_overlap:
            st.success(f"**{len(field_overlap)} overlap(s)** found with graduates' most common occupations in your field.")
        else:
            st.warning("No direct overlap found — proceed to the competence comparison to understand the gap.")

    # ── Section B ─────────────────────────────────────────────
    st.markdown(
        f"<div style='margin:20px 0 8px'>{_section_label('B', 'Holland Best Fit  ×  Your 6 Selected Occupations')}</div>",
        unsafe_allow_html=True,
    )
    if not selected_nocs:
        st.info("No selected occupations from Career Explorer. Use **Career Explorer** in the sidebar to select up to 6.")
        sel_overlap: set = set()
    else:
        sel_overlap = set(best_codes) & sel_codes
        if sel_overlap:
            st.success(f"**{len(sel_overlap)} overlap(s)** found with your personally selected occupations.")
        else:
            st.warning("None of your selected occupations directly matches your Holland Best Fit careers.")

    all_overlap = field_overlap | sel_overlap

    # ── Overlap cards ─────────────────────────────────────────
    if all_overlap:
        st.markdown(
            f"<div style='margin:28px 0 8px'>{_section_label('Overlapping Occupations', 'employment headcount · description · NOC profile')}</div>",
            unsafe_allow_html=True,
        )

        overlap_entries = []
        for code in all_overlap:
            title = best_titles.get(code) or worth_titles.get(code)
            if not title:
                for n in all_field_nocs:
                    if n["code"] == code:
                        title = n["name"]; break
            overlap_entries.append({"noc": f"{code} {title or code}"})

        with st.spinner("Fetching headcount…"):
            try:
                gender_data = fetch_noc_gender_breakdown(
                    overlap_entries, cip_code, "", "", top_n=len(overlap_entries), geo=geo)
            except Exception:
                gender_data = []

        noc_desc_data: dict = {}
        noc_profiles:  dict = {}
        with st.spinner("Fetching NOC profiles…"):
            for entry in overlap_entries:
                code = entry["noc"].split(" ", 1)[0]
                try:
                    info = fetch_noc_description(code)
                    if info and (info.get("description") or info.get("sub_profiles")):
                        noc_desc_data[entry["noc"]] = info
                except Exception:
                    pass
                try:
                    noc_profiles[code] = fetch_noc_unit_profile(code)
                except Exception:
                    pass

        _DETAIL_KEYS = [
            ("example_titles","Example Titles"), ("main_duties","Main Duties"),
            ("employment_requirements","Employment Requirements"),
            ("additional_information","Additional Information"),
        ]
        gender_lookup = {row["noc"].split(" ",1)[0]: row for row in (gender_data or [])}

        for idx, entry in enumerate(overlap_entries, 1):
            noc_name = entry["noc"]
            noc_code = noc_name.split(" ", 1)[0]

            # Card wrapper
            st.markdown(
                f"<div style='border:1px solid #E2E8F0;border-radius:8px;padding:16px 20px;"
                f"margin-bottom:12px;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.04)'>",
                unsafe_allow_html=True,
            )

            # Header row
            tag_html = ""
            if noc_code in field_overlap:
                tag_html += _tag("✓ Field Match", "match") + " "
            if noc_code in sel_overlap:
                tag_html += _tag("✓ Your Selection", "select")

            st.markdown(
                f"<div style='display:flex;align-items:baseline;gap:10px;margin-bottom:8px'>"
                f"<span style='font-size:1rem;font-weight:700;color:#0F172A'>{idx}. {noc_name}</span>"
                f"<span>{tag_html}</span></div>",
                unsafe_allow_html=True,
            )

            # Description
            desc = None
            info = noc_desc_data.get(noc_name)
            if info:
                desc = info.get("description")
                if not desc:
                    for sp in (info.get("sub_profiles") or []):
                        if sp.get("description"): desc = sp["description"]; break
            if not desc:
                duties = (noc_profiles.get(noc_code) or {}).get("main_duties") or []
                if duties:
                    desc = "; ".join(duties[:3]) + ("…" if len(duties) > 3 else "")
            if desc:
                st.markdown(
                    f"<div style='font-size:.83rem;line-height:1.6;color:#475569;"
                    f"border-left:2px solid #E2E8F0;padding-left:12px;margin-bottom:10px'>"
                    f"{desc}</div>",
                    unsafe_allow_html=True,
                )

            # Headcount
            gr = gender_lookup.get(noc_code)
            if gr:
                def _fmt(v): return f"{v:,}" if v is not None else "N/A"
                st.markdown(
                    f"<div style='display:flex;gap:20px;font-size:.78rem;color:#64748B;margin-bottom:8px'>"
                    f"<span>Total <b style='color:#0F172A'>{_fmt(gr.get('count_total'))}</b></span>"
                    f"<span>Male <b style='color:#0F172A'>{_fmt(gr.get('count_male'))}</b></span>"
                    f"<span>Female <b style='color:#0F172A'>{_fmt(gr.get('count_female'))}</b></span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            profile = noc_profiles.get(noc_code, {})
            if any(profile.get(k) for k, _ in _DETAIL_KEYS):
                with st.expander("View Details"):
                    for fk, fl in _DETAIL_KEYS:
                        items = profile.get(fk) or []
                        if items:
                            st.markdown(
                                f"<div style='font-size:.75rem;font-weight:700;color:#0F172A;"
                                f"text-transform:uppercase;letter-spacing:.06em;margin:10px 0 4px'>"
                                f"{fl}</div>",
                                unsafe_allow_html=True,
                            )
                            st.markdown(
                                "<ul style='margin:0;padding-left:16px;font-size:.82rem;"
                                "line-height:1.6;color:#475569'>"
                                + "".join(f"<li>{it}</li>" for it in items)
                                + "</ul>",
                                unsafe_allow_html=True,
                            )

            st.markdown("</div>", unsafe_allow_html=True)

    _nav(None, 1, next_label="Step 2: Competence Match →")


# ═════════════════════════════════════════════════════════════
# PAGE 1 — STEP 2: COMPETENCE MATCH
# ═════════════════════════════════════════════════════════════
elif _page == 1:
    if not selected_nocs:
        st.info("No selected occupations from Career Explorer. Use **Career Explorer** in the sidebar to select up to 6.")
        st.stop()

    holland_nocs = [
        {"code": c, "name": best_titles.get(c, worth_titles.get(c, ""))}
        for c in (best_codes + worth_codes)
    ]
    career_nocs = [{"code": n["code"], "name": n.get("name", "")} for n in selected_nocs]

    # NOC pills — two columns
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_section_label("Holland Code Careers"), unsafe_allow_html=True)
        _best_pills = "".join(
            _pill(c, best_titles.get(c, "")) for c in best_codes
        ) + "".join(
            _pill(c, worth_titles.get(c, "")) for c in worth_codes
        )
        st.markdown(f"<div style='line-height:2.2'>{_best_pills}</div>", unsafe_allow_html=True)
    with c2:
        st.markdown(_section_label("Career Explorer Selected"), unsafe_allow_html=True)
        _sel_pills = "".join(
            _pill(n["code"],
                  n.get("name","").split(" ",1)[-1] if " " in n.get("name","") else n.get("name",""))
            for n in selected_nocs
        )
        st.markdown(f"<div style='line-height:2.2'>{_sel_pills}</div>", unsafe_allow_html=True)

    # Fetch / cache skills
    _cache_key = tuple(sorted({n["code"] for n in holland_nocs + career_nocs}))
    if st.session_state.get("cmp_skills_key") != _cache_key:
        _fetched: dict = {}
        with st.spinner("Fetching competency data from Job Bank…"):
            for code in _cache_key:
                _fetched[code] = fetch_jobbank_skills(code, geo)
        st.session_state["cmp_skills"]     = _fetched
        st.session_state["cmp_skills_key"] = _cache_key
    all_skills: dict = st.session_state["cmp_skills"]

    if not any(s.get("skills") or s.get("work_styles") or s.get("knowledge")
               for s in all_skills.values()):
        st.warning("Could not retrieve competency data from Job Bank.")
        st.stop()

    _all_items: list = []
    for sk, st_title, ll, cm, mx in [
        ("skills",      "Skills",      "Proficiency / Complexity", _C5, 5),
        ("work_styles", "Work Styles", "Importance",               _C5, 5),
        ("knowledge",   "Knowledge",   "Knowledge Level",          _C3, 3),
    ]:
        _cmp_table(sk, st_title, ll, cm, mx, holland_nocs, career_nocs, all_skills, _all_items)

    st.session_state["cmp_all_items"]     = _all_items
    st.session_state["cmp_holland_nocs"]  = holland_nocs
    st.session_state["cmp_career_nocs"]   = career_nocs

    _nav(0, 2, back_label="← Step 1", next_label="Step 3: Gap Analysis →")


# ═════════════════════════════════════════════════════════════
# PAGE 2 — STEP 3: SORTED GAP ANALYSIS
# ═════════════════════════════════════════════════════════════
elif _page == 2:
    _all_items: list = st.session_state.get("cmp_all_items", [])
    if not _all_items:
        st.warning("No competency data — go back to Step 2 first.")
        _nav(1, None, back_label="← Step 2")
        st.stop()

    sorted_items = sorted(_all_items, key=lambda x: x["norm_gap"], reverse=True)
    avg_norm = sum(i["norm_gap"] for i in _all_items) / len(_all_items)
    if   avg_norm <= 0.20: overall_level, overall_clr = "Strong Match",  "#16A34A"
    elif avg_norm <= 0.35: overall_level, overall_clr = "Partial Match", "#D97706"
    else:                  overall_level, overall_clr = "Weak Match",    "#DC2626"

    # Banner
    _bk = {l: sum(1 for i in _all_items if i["match_label"] == l)
           for l in ("Strong","Good","Moderate","Weak","Low")}
    _bk_html = "".join(
        f"<div style='text-align:center'>"
        f"<div style='font-family:JetBrains Mono,monospace;font-size:1.1rem;"
        f"font-weight:700;color:{c}'>{_bk[l]}</div>"
        f"<div style='font-size:.65rem;color:#94A3B8;margin-top:1px'>{l}</div>"
        f"</div>"
        for c, l in [
            ("#16A34A","Strong"), ("#65A30D","Good"),
            ("#D97706","Moderate"), ("#EA580C","Weak"), ("#DC2626","Low"),
        ]
    )
    st.markdown(
        f"<div style='border:1px solid #E2E8F0;border-radius:8px;padding:16px 24px;"
        f"margin-bottom:24px;background:#fff;display:flex;align-items:center;gap:32px;"
        f"box-shadow:0 1px 3px rgba(0,0,0,.04)'>"
        f"<div>"
        f"<div style='font-family:JetBrains Mono,monospace;font-size:.6rem;"
        f"letter-spacing:.12em;color:#94A3B8;text-transform:uppercase;margin-bottom:4px'>"
        f"Overall Alignment</div>"
        f"<div style='font-size:1.5rem;font-weight:800;color:{overall_clr};"
        f"letter-spacing:-.02em'>{overall_level}</div>"
        f"<div style='font-size:.75rem;color:#94A3B8;margin-top:2px'>"
        f"avg gap {avg_norm*100:.0f}% · {len(_all_items)} items</div>"
        f"</div>"
        f"<div style='flex:1'></div>"
        f"<div style='display:flex;gap:20px'>{_bk_html}</div>"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Sorted table
    _SECT_CLR = {
        "Skills":      ("#F1F5F9","#334155"),
        "Work Styles": ("#FEF9EC","#78350F"),
        "Knowledge":   ("#F0FDF4","#14532D"),
    }
    TH2 = ("background:#0F172A;color:#94A3B8;padding:8px 10px;font-size:.65rem;"
           "font-weight:600;letter-spacing:.07em;text-transform:uppercase;text-align:")
    TD2 = "padding:5px 10px;border-bottom:1px solid #F1F5F9;vertical-align:middle;"

    col_defs = (
        "<colgroup><col style='width:76px'/><col style='width:190px'/>"
        "<col style='width:150px'/><col style='width:150px'/><col style='width:110px'/></colgroup>"
    )
    thead = (
        f"<thead><tr>"
        f"<th style='{TH2}left;border-right:1px solid #1E293B'>Cat.</th>"
        f"<th style='{TH2}left;border-right:1px solid #1E293B'>Competency Item</th>"
        f"<th style='{TH2}center;border-right:1px solid #1E293B'>Career Explorer Avg</th>"
        f"<th style='{TH2}center;border-right:1px solid #1E293B'>Holland Code Avg</th>"
        f"<th style='{TH2}center'>Match</th>"
        f"</tr></thead>"
    )

    rows = ""
    for idx, it in enumerate(sorted_items):
        sbg, scl = _SECT_CLR.get(it["section"], ("#F8FAFC","#475569"))
        sect_html = (
            f"<span style='background:{sbg};color:{scl};border-radius:3px;"
            f"padding:2px 6px;font-size:.62rem;font-weight:700;"
            f"letter-spacing:.03em'>{it['section']}</span>"
        )
        cm_row = _C3 if it["mx"] == 3 else _C5
        c_bar  = _score_bar(it["career_avg"],  it["mx"], cm_row.get(round(it["career_avg"]),  "#94A3B8"))
        h_bar  = _score_bar(it["holland_avg"], it["mx"], cm_row.get(round(it["holland_avg"]), "#94A3B8"))
        m_cell = _match_cell(it["norm_gap"])
        row_bg = "#FFFBF0" if it["norm_gap"] > 0.35 else ("#FFFFFF" if idx % 2 == 0 else "#FAFAFA")
        rows += (
            f"<tr style='background:{row_bg}'>"
            f"<td style='{TD2}border-right:1px solid #F1F5F9'>{sect_html}</td>"
            f"<td style='{TD2}border-right:1px solid #F1F5F9;font-size:.8rem;"
            f"font-weight:500;color:#1E293B'>{it['name']}</td>"
            f"<td style='{TD2}border-right:1px solid #F1F5F9;background:#FAFEFF'>{c_bar}</td>"
            f"<td style='{TD2}border-right:1px solid #F1F5F9;background:#F7FBF7'>{h_bar}</td>"
            f"<td style='{TD2}'>{m_cell}</td>"
            f"</tr>"
        )

    st.markdown(
        f"<div style='border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;"
        f"box-shadow:0 1px 4px rgba(0,0,0,.06);margin-bottom:8px'>"
        f"<table style='width:100%;border-collapse:collapse;table-layout:fixed'>"
        f"{col_defs}{thead}<tbody>{rows}</tbody></table></div>",
        unsafe_allow_html=True,
    )
    st.markdown(f"<div style='margin-bottom:8px'>{_MATCH_LEGEND}</div>", unsafe_allow_html=True)

    _nav(1, 3, back_label="← Step 2", next_label="Step 4: AI Advising →")


# ═════════════════════════════════════════════════════════════
# PAGE 3 — STEP 4: AI ADVISING REPORT
# ═════════════════════════════════════════════════════════════
elif _page == 3:
    _all_items: list = st.session_state.get("cmp_all_items", [])
    if not _all_items:
        st.warning("No competency data — go back to Step 2 first.")
        _nav(1, None, back_label="← Step 2")
        st.stop()

    sorted_items = sorted(_all_items, key=lambda x: x["norm_gap"], reverse=True)
    avg_norm = sum(i["norm_gap"] for i in _all_items) / len(_all_items)
    if   avg_norm <= 0.20: overall_level, overall_clr = "Strong Match",  "#16A34A"
    elif avg_norm <= 0.35: overall_level, overall_clr = "Partial Match", "#D97706"
    else:                  overall_level, overall_clr = "Weak Match",    "#DC2626"

    n_strong   = sum(1 for i in _all_items if i["match_label"] in ("Strong","Good"))
    n_moderate = sum(1 for i in _all_items if i["match_label"] == "Moderate")
    n_weak     = sum(1 for i in _all_items if i["match_label"] in ("Weak","Low"))

    # ── Stat cards ────────────────────────────────────────────
    cards_data = [
        ("OVERALL",       overall_level,    overall_clr),
        ("ITEMS ANALYSED",str(len(_all_items)), "#0F172A"),
        ("STRONG / GOOD", str(n_strong),    "#16A34A"),
        ("MODERATE",      str(n_moderate),  "#D97706"),
        ("WEAK / LOW",    str(n_weak),      "#DC2626"),
        ("AVG GAP",       f"{avg_norm*100:.0f}%", "#64748B"),
    ]
    card_html = "<div style='display:flex;gap:10px;margin-bottom:28px;flex-wrap:wrap'>"
    for lbl, val, clr in cards_data:
        card_html += (
            f"<div style='flex:1;min-width:110px;border:1px solid #E2E8F0;"
            f"border-radius:8px;padding:14px 16px;background:#fff;"
            f"box-shadow:0 1px 3px rgba(0,0,0,.04)'>"
            f"<div style='font-family:JetBrains Mono,monospace;font-size:.58rem;"
            f"font-weight:500;letter-spacing:.12em;text-transform:uppercase;"
            f"color:#94A3B8;margin-bottom:6px'>{lbl}</div>"
            f"<div style='font-size:1.25rem;font-weight:800;color:{clr};"
            f"letter-spacing:-.02em;line-height:1.1'>{val}</div>"
            f"</div>"
        )
    card_html += "</div>"
    st.markdown(card_html, unsafe_allow_html=True)

    # ── Charts ────────────────────────────────────────────────
    _SECT_KEYS = ["Skills", "Work Styles", "Knowledge"]
    _MAX_BY    = {"Skills": 5, "Work Styles": 5, "Knowledge": 3}

    def _sect_avg(sect, field):
        items = [i for i in _all_items if i["section"] == sect]
        return sum(i[field] for i in items) / len(items) if items else 0

    radar_career  = [_sect_avg(s, "career_avg")  for s in _SECT_KEYS]
    radar_holland = [_sect_avg(s, "holland_avg") for s in _SECT_KEYS]
    radar_cn = [v / _MAX_BY[s] * 100 for v, s in zip(radar_career,  _SECT_KEYS)]
    radar_hn = [v / _MAX_BY[s] * 100 for v, s in zip(radar_holland, _SECT_KEYS)]
    theta = _SECT_KEYS + [_SECT_KEYS[0]]

    ch_left, ch_right = st.columns([1, 1])

    # Radar
    with ch_left:
        fig_radar = go.Figure()
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_cn + [radar_cn[0]], theta=theta, fill="toself",
            name="Career Explorer",
            line=dict(color="#6366F1", width=2),
            fillcolor="rgba(99,102,241,0.12)",
            marker=dict(color="#6366F1", size=5),
        ))
        fig_radar.add_trace(go.Scatterpolar(
            r=radar_hn + [radar_hn[0]], theta=theta, fill="toself",
            name="Holland Code",
            line=dict(color="#0EA5E9", width=2),
            fillcolor="rgba(14,165,233,0.10)",
            marker=dict(color="#0EA5E9", size=5),
        ))
        fig_radar.update_layout(
            polar=dict(
                bgcolor="#F8FAFC",
                radialaxis=dict(
                    visible=True, range=[0, 100],
                    tickfont=dict(size=8, color="#94A3B8"),
                    gridcolor="#E2E8F0", linecolor="#E2E8F0",
                ),
                angularaxis=dict(
                    tickfont=dict(size=10, color="#334155"),
                    linecolor="#E2E8F0", gridcolor="#E2E8F0",
                ),
            ),
            showlegend=True,
            legend=dict(font=dict(size=10, color="#334155"), bgcolor="rgba(0,0,0,0)"),
            margin=dict(t=40, b=20, l=20, r=20),
            height=300,
            title=dict(
                text="Competency Profile (normalised 0–100%)",
                font=dict(size=12, color="#0F172A"), x=0.5,
            ),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # Donut
    with ch_right:
        _lvl_order  = ["Strong","Good","Moderate","Weak","Low"]
        _lvl_colors = ["#16A34A","#65A30D","#D97706","#EA580C","#DC2626"]
        _lvl_counts = [sum(1 for i in _all_items if i["match_label"] == l) for l in _lvl_order]
        fig_donut = go.Figure(go.Pie(
            labels=_lvl_order, values=_lvl_counts,
            hole=0.60,
            marker=dict(colors=_lvl_colors, line=dict(color="#fff", width=2)),
            textfont=dict(size=10, color="#fff"),
            hovertemplate="%{label}: %{value} items (%{percent})<extra></extra>",
        ))
        fig_donut.update_layout(
            showlegend=True,
            legend=dict(font=dict(size=10, color="#334155"), bgcolor="rgba(0,0,0,0)",
                        orientation="v", x=1.02, y=0.5),
            margin=dict(t=40, b=20, l=0, r=80),
            height=300,
            title=dict(text="Match Distribution", font=dict(size=12, color="#0F172A"), x=0.5),
            paper_bgcolor="rgba(0,0,0,0)",
            annotations=[dict(
                text=f"<b>{avg_norm*100:.0f}%</b><br><span style='font-size:9'>avg gap</span>",
                x=0.5, y=0.5, font=dict(size=13, color=overall_clr), showarrow=False,
            )],
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    # Top gaps bar chart — gap magnitude only
    top_gaps = sorted_items[:12]
    if top_gaps:
        # Colour by category
        _SECT_COLOR = {
            "Skills":      "#6366F1",   # indigo
            "Work Styles": "#0EA5E9",   # sky blue
            "Knowledge":   "#10B981",   # emerald
        }
        _rev = list(reversed(top_gaps))
        _names      = [it["name"] for it in _rev]
        _gap_vals   = [abs(it["career_avg"] - it["holland_avg"]) for it in _rev]
        _bar_colors = [_SECT_COLOR.get(it["section"], "#94A3B8") for it in _rev]
        _hover = [
            f"<b>{it['name']}</b>  [{it['section']}]"
            f"<br>Career: {it['career_avg']:.1f} · Holland: {it['holland_avg']:.1f}"
            f"<br>Gap: {abs(it['career_avg']-it['holland_avg']):.2f}  ({it['norm_gap']*100:.0f}%  {it['match_label']})"
            for it in _rev
        ]

        # One trace per section so legend entries appear
        fig_bar = go.Figure()
        for _sect, _clr in _SECT_COLOR.items():
            _idx = [i for i, it in enumerate(_rev) if it["section"] == _sect]
            if not _idx:
                continue
            fig_bar.add_trace(go.Bar(
                name=_sect,
                y=[_names[i] for i in _idx],
                x=[_gap_vals[i] for i in _idx],
                orientation="h",
                marker=dict(color=_clr, opacity=0.88),
                hovertext=[_hover[i] for i in _idx],
                hovertemplate="%{hovertext}<extra></extra>",
            ))

        fig_bar.update_layout(
            barmode="overlay",
            xaxis=dict(
                title=dict(text="Gap (score units)", font=dict(size=10, color="#94A3B8")),
                range=[0, 5], tickfont=dict(size=9, color="#94A3B8"),
                gridcolor="#F1F5F9", linecolor="#E2E8F0",
            ),
            yaxis=dict(
                automargin=True, tickfont=dict(size=9.5, color="#334155"),
                linecolor="#E2E8F0", categoryorder="array",
                categoryarray=_names,
            ),
            showlegend=True,
            legend=dict(
                font=dict(size=10, color="#334155"),
                bgcolor="rgba(0,0,0,0)",
                orientation="h", y=1.06, x=0,
            ),
            margin=dict(t=52, b=20, l=10, r=16),
            height=max(300, len(top_gaps) * 28 + 80),
            title=dict(
                text="Top 12 Competency Gaps — Score Difference",
                font=dict(size=12, color="#0F172A"),
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="#FAFAFA",
            bargap=0.32,
        )
        fig_bar.update_xaxes(gridcolor="#F1F5F9")
        st.plotly_chart(fig_bar, use_container_width=True)

    st.divider()

    # ── AI Advising ───────────────────────────────────────────
    st.markdown(
        f"<div style='margin-bottom:4px'>{_section_label('Personalised Advising Report', 'AI-generated · Student Advising Dataset framework')}</div>",
        unsafe_allow_html=True,
    )

    qwen_url, qwen_key = _get_qwen_creds()

    if not qwen_url or not qwen_key:
        st.warning(
            "Qwen API credentials not found. "
            "Set `QWEN_BASE_URL` and `QWEN_API_KEY` in `Holland/.streamlit/secrets.toml`."
        )
    else:
        _holland_type  = " / ".join(best_titles.get(c, c) for c in best_codes[:3]) or "Unknown"
        _career_titles = ", ".join(n.get("name", n.get("code","")) for n in selected_nocs[:6]) or "Unknown"
        _field         = cip_name or "your field of study"
        _gap_pct       = f"{avg_norm * 100:.0f}%"
        _skills_gap    = sum(1 for i in _all_items if i["section"] == "Skills"      and i["norm_gap"] > 0.35)
        _know_gap      = sum(1 for i in _all_items if i["section"] == "Knowledge"   and i["norm_gap"] > 0.35)
        _ws_gap        = sum(1 for i in _all_items if i["section"] == "Work Styles" and i["norm_gap"] > 0.35)
        _worst5 = sorted(_all_items, key=lambda x: x["norm_gap"], reverse=True)[:5]
        _best5  = sorted(_all_items, key=lambda x: x["norm_gap"])[:5]
        _worst_lines = "\n".join(
            f"  - {i['name']} ({i['section']}): Career {i['career_avg']:.1f} vs Holland {i['holland_avg']:.1f} → {i['match_label']}"
            for i in _worst5)
        _best_lines = "\n".join(
            f"  - {i['name']} ({i['section']}): Career {i['career_avg']:.1f} vs Holland {i['holland_avg']:.1f} → {i['match_label']}"
            for i in _best5)
        _sect_summary = "\n".join(
            f"  - {s}: Career avg {radar_career[k]:.2f}, Holland avg {radar_holland[k]:.2f}"
            for k, s in enumerate(_SECT_KEYS))

        _system_prompt = (
            "You are an experienced career advisor at a Canadian post-secondary institution. "
            "Write warm, encouraging, and practical advising reports in English. "
            "Follow the Student Advising Dataset framework: "
            "Strong Match (avg gap ≤20%) → deepen and accelerate existing strengths; "
            "Partial Match (avg gap 21–35%) → explore bridging experiences and targeted skill development; "
            "Weak Match (avg gap >35%) → clarify direction, consider pathway adjustment. "
            "Reference specific competency item names and their scores. "
            "Include a 3-stage WIL pathway (CEWIL: e.g. Job Shadowing → Volunteer/Simulation → Co-op/Internship). "
            "Use clear bold section headers. Approximately 450 words. "
            "Do NOT output any <think> tags or internal reasoning — only the final report."
        )
        _user_prompt = (
            f"Write a personalised career advising report.\n\n"
            f"**Profile:**\n"
            f"- Field of Study: {_field}\n"
            f"- Holland Code Best-Fit Careers: {_holland_type}\n"
            f"- Career Explorer Selected Occupations: {_career_titles}\n"
            f"- Overall Alignment: {overall_level} (average gap: {_gap_pct}, {len(_all_items)} items)\n\n"
            f"**Section Averages (Career vs Holland, raw scale):**\n{_sect_summary}\n\n"
            f"**Top 5 Gaps:**\n{_worst_lines}\n\n"
            f"**Top 5 Strengths:**\n{_best_lines}\n\n"
            f"**Gap counts (items with >35% gap):** Skills {_skills_gap} · Knowledge {_know_gap} · Work Styles {_ws_gap}\n\n"
            f"**Report structure (use these bold headers):**\n"
            f"1. **Profile Summary** — open: \"Let's look at your profile together. Your Holland personality profile points toward [types] and you are studying {_field}.\"\n"
            f"2. **Career Direction**\n"
            f"3. **Competency Analysis** (cite item names + scores)\n"
            f"4. **What This Means** (interpret {overall_level} practically)\n"
            f"5. **Next Steps** (3-4 actions matched to gap level)\n"
            f"6. **WIL Journey Plan** (3 stages with rationale)\n"
        )

        if "ai_report" not in st.session_state:
            if st.button("Generate AI Advising Report", type="primary"):
                with st.spinner("Generating report…"):
                    try:
                        from openai import OpenAI
                        _client = OpenAI(base_url=qwen_url, api_key=qwen_key)
                        _resp = _client.chat.completions.create(
                            model="Qwen/Qwen3-32B",
                            messages=[
                                {"role": "system", "content": _system_prompt},
                                {"role": "user",   "content": _user_prompt},
                            ],
                            max_tokens=1400,
                            temperature=0.7,
                            extra_body={"enable_thinking": False},
                        )
                        _raw = _resp.choices[0].message.content
                        st.session_state["ai_report"] = _strip_think(_raw)
                        st.rerun()
                    except Exception as _e:
                        st.error(f"AI generation failed: {_e}")

        if "ai_report" in st.session_state:
            st.markdown(st.session_state["ai_report"])

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            _rc, _ = st.columns([1.5, 7])
            with _rc:
                if st.button("↺ Regenerate", use_container_width=True):
                    del st.session_state["ai_report"]
                    st.rerun()

    _nav(2, None, back_label="← Step 3")

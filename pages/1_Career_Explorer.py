"""YF — Career Exploration Application.

Queries Statistics Canada WDS REST API directly (no CSV downloads)
to display employment statistics and job market prospects.

Multi-page wizard: Page 1 collects user profile & matches field of study,
Page 2 shows the analysis tabs, Page 3 provides deep career analysis.
"""

import traceback

import pandas as pd
import streamlit as st

# Clear any stale cached data from previous code versions
st.cache_data.clear()

from config import FIELD_OPTIONS, EDUCATION_OPTIONS, GEO_OPTIONS
from cip_codes import CIP_TO_BROAD, CIP_SERIES, CIP_SUBSERIES, CIP_CODES
from field_matcher import match_fields, resolve_subfield
from processors import (
    fetch_cip_employment_distribution,
    fetch_graduate_outcomes,
    fetch_income,
    fetch_job_vacancies,
    fetch_labour_force,
    fetch_noc_distribution,
    fetch_noc_gender_breakdown,
    fetch_noc_income_for_quadrant,
    fetch_subfield_comparison,
    fetch_unemployment_trends,
)
from charts import (
    cip_growth_bar,
    cip_income_comparison_bar,
    cip_subfield_income_bar,
    education_comparison_grouped,
    employment_rate_bar,
    graduate_income_trajectory,
    income_by_education_line,
    income_ranking_bar,
    job_vacancy_dual_axis,
    noc_detail_bar,
    noc_distribution_donut,
    noc_distribution_bar,
    noc_quadrant_bubble,
    noc_submajor_bar,
    radar_overview,
    unemployment_trend_lines,
    holland_radar_chart,
)
from oasis_client import (
    fetch_oasis_matches, fetch_noc_description, fetch_noc_unit_profile,
    fetch_jobbank_skills, fetch_jobbank_wages,
    HOLLAND_CODES, HOLLAND_DESCRIPTIONS,
)
from analysis_engine import run_all_analyses
from holland_interpreter import (
    compute_rule_outputs, stream_interpretation, fetch_noc_matches_for_interpretation,
    DIMENSION_CN, RIASEC_ORDER as HC_RIASEC_ORDER,
)
from analysis_charts import (
    composite_score_gauge,
    component_radar,
    unemployment_forecast_chart,
    vacancy_forecast_chart,
    income_projection_chart,
    risk_assessment_chart,
    education_roi_waterfall,
    break_even_timeline,
    career_quadrant_chart,
    subfield_quadrant_chart,
)
from styles import GLOBAL_CSS

st.set_page_config(
    page_title="YF \u2014 Career Exploration",
    page_icon="\u2B50",
    layout="wide",
)

# Inject global modern styles
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


# ── Page 1: User Profile & Field Matching ─────────────────────────


def render_profile_page():
    st.title("YF \u2014 Career Exploration")
    st.caption("Step 1: Tell us about yourself")

    # ── Personal info ─────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        user_name = st.text_input(
            "Name",
            value=st.session_state.get("user_name", ""),
        )
    with col2:
        user_age = st.slider(
            "Age",
            min_value=16,
            max_value=70,
            value=st.session_state.get("user_age", 25),
        )

    col3, col4 = st.columns(2)
    with col3:
        gender_options = ["Male", "Female", "Other"]
        gender_idx = 0
        saved_gender = st.session_state.get("user_gender")
        if saved_gender in gender_options:
            gender_idx = gender_options.index(saved_gender)
        user_gender = st.selectbox("Gender", gender_options, index=gender_idx)
    with col4:
        edu_keys = list(EDUCATION_OPTIONS.keys())
        edu_idx = 0
        saved_edu = st.session_state.get("education")
        if saved_edu in edu_keys:
            edu_idx = edu_keys.index(saved_edu)
        education = st.selectbox("Education Level", edu_keys, index=edu_idx)

    geo_idx = 0
    saved_geo = st.session_state.get("geo")
    if saved_geo in GEO_OPTIONS:
        geo_idx = GEO_OPTIONS.index(saved_geo)
    geo = st.selectbox("Province / Territory", GEO_OPTIONS, index=geo_idx)

    st.divider()

    # ── Field of study search ─────────────────────────────────
    st.subheader("Field of Study")

    # If Browse was just used, clear the search box
    if st.session_state.pop("_clear_search", False):
        _query_default = ""
    else:
        _query_default = st.session_state.get("_field_query", "")

    query = st.text_input(
        "Search by keyword or CIP code (e.g. 'computer science', '14.08')",
        value=_query_default,
        key="field_query",
    )

    broad_field = st.session_state.get("broad_field")
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")

    if query:
        matches = match_fields(query, FIELD_OPTIONS)
        if matches:
            options = [m["display_name"] for m in matches]
            # Pre-select if user already chose one
            preselect = 0
            saved_display = st.session_state.get("_selected_display")
            if saved_display in options:
                preselect = options.index(saved_display)

            choice = st.radio(
                "Select your field:",
                options,
                index=preselect,
                key="field_radio",
            )
            selected = matches[options.index(choice)]
            broad_field = selected["broad_field"]
            subfield = selected["subfield"]
            cip_code = selected.get("cip_code")
            cip_name = selected.get("cip_name")

            # Show fallback info when CIP has no exact subfield data
            if cip_code and not subfield:
                st.caption(
                    f"CIP {cip_code} has no dedicated statistics — "
                    f"analysis will use the broad category: {broad_field}"
                )
            elif cip_code and subfield and not subfield.startswith(cip_code):
                st.caption(
                    f"CIP {cip_code} mapped to nearest available data: {subfield}"
                )
        else:
            st.warning("No matches found. Try a different keyword or browse below.")
            broad_field = None
            subfield = None
            cip_code = None
            cip_name = None

    # Fallback: browse all fields (3-level CIP hierarchy)
    with st.expander("Browse all fields"):
        # ── Level 1: Broad field ──
        broad_fields = list(FIELD_OPTIONS.keys())
        browse_idx = 0
        if broad_field in broad_fields:
            browse_idx = broad_fields.index(broad_field)
        browse_broad = st.selectbox(
            "Broad field",
            broad_fields,
            index=browse_idx,
            key="browse_broad",
        )

        # ── Level 2: CIP series (2-digit) that map to this broad field ──
        series_for_broad = sorted(
            code for code, bf in CIP_TO_BROAD.items() if bf == browse_broad
        )
        series_options = {
            code: f"{code}. {CIP_SERIES.get(code, code)}"
            for code in series_for_broad
            if code in CIP_SERIES
        }
        if series_options:
            series_labels = ["(All series)"] + list(series_options.values())
            series_choice = st.selectbox(
                "Series (2-digit CIP)",
                series_labels,
                key="browse_series",
            )
            chosen_series = None
            if series_choice != "(All series)":
                # reverse lookup code from label
                for code, label in series_options.items():
                    if label == series_choice:
                        chosen_series = code
                        break
        else:
            chosen_series = None

        # ── Level 3: Subseries (4-digit) under chosen series ──
        chosen_subseries = None
        if chosen_series:
            subs_for_series = sorted(
                (code, name)
                for code, name in CIP_SUBSERIES.items()
                if code.startswith(chosen_series + ".")
            )
            if subs_for_series:
                sub4_labels = ["(All subseries)"] + [
                    f"{code} {name}" for code, name in subs_for_series
                ]
                sub4_choice = st.selectbox(
                    "Subseries (4-digit CIP)",
                    sub4_labels,
                    key="browse_sub4",
                )
                if sub4_choice != "(All subseries)":
                    chosen_subseries = sub4_choice.split(" ", 1)[0]

        # ── Level 4: Class (6-digit) under chosen subseries ──
        chosen_class = None
        if chosen_subseries:
            classes_for_sub = sorted(
                (code, name)
                for code, name in CIP_CODES.items()
                if code.startswith(chosen_subseries)
            )
            if classes_for_sub:
                cls_labels = ["(All programs)"] + [
                    f"{code} {name}" for code, name in classes_for_sub
                ]
                cls_choice = st.selectbox(
                    "Program (6-digit CIP)",
                    cls_labels,
                    key="browse_cls6",
                )
                if cls_choice != "(All programs)":
                    chosen_class = cls_choice.split(" ", 1)[0]

        if st.button("Use this field", key="use_browse"):
            _bf = browse_broad
            _sf = None
            _cc = None
            _cn = None
            if chosen_class:
                _cc = chosen_class
                _cn = CIP_CODES.get(chosen_class, "")
                _sf, _bf = resolve_subfield(_cc, browse_broad, FIELD_OPTIONS)
            elif chosen_subseries:
                general_code = chosen_subseries + "00"
                if general_code in CIP_CODES:
                    _cc = general_code
                    _cn = CIP_CODES[general_code]
                else:
                    first = sorted(
                        c for c in CIP_CODES if c.startswith(chosen_subseries)
                    )
                    _cc = first[0] if first else None
                    _cn = CIP_CODES.get(_cc, "") if _cc else None
                if _cc:
                    _sf, _bf = resolve_subfield(_cc, browse_broad, FIELD_OPTIONS)
            # Persist immediately so values survive the next rerun
            st.session_state["broad_field"] = _bf
            st.session_state["subfield"] = _sf
            st.session_state["cip_code"] = _cc
            st.session_state["cip_name"] = _cn
            st.session_state["_field_query"] = ""
            st.session_state["_clear_search"] = True
            st.rerun()

    st.divider()

    # ── Confirm ───────────────────────────────────────────────
    if broad_field:
        if cip_code and cip_name:
            st.info(
                f"**CIP {cip_code}** — {cip_name}\n\n"
                f"Broad field: {broad_field}"
                + (f"  |  Data source: {subfield}" if subfield else "")
            )
        else:
            field_display = subfield or broad_field
            st.info(f"Selected field: **{field_display}**")
    else:
        st.warning("Please search or browse to select a field of study.")

    can_proceed = bool(broad_field)

    # CIP Employment Distribution button
    col_btn1, _ = st.columns([2, 1])
    with col_btn1:
        if st.button(
            "View Graduate Employment Distribution",
            use_container_width=True,
            disabled=not can_proceed,
            help="View 2yr and 5yr post-graduation income distribution for your CIP field",
        ):
            st.session_state["user_name"] = user_name
            st.session_state["user_age"] = user_age
            st.session_state["user_gender"] = user_gender
            st.session_state["broad_field"] = broad_field
            st.session_state["subfield"] = subfield
            st.session_state["cip_code"] = cip_code
            st.session_state["cip_name"] = cip_name
            st.session_state["education"] = education
            st.session_state["geo"] = geo
            st.session_state["_field_query"] = query
            st.session_state["wizard_page"] = "cip_distribution"
            st.rerun()

    st.divider()

    if st.button(
        "Confirm & View Analysis",
        type="primary",
        use_container_width=True,
        disabled=not can_proceed,
    ):
        st.session_state["user_name"] = user_name
        st.session_state["user_age"] = user_age
        st.session_state["user_gender"] = user_gender
        st.session_state["broad_field"] = broad_field
        st.session_state["subfield"] = subfield
        st.session_state["cip_code"] = cip_code
        st.session_state["cip_name"] = cip_name
        st.session_state["education"] = education
        st.session_state["geo"] = geo
        st.session_state["_field_query"] = query
        # Store the radio display_name so it can be re-selected on page revisit
        if query:
            _matches = match_fields(query, FIELD_OPTIONS)
            _opts = [m["display_name"] for m in _matches]
            for m in _matches:
                if m["broad_field"] == broad_field and m["subfield"] == subfield:
                    st.session_state["_selected_display"] = m["display_name"]
                    break
            else:
                st.session_state["_selected_display"] = (
                    f"{subfield}  ({broad_field})" if subfield else broad_field
                )
        else:
            st.session_state["_selected_display"] = (
                f"{subfield}  ({broad_field})" if subfield else broad_field
            )
        st.session_state["wizard_page"] = "analysis"
        st.rerun()


# ── Page 2: Analysis ──────────────────────────────────────────────


def _scroll_to_top():
    """Inject JS to scroll the main content area to the top."""
    st.components.v1.html(
        """<script>
        window.parent.document.querySelector('section.main').scrollTo(0, 0);
        </script>""",
        height=0,
    )


def render_analysis_page():
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    # Initialize page2_data cache for deep analysis
    page2_data = st.session_state.get("page2_data", {})

    # ── Sidebar: user summary + edit button ───────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Edit Profile", use_container_width=True):
            st.session_state["wizard_page"] = "profile"
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_analysis"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("analysis")

    # ── Fixed header: title + navigation ─────────────────────
    sections = [
        ("sect-employment", "Employment Overview"),
        ("sect-income", "Income Analysis"),
        ("sect-unemployment", "Unemployment Trends"),
        ("sect-jobs", "Job Market"),
        ("sect-graduates", "Graduate Outcomes"),
    ]

    nav_links = "".join(
        f'<a href="#{sid}">{label}</a>'
        for sid, label in sections
    )

    st.markdown(
        '<div id="yf-header">'
        '  <h1>YF \u2014 Career Exploration</h1>'
        '  <p class="caption">'
        "Powered by Statistics Canada open data (live API queries)</p>"
        f'  <div class="nav">{nav_links}</div>'
        "</div>"
        '<div style="height:160px"></div>',
        unsafe_allow_html=True,
    )

    # ── Section 1: Employment Overview ────────────────────────
    st.markdown('<div id="sect-employment"></div>', unsafe_allow_html=True)
    st.header("Employment Overview")
    try:
        with st.spinner("Querying employment data..."):
            result = fetch_labour_force(broad_field, subfield, education, geo)
        page2_data["labour_force"] = result

        summary = result["summary"]
        col1, col2, col3 = st.columns(3)
        col1.metric("Employment Rate", f"{summary.get('employment_rate', 'N/A')}%")
        col2.metric("Participation Rate", f"{summary.get('participation_rate', 'N/A')}%")
        col3.metric("Unemployment Rate", f"{summary.get('unemployment_rate', 'N/A')}%")

        chart_col1, chart_col2 = st.columns([3, 2])
        with chart_col1:
            st.plotly_chart(
                employment_rate_bar(result["comparison"], field_display),
                use_container_width=True,
            )
        with chart_col2:
            st.plotly_chart(
                education_comparison_grouped(summary, education),
                use_container_width=True,
            )

        emp_rate = summary.get("employment_rate", 50)
        unemp_rate = summary.get("unemployment_rate", 10)
        st.plotly_chart(
            radar_overview(
                employment_rate=min(emp_rate, 100),
                income_percentile=50,
                low_unemployment=max(0, 100 - unemp_rate * 5),
                vacancy_score=50,
                income_growth=50,
            ),
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error loading employment data: {e}")
        st.code(traceback.format_exc())

    st.divider()

    # ── Section 2: Income Analysis ────────────────────────────
    st.markdown('<div id="sect-income"></div>', unsafe_allow_html=True)
    st.header("Income Analysis")
    try:
        with st.spinner("Querying income data..."):
            result = fetch_income(broad_field, subfield, education, geo)
        page2_data["income"] = result

        summary = result["summary"]
        col1, col2 = st.columns(2)
        median = summary.get("median_income")
        avg = summary.get("average_income")
        col1.metric("Median Income", f"${median:,.0f}" if median else "N/A")
        col2.metric("Average Income", f"${avg:,.0f}" if avg else "N/A")

        chart_col1, chart_col2 = st.columns([3, 2])
        with chart_col1:
            st.plotly_chart(
                income_ranking_bar(result["ranking"], field_display),
                use_container_width=True,
            )
        with chart_col2:
            st.plotly_chart(
                income_by_education_line(result["by_education"], field_display),
                use_container_width=True,
            )
    except Exception as e:
        st.error(f"Error loading income data: {e}")
        st.code(traceback.format_exc())

    st.divider()

    # ── Section 3: Unemployment Trends ────────────────────────
    st.markdown('<div id="sect-unemployment"></div>', unsafe_allow_html=True)
    st.header("Unemployment Trends")
    try:
        with st.spinner("Querying unemployment trends..."):
            result = fetch_unemployment_trends(education, geo)
        page2_data["unemployment"] = result

        summary = result["summary"]
        col1, col2 = st.columns(2)
        col1.metric("Current Rate", f"{summary.get('current_rate', 'N/A')}%")
        col2.metric("5-Year Average", f"{summary.get('five_yr_avg', 'N/A')}%")

        st.plotly_chart(
            unemployment_trend_lines(result["trends"], education),
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error loading unemployment trends: {e}")
        st.code(traceback.format_exc())

    st.divider()

    # ── Section 4: Job Market ─────────────────────────────────
    st.markdown('<div id="sect-jobs"></div>', unsafe_allow_html=True)
    st.header("Job Market")
    try:
        with st.spinner("Querying job market data..."):
            result = fetch_job_vacancies(education, geo)
        page2_data["job_vacancies"] = result

        summary = result["summary"]
        col1, col2 = st.columns(2)
        vac = summary.get("vacancies")
        wage = summary.get("avg_wage")
        col1.metric("Latest Vacancies", f"{vac:,}" if vac else "N/A")
        col2.metric("Avg Offered Wage", f"${wage:,.2f}/hr" if wage else "N/A")

        st.plotly_chart(
            job_vacancy_dual_axis(result["trends"]),
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error loading job market data: {e}")
        st.code(traceback.format_exc())

    st.divider()

    # ── Section 5: Graduate Outcomes ──────────────────────────
    st.markdown('<div id="sect-graduates"></div>', unsafe_allow_html=True)
    st.header("Graduate Outcomes")
    try:
        with st.spinner("Querying graduate outcomes..."):
            result = fetch_graduate_outcomes(broad_field, education, geo)
        page2_data["graduate_outcomes"] = result

        summary = result["summary"]
        col1, col2, col3 = st.columns(3)
        inc2 = summary.get("income_2yr")
        inc5 = summary.get("income_5yr")
        growth = summary.get("growth_pct")
        col1.metric("Income (2yr after)", f"${inc2:,.0f}" if inc2 else "N/A")
        col2.metric("Income (5yr after)", f"${inc5:,.0f}" if inc5 else "N/A")
        col3.metric("Growth", f"{growth:+.1f}%" if growth else "N/A")

        st.plotly_chart(
            graduate_income_trajectory(result["trajectory"]),
            use_container_width=True,
        )
    except Exception as e:
        st.error(f"Error loading graduate outcomes: {e}")
        st.code(traceback.format_exc())

    # Fetch subfield comparison data (silent — no visible section on Page 2)
    try:
        sf_result = fetch_subfield_comparison(broad_field, subfield, education, geo)
        page2_data["subfield_comparison"] = sf_result
    except Exception:
        pass

    # Cache page2_data for deep analysis
    st.session_state["page2_data"] = page2_data

    # Deep Analysis CTA
    st.divider()
    st.markdown(
        '<div class="yf-cta">'
        '<h3>Ready for deeper insights?</h3>'
        '<p>Composite scoring, trend forecasting, income projections, risk assessment, and education ROI</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    if st.button(
        "Launch Deep Career Analysis",
        type="primary",
        use_container_width=True,
    ):
        st.session_state["wizard_page"] = "deep_analysis"
        st.rerun()

    # Footer
    st.divider()
    st.markdown(
        '<div class="yf-footer">Data source: Statistics Canada WDS REST API. '
        'Data is queried in real-time. Results are cached for 1 hour.</div>',
        unsafe_allow_html=True,
    )


# ── Page 3: Deep Career Analysis ─────────────────────────────────


def render_deep_analysis_page():
    _scroll_to_top()

    page2_data = st.session_state.get("page2_data", {})
    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    if not page2_data:
        st.warning("No data available. Please run the basic analysis first.")
        if st.button("Back to Analysis"):
            st.session_state["wizard_page"] = "analysis"
            st.rerun()
        return

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Back to Overview", use_container_width=True):
            st.session_state["wizard_page"] = "analysis"
            st.rerun()
        if st.button("Edit Profile", use_container_width=True, key="deep_edit"):
            st.session_state["wizard_page"] = "profile"
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_deep"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("deep")

    # ── Run analysis ──────────────────────────────────────────
    with st.spinner("Running deep analysis algorithms..."):
        results = run_all_analyses(page2_data)

    # ── Fixed header ──────────────────────────────────────────
    sections = [
        ("deep-score", "Prospect Score"),
        ("deep-quadrant", "Career Quadrant"),
        ("deep-subfield", "Subfield Quadrant"),
        ("deep-forecast", "Trend Forecast"),
        ("deep-income", "Income Projection"),
        ("deep-risk", "Risk Assessment"),
        ("deep-roi", "Education ROI"),
        ("deep-compete", "Competitiveness"),
    ]

    nav_links = "".join(
        f'<a href="#{sid}">{label}</a>'
        for sid, label in sections
    )
    st.markdown(
        '<div id="yf-header">'
        '  <h1>YF — Deep Career Analysis</h1>'
        '  <p class="caption">'
        f"Advanced analysis for: {field_display} | {education} | {geo}</p>"
        f'  <div class="nav">{nav_links}</div>'
        "</div>"
        '<div style="height:160px"></div>',
        unsafe_allow_html=True,
    )

    # ── Section 1: Composite Career Prospect Score ────────────
    st.markdown('<div id="deep-score"></div>', unsafe_allow_html=True)
    st.header("Career Prospect Score")
    score = results["composite_score"]
    col1, col2 = st.columns([1, 1])
    with col1:
        st.plotly_chart(composite_score_gauge(score), use_container_width=True)
    with col2:
        st.plotly_chart(component_radar(score), use_container_width=True)

    # Component breakdown
    components = score.get("components", {})
    cols = st.columns(len(components))
    for col, (name, val) in zip(cols, components.items()):
        col.metric(name, f"{val:.0f}/100")

    st.divider()

    # ── Section 2: Career Quadrant ────────────────────────────
    st.markdown('<div id="deep-quadrant"></div>', unsafe_allow_html=True)
    st.header("Career Quadrant — Employability vs Income")
    quadrant = results["career_quadrant"]
    if "error" not in quadrant:
        st.plotly_chart(career_quadrant_chart(quadrant), use_container_width=True)

        uq = quadrant.get("user_quadrant", "N/A")
        if "High Employability + High Income" in uq:
            st.success(f"**Your field:** {uq} — strong on both dimensions.")
        elif "High Income" in uq:
            st.info(f"**Your field:** {uq} — competitive entry but rewarding earnings.")
        elif "Accessible" in uq:
            st.info(f"**Your field:** {uq} — good job availability, room for income growth.")
        else:
            st.warning(f"**Your field:** {uq} — consider strategies to strengthen prospects.")

        st.caption(
            "Each dot is a field of study. The dashed lines split at the median across all fields. "
            "Your field is marked with a star."
        )
    else:
        st.warning(quadrant["error"])

    st.divider()

    # ── Section 2b: Subfield Quadrant ─────────────────────────
    st.markdown('<div id="deep-subfield"></div>', unsafe_allow_html=True)
    sf_quad = results["subfield_quadrant"]
    if "error" not in sf_quad:
        sf_broad = sf_quad.get("broad_field", broad_field)
        st.header(f"Within-Field Comparison — {sf_broad}")
        st.plotly_chart(subfield_quadrant_chart(sf_quad), use_container_width=True)

        sf_uq = sf_quad.get("user_quadrant", "N/A")
        if sf_uq != "N/A":
            if "High Employability + High Income" in sf_uq:
                st.success(f"**Among peers:** {sf_uq} — top subfield in your category.")
            elif "High Income" in sf_uq:
                st.info(f"**Among peers:** {sf_uq} — high earning but competitive entry.")
            elif "Accessible" in sf_uq:
                st.info(f"**Among peers:** {sf_uq} — easier entry, consider specialization for higher income.")
            else:
                st.warning(f"**Among peers:** {sf_uq} — may benefit from complementary skills or pivoting.")

        notes = []
        if sf_quad.get("has_estimated_emp"):
            notes.append(
                "Diamond markers indicate subfields where employment rate is estimated "
                "from a parent CIP category (exact data not available)."
            )
        notes.append(
            "Dashed lines split at the median of subfields within this broad field."
        )
        st.caption(" ".join(notes))
    else:
        st.header(f"Within-Field Comparison — {broad_field}")
        st.info(sf_quad["error"])

    st.divider()

    # ── Section 3: Trend Forecasts ────────────────────────────
    st.markdown('<div id="deep-forecast"></div>', unsafe_allow_html=True)
    st.header("Trend Forecasts")

    unemp_fc = results["unemployment_forecast"]
    vac_fc = results["vacancy_forecast"]

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(unemployment_forecast_chart(unemp_fc), use_container_width=True)
        if "interpretation" in unemp_fc:
            st.info(f"**Unemployment:** {unemp_fc['interpretation']}")
    with col2:
        st.plotly_chart(vacancy_forecast_chart(vac_fc), use_container_width=True)
        if "interpretation" in vac_fc:
            st.info(f"**Vacancies:** {vac_fc['interpretation']}")

    st.divider()

    # ── Section 3: Income Growth Projection ───────────────────
    st.markdown('<div id="deep-income"></div>', unsafe_allow_html=True)
    st.header("Income Growth Projection")
    proj = results["income_projection"]
    if "error" not in proj:
        st.plotly_chart(income_projection_chart(proj), use_container_width=True)

        col1, col2, col3 = st.columns(3)
        dp = proj["data_points"]
        pp = proj["projected_points"]
        col1.metric("2yr Actual", f"${dp[0]['income']:,.0f}")
        col2.metric("5yr Actual", f"${dp[1]['income']:,.0f}")
        col3.metric(
            "10yr Projected",
            f"${pp[0]['income']:,.0f}",
            delta=f"+${pp[0]['income'] - dp[1]['income']:,.0f} from 5yr",
        )

        formula = proj["formula"]
        st.caption(
            f"Model: income = {formula['a']:,.2f} * ln(year) + {formula['b']:,.2f}"
        )
    else:
        st.warning(proj["error"])

    st.divider()

    # ── Section 4: Risk Assessment ────────────────────────────
    st.markdown('<div id="deep-risk"></div>', unsafe_allow_html=True)
    st.header("Career Stability & Risk Assessment")
    risk = results["risk_assessment"]
    st.plotly_chart(risk_assessment_chart(risk), use_container_width=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Volatility (CV%)", f"{risk['volatility_cv']:.1f}%" if risk.get("volatility_cv") is not None else "N/A")
    col2.metric("Income Symmetry", f"{risk['income_symmetry']:.3f}" if risk.get("income_symmetry") is not None else "N/A")
    col3.metric("Overall Stability", risk.get("overall_grade", "N/A"))

    st.info(risk.get("interpretation", ""))

    st.divider()

    # ── Section 5: Education ROI ──────────────────────────────
    st.markdown('<div id="deep-roi"></div>', unsafe_allow_html=True)
    st.header("Education ROI Analysis")
    roi = results["education_roi"]
    if "error" not in roi:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(education_roi_waterfall(roi), use_container_width=True)
        with col2:
            st.plotly_chart(break_even_timeline(roi), use_container_width=True)

        # Best ROI highlight
        best = roi.get("best_roi")
        if best:
            st.success(
                f"**Best ROI:** {best['from_level']} to {best['to_level']} — "
                f"${best['income_premium']:,.0f}/yr premium, "
                f"break-even in {best['break_even_years']:.1f} years"
            )

        # Detail table
        with st.expander("ROI Details"):
            for level in roi["levels"]:
                st.write(
                    f"**{level['from_level']} -> {level['to_level']}**: "
                    f"Premium ${level['income_premium']:,.0f}/yr ({level['premium_pct']:+.1f}%), "
                    f"Cost ${level['total_cost']:,.0f} over {level['duration_years']}yr, "
                    f"Break-even: {level['break_even_years']:.1f}yr" if level['break_even_years'] else
                    f"**{level['from_level']} -> {level['to_level']}**: "
                    f"No positive return"
                )
    else:
        st.warning(roi["error"])

    st.divider()

    # ── Section 6: Field Competitiveness ──────────────────────
    st.markdown('<div id="deep-compete"></div>', unsafe_allow_html=True)
    st.header("Field Competitiveness")
    compete = results["field_competitiveness"]
    if "error" not in compete:
        col1, col2, col3 = st.columns(3)
        col1.metric(
            "Employment Rank",
            f"#{compete['employment_rank']}" if compete.get("employment_rank") else "N/A",
            delta=compete.get("emp_quartile"),
        )
        col2.metric(
            "Income Rank",
            f"#{compete['income_rank']}" if compete.get("income_rank") else "N/A",
            delta=compete.get("inc_quartile"),
        )
        col3.metric("Total Fields", compete.get("total_fields", "N/A"))

        if compete.get("strengths"):
            st.success("**Strengths:** " + ", ".join(compete["strengths"]))
        if compete.get("weaknesses"):
            st.warning("**Weaknesses:** " + ", ".join(compete["weaknesses"]))
        if not compete.get("strengths") and not compete.get("weaknesses"):
            st.info("Your field ranks in the middle range across all metrics.")

        # Rankings table
        with st.expander("Full Field Rankings"):
            for i, fr in enumerate(compete["field_rankings"], 1):
                emp = f"{fr['employment_rate']:.1f}%" if fr.get("employment_rate") is not None else "N/A"
                inc = f"${fr['median_income']:,.0f}" if fr.get("median_income") is not None else "N/A"
                st.write(f"{i}. **{fr['field']}** — Employment: {emp}, Income: {inc}")
    else:
        st.warning(compete["error"])

    # Footer
    st.divider()
    st.markdown(
        '<div class="yf-footer">Deep analysis powered by algorithmic models applied to Statistics Canada data. '
        'Projections are estimates based on historical trends and should not be taken as guarantees.</div>',
        unsafe_allow_html=True,
    )


# ── Page: CIP Employment Distribution ─────────────────────────────


def render_cip_distribution_page():
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Back to Profile", use_container_width=True):
            st.session_state["wizard_page"] = "profile"
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_cip"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("cip")

    # ── Header ─────────────────────────────────────────────────
    st.markdown(
        '<div id="yf-header">'
        '  <h1>YF — Graduate Employment Distribution</h1>'
        '  <p class="caption">'
        "Employment income, occupation direction (NOC), and proportions after graduation</p>"
        '  <div class="nav">'
        '    <a href="#sect-overview">Overview</a>'
        '    <a href="#sect-noc">Occupation (NOC)</a>'
        '    <a href="#sect-noc-detail">NOC Groups</a>'
        '    <a href="#sect-noc-specific">Specific Jobs</a>'
        '    <a href="#sect-quadrant">Quadrant</a>'
        '    <a href="#sect-broad">Income by Field</a>'
        '    <a href="#sect-subfield">Sub-fields</a>'
        '    <a href="#sect-growth">Growth Rate</a>'
        '  </div>'
        "</div>"
        '<div style="height:160px"></div>',
        unsafe_allow_html=True,
    )

    # Fetch both datasets
    try:
        with st.spinner("Querying graduate employment distribution data..."):
            result = fetch_cip_employment_distribution(cip_code, broad_field, education, geo)
    except Exception as e:
        st.error(f"Error loading CIP employment distribution: {e}")
        st.code(traceback.format_exc())
        return

    try:
        with st.spinner("Querying occupation (NOC) distribution data..."):
            noc_result = fetch_noc_distribution(cip_code, broad_field, education, geo)
    except Exception as e:
        st.error(f"Error loading NOC distribution: {e}")
        if st.button("Clear cache and retry", key="cip_retry_noc"):
            st.cache_data.clear()
            st.rerun()
        noc_result = None

    user_summary = result["user_summary"]
    user_field_name = result["user_field_name"]

    # ── OaSIS Interest Match Summary ──────────────────────────
    oasis_result = st.session_state.get("oasis_result")
    oasis_noc_set = set()
    if oasis_result and oasis_result.get("success") and oasis_result.get("noc_codes"):
        oasis_noc_set = set(oasis_result["noc_codes"])

        # Find overlapping NOCs between OaSIS results and CIP distribution
        if noc_result and noc_result.get("detail_distribution"):
            cip_noc_codes = set()
            for occ in noc_result["detail_distribution"]:
                code = occ["noc"].split(" ", 1)[0]
                cip_noc_codes.add(code)
            overlap = oasis_noc_set & cip_noc_codes

            if overlap:
                # Build display names for overlapping NOCs
                overlap_names = []
                for occ in noc_result["detail_distribution"]:
                    code = occ["noc"].split(" ", 1)[0]
                    if code in overlap:
                        overlap_names.append(occ["noc"])
                i1 = st.session_state.get("oasis_interest_1", "")
                i2 = st.session_state.get("oasis_interest_2", "")
                i3 = st.session_state.get("oasis_interest_3", "")
                match_items = "".join(f"<li>{n}</li>" for n in overlap_names)
                st.markdown(
                    f'<div class="yf-oasis-banner">'
                    f'<h4>OaSIS Interest Match Found!</h4>'
                    f'<p>Your interest profile ({i1} &gt; {i2} &gt; {i3}) aligns with '
                    f'<strong>{len(overlap)}</strong> occupation(s) that graduates in your field actually enter:</p>'
                    f'<ul>{match_items}</ul>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                i1 = st.session_state.get("oasis_interest_1", "")
                i2 = st.session_state.get("oasis_interest_2", "")
                i3 = st.session_state.get("oasis_interest_3", "")
                st.info(
                    f"**OaSIS Interest Search** ({i1} > {i2} > {i3}): "
                    f"Found {len(oasis_noc_set)} matching occupations, "
                    f"but none overlap with the top occupations for this field of study. "
                    f"The matched occupations are highlighted with \u2605 if they appear in the charts below."
                )
    elif oasis_result and not oasis_result.get("success"):
        st.warning(
            f"OaSIS interest search could not be completed: {oasis_result.get('error', 'Unknown error')}. "
            "Charts will display without interest highlights."
        )

    # ── Section: Overview ──────────────────────────────────────
    st.markdown('<div id="sect-overview"></div>', unsafe_allow_html=True)
    st.header("Your Field — Graduate Income Overview")

    if cip_code and cip_name:
        st.info(f"**CIP {cip_code}** — {cip_name}  →  Data mapped to: **{user_field_name}**")

    col1, col2, col3, col4 = st.columns(4)
    inc2 = user_summary.get("income_2yr")
    inc5 = user_summary.get("income_5yr")
    growth = user_summary.get("growth_pct")
    grad_count = user_summary.get("graduate_count")
    col1.metric("Income (2yr after)", f"${inc2:,.0f}" if inc2 else "N/A")
    col2.metric("Income (5yr after)", f"${inc5:,.0f}" if inc5 else "N/A")
    col3.metric("Growth (2yr→5yr)", f"{growth:+.1f}%" if growth is not None else "N/A")
    col4.metric("Graduate Count", f"{grad_count:,}" if grad_count else "N/A")

    st.divider()

    # ── Section: NOC Occupation Distribution ───────────────────
    st.markdown('<div id="sect-noc"></div>', unsafe_allow_html=True)
    st.header("Employment Direction — Occupation (NOC) Distribution")
    st.caption(
        "Where do graduates with this field of study actually work? "
        "This shows the distribution across NOC (National Occupational Classification) "
        "broad categories, based on 2021 Census data."
    )

    if noc_result and noc_result["broad_distribution"]:
        col_chart1, col_chart2 = st.columns([2, 3])
        with col_chart1:
            st.plotly_chart(
                noc_distribution_donut(noc_result["broad_distribution"]),
                use_container_width=True,
            )
            st.caption("Hover over slices for detailed breakdowns.")
        with col_chart2:
            st.plotly_chart(
                noc_distribution_bar(noc_result["broad_distribution"]),
                use_container_width=True,
            )

        # Show top 3 occupations as callouts
        top3 = noc_result["broad_distribution"][:3]
        cols = st.columns(len(top3))
        for col, occ in zip(cols, top3):
            cnt_str = f" ({occ['count']:,} people)" if occ.get("count") else ""
            col.metric(occ["noc"], f"{occ['percentage']:.1f}%", delta=cnt_str)

        # Not applicable info
        na_pct = noc_result.get("not_applicable_pct")
        if na_pct and na_pct > 0:
            na_cnt = noc_result.get("not_applicable_count")
            na_detail = f" ({na_cnt:,} people)" if na_cnt else ""
            st.caption(
                f"Note: {na_pct:.1f}% of graduates had no occupation classification{na_detail} "
                "(e.g., not in labour force, students, etc.)"
            )
    else:
        st.warning("No occupation distribution data available.")

    st.divider()

    # ── Section: NOC Detailed Sub-groups ───────────────────────
    st.markdown('<div id="sect-noc-detail"></div>', unsafe_allow_html=True)
    st.header("Detailed Occupation Groups (NOC 2-digit)")
    st.caption(
        "More granular breakdown of the top occupation sub-groups "
        "where graduates in this field are employed."
    )

    if noc_result and noc_result["submajor_distribution"]:
        st.plotly_chart(
            noc_submajor_bar(noc_result["submajor_distribution"]),
            use_container_width=True,
        )

        # Show full table in expander
        with st.expander("View all occupation groups"):
            for i, occ in enumerate(noc_result["submajor_distribution"], 1):
                cnt_str = f" — {occ['count']:,} people" if occ.get("count") else ""
                st.write(f"{i}. **{occ['noc']}**: {occ['percentage']:.1f}%{cnt_str}")
    else:
        st.info("No detailed occupation group data available.")

    st.divider()

    # ── Section: NOC 5-digit Specific Occupations ──────────────
    st.markdown('<div id="sect-noc-specific"></div>', unsafe_allow_html=True)
    st.header("Specific Occupations (NOC 5-digit)")
    st.caption(
        "The most specific occupation titles where graduates in this field work. "
        "Shows the top occupations with their NOC 2021 codes and proportions."
    )

    if noc_result and noc_result.get("detail_distribution"):
        st.plotly_chart(
            noc_detail_bar(noc_result["detail_distribution"], oasis_noc_set=oasis_noc_set),
            use_container_width=True,
        )

        # Show full table in expander
        with st.expander("View all specific occupations"):
            for i, occ in enumerate(noc_result["detail_distribution"], 1):
                code = occ["noc"].split(" ", 1)[0]
                oasis_marker = " \u2605 **OaSIS Match**" if code in oasis_noc_set else ""
                cnt_str = f" — {occ['count']:,} people" if occ.get("count") else ""
                st.write(f"{i}. **{occ['noc']}**: {occ['percentage']:.1f}%{cnt_str}{oasis_marker}")
    else:
        st.info("No specific occupation data available.")

    st.divider()

    # ── Section: Quadrant Bubble Chart ─────────────────────────
    st.markdown('<div id="sect-quadrant"></div>', unsafe_allow_html=True)
    st.header("Occupation Quadrant — Employment Count vs Income")
    st.caption(
        "Each bubble represents a specific occupation (5-digit NOC). "
        "X-axis: employment count (more people → further right). "
        "Y-axis: median income for age 25-64 (higher → more income). "
        "Bubble size: employment share (larger bubble = higher proportion of graduates)."
    )

    if noc_result and noc_result.get("detail_distribution"):
        try:
            with st.spinner("Querying income data for occupation quadrant..."):
                quadrant_data = fetch_noc_income_for_quadrant(
                    noc_result["detail_distribution"],
                    cip_code,
                    broad_field,
                    education,
                )
            if quadrant_data:
                st.plotly_chart(
                    noc_quadrant_bubble(quadrant_data, oasis_noc_set=oasis_noc_set),
                    use_container_width=True,
                )

                # Compact quadrant legend
                q1, q2, q3, q4 = st.columns(4)
                q1.markdown(
                    '<span style="color:#10B981;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Many + High Pay</span>',
                    unsafe_allow_html=True,
                )
                q2.markdown(
                    '<span style="color:#6366F1;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Few + High Pay</span>',
                    unsafe_allow_html=True,
                )
                q3.markdown(
                    '<span style="color:#F59E0B;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Many + Lower Pay</span>',
                    unsafe_allow_html=True,
                )
                q4.markdown(
                    '<span style="color:#F43F5E;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Few + Lower Pay</span>',
                    unsafe_allow_html=True,
                )
                st.caption("Bubble size = share of graduates. Hover for details.")
            else:
                st.info("Could not retrieve income data for the occupation quadrant chart.")
        except Exception as e:
            st.error(f"Error loading quadrant data: {e}")
            st.code(traceback.format_exc())
    else:
        st.info("No specific occupation data available for quadrant chart.")

    st.divider()

    # ── Section: Broad field income comparison ─────────────────
    st.markdown('<div id="sect-broad"></div>', unsafe_allow_html=True)
    st.header("Income by Field of Study — All Fields")
    st.caption(
        "Comparison of median employment income across all broad fields of study, "
        "2 years and 5 years after graduation. Your field is highlighted."
    )

    if result["broad_comparison"]:
        st.plotly_chart(
            cip_income_comparison_bar(result["broad_comparison"], broad_field),
            use_container_width=True,
        )
    else:
        st.warning("No broad field comparison data available.")

    st.divider()

    # ── Section: Sub-field comparison ──────────────────────────
    st.markdown('<div id="sect-subfield"></div>', unsafe_allow_html=True)
    st.header(f"Sub-field Breakdown — {broad_field}")
    st.caption(
        f"Detailed income comparison within the '{broad_field}' category."
    )

    if result["subfield_comparison"]:
        st.plotly_chart(
            cip_subfield_income_bar(result["subfield_comparison"], user_field_name),
            use_container_width=True,
        )
    else:
        st.info("No sub-field data available for this broad category.")

    st.divider()

    # ── Section: Growth rate comparison ────────────────────────
    st.markdown('<div id="sect-growth"></div>', unsafe_allow_html=True)
    st.header("Income Growth Rate — 2yr to 5yr After Graduation")
    st.caption(
        "Percentage increase in median income from 2 years to 5 years after graduation. "
        "Higher growth rates indicate stronger career trajectory early on."
    )

    if result["broad_comparison"]:
        st.plotly_chart(
            cip_growth_bar(result["broad_comparison"], broad_field),
            use_container_width=True,
        )
    else:
        st.warning("No growth rate data available.")

    # ── Navigation ─────────────────────────────────────────────
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Back to Profile", use_container_width=True, key="cip_back_profile"):
            st.session_state["wizard_page"] = "profile"
            st.rerun()
    with col2:
        if st.button(
            "Continue to Full Analysis",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["wizard_page"] = "analysis"
            st.rerun()

    # Footer
    st.divider()
    st.markdown(
        '<div class="yf-footer">Data sources: Statistics Canada Table 37-10-0280-01 '
        '(Graduate income by CIP field), Table 98-10-0403-01 '
        '(Occupation by field of study), and Table 98-10-0412-01 '
        '(Income by NOC and CIP, 2021 Census). '
        'Queried in real-time via WDS REST API.</div>',
        unsafe_allow_html=True,
    )


# ── New Page: Career Exploration ──────────────────────────────────


def render_career_exploration_page():
    """Career Exploration wizard — routes between step 1 and step 2."""
    step = st.session_state.get("_ce_step", 1)
    if step == 2:
        _render_ce_step2()
    else:
        _render_ce_step1()


def _render_ce_step_indicator(current_step):
    """Render a compact 2-step numbered progress indicator."""
    _A = "#6366F1"
    _W = "#FFFFFF"
    _G = "#94A3B8"
    _D = "#475569"
    _PB = "#F8FAFC"
    _PE = "#E2E8F0"

    if current_step > 1:
        s1_s = f"background:{_A};color:{_W};border:1.5px solid {_A}"
        s1_t = f"color:{_D};font-weight:600"
        s1_c = "\u2713"
    else:
        s1_s = f"background:{_A};color:{_W};border:1.5px solid {_A};box-shadow:0 0 0 3px rgba(99,102,241,0.15)"
        s1_t = f"color:{_A};font-weight:600"
        s1_c = "1"

    if current_step == 2:
        s2_s = f"background:{_A};color:{_W};border:1.5px solid {_A};box-shadow:0 0 0 3px rgba(99,102,241,0.15)"
        s2_t = f"color:{_A};font-weight:600"
        ln = _A
    else:
        s2_s = f"background:{_PB};color:{_G};border:1.5px solid {_PE}"
        s2_t = f"color:{_G};font-weight:500"
        ln = _PE

    st.markdown(
        f'<div style="display:flex;align-items:center;justify-content:center;gap:0;'
        f'margin:12px 0 28px;user-select:none">'
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:6px;min-width:90px">'
        f'<div style="width:32px;height:32px;border-radius:50%;display:flex;align-items:center;'
        f'justify-content:center;font-size:0.8rem;font-weight:600;transition:all 0.3s;{s1_s}">{s1_c}</div>'
        f'<span style="font-size:0.72rem;letter-spacing:0.03em;{s1_t}">Profile</span></div>'
        f'<div style="width:56px;height:2px;background:{ln};margin-bottom:22px;'
        f'border-radius:1px;transition:background 0.3s"></div>'
        f'<div style="display:flex;flex-direction:column;align-items:center;gap:6px;min-width:90px">'
        f'<div style="width:32px;height:32px;border-radius:50%;display:flex;align-items:center;'
        f'justify-content:center;font-size:0.8rem;font-weight:600;transition:all 0.3s;{s2_s}">2</div>'
        f'<span style="font-size:0.72rem;letter-spacing:0.03em;{s2_t}">Field of Study</span>'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def _render_ce_step1():
    """Step 1: collect basic personal information."""
    st.markdown('<div class="yf-wizard-wrapper">', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            '<div class="yf-wizard-hero">'
            "<h1>Career Explorer</h1>"
            "<p>Discover your career path with data-driven insights.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        # Row 1 — Name + Age
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div class="yf-field-label">Name</div>', unsafe_allow_html=True)
            user_name = st.text_input(
                "Name", value=st.session_state.get("user_name", ""),
                key="ce_name", label_visibility="collapsed", placeholder="Your name",
            )
        with col2:
            st.markdown('<div class="yf-field-label">Age</div>', unsafe_allow_html=True)
            user_age = st.slider(
                "Age", min_value=16, max_value=70,
                value=st.session_state.get("user_age", 25),
                key="ce_age", label_visibility="collapsed",
            )

        # Row 2 — Gender + Education
        col3, col4 = st.columns(2)
        with col3:
            st.markdown('<div class="yf-field-label">Gender</div>', unsafe_allow_html=True)
            gender_options = ["Male", "Female", "Other"]
            gender_idx = 0
            saved_gender = st.session_state.get("user_gender")
            if saved_gender in gender_options:
                gender_idx = gender_options.index(saved_gender)
            user_gender = st.selectbox(
                "Gender", gender_options, index=gender_idx,
                key="ce_gender", label_visibility="collapsed",
            )
        with col4:
            st.markdown('<div class="yf-field-label">Education</div>', unsafe_allow_html=True)
            edu_keys = list(EDUCATION_OPTIONS.keys())
            edu_idx = 0
            saved_edu = st.session_state.get("education")
            if saved_edu in edu_keys:
                edu_idx = edu_keys.index(saved_edu)
            education = st.selectbox(
                "Education Level", edu_keys, index=edu_idx,
                key="ce_edu", label_visibility="collapsed",
            )

        # Row 3 — Province
        st.markdown('<div class="yf-field-label">Province / Territory</div>', unsafe_allow_html=True)
        geo_idx = 0
        saved_geo = st.session_state.get("geo")
        if saved_geo in GEO_OPTIONS:
            geo_idx = GEO_OPTIONS.index(saved_geo)
        geo = st.selectbox(
            "Province / Territory", GEO_OPTIONS, index=geo_idx,
            key="ce_geo", label_visibility="collapsed",
        )

    if st.button("Continue \u2192", type="primary", use_container_width=True, key="ce_next"):
        st.session_state["user_name"] = user_name
        st.session_state["user_age"] = user_age
        st.session_state["user_gender"] = user_gender
        st.session_state["education"] = education
        st.session_state["geo"] = geo
        st.session_state["_ce_step"] = 2
        st.rerun()

    _render_ce_step_indicator(1)
    st.markdown("</div>", unsafe_allow_html=True)


def _render_ce_step2():
    """Step 2: search and select field of study (keyword only)."""
    st.markdown('<div class="yf-wizard-wrapper">', unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown(
            '<div class="yf-wizard-hero">'
            "<h1>What did you study?</h1>"
            "<p>Search by keyword to find your field of study.</p>"
            "</div>",
            unsafe_allow_html=True,
        )

        st.markdown('<div class="yf-field-label">Search your major</div>', unsafe_allow_html=True)
        query = st.text_input(
            "Search", value=st.session_state.get("_ce_field_query", ""),
            placeholder="e.g. computer science, nursing, 14.08",
            key="ce_field_query", label_visibility="collapsed",
        )

        broad_field = st.session_state.get("broad_field")
        subfield = st.session_state.get("subfield")
        cip_code = st.session_state.get("cip_code")
        cip_name = st.session_state.get("cip_name")

        if query:
            matches = match_fields(query, FIELD_OPTIONS)
            if matches:
                options = [m["display_name"] for m in matches]
                preselect = 0
                saved_display = st.session_state.get("_selected_display")
                if saved_display in options:
                    preselect = options.index(saved_display)

                choice = st.radio(
                    "Select your field:", options, index=preselect,
                    key="ce_field_radio", label_visibility="collapsed",
                )
                selected = matches[options.index(choice)]
                broad_field = selected["broad_field"]
                subfield = selected["subfield"]
                cip_code = selected.get("cip_code")
                cip_name = selected.get("cip_name")

                if cip_code and not subfield:
                    st.caption(
                        f"CIP {cip_code} has no dedicated statistics \u2014 "
                        f"analysis will use the broad category: {broad_field}"
                    )
                elif cip_code and subfield and not subfield.startswith(cip_code):
                    st.caption(f"CIP {cip_code} mapped to nearest available data: {subfield}")
            else:
                st.warning("No matches found. Try a different keyword.")
                broad_field = None
                subfield = None
                cip_code = None
                cip_name = None
        else:
            st.markdown(
                '<div style="text-align:center;padding:24px 0;color:#94A3B8">'
                "<p>Type above to find your field of study.</p>"
                "</div>",
                unsafe_allow_html=True,
            )

    can_proceed = bool(broad_field)
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("\u2190 Back", use_container_width=True, key="ce_back_step1"):
            st.session_state["_ce_step"] = 1
            st.rerun()
    with col_next:
        if st.button(
            "View Analysis \u2192", type="primary", use_container_width=True,
            disabled=not can_proceed, key="ce_confirm",
        ):
            st.session_state["broad_field"] = broad_field
            st.session_state["subfield"] = subfield
            st.session_state["cip_code"] = cip_code
            st.session_state["cip_name"] = cip_name
            st.session_state["_ce_field_query"] = query
            if query:
                _matches = match_fields(query, FIELD_OPTIONS)
                for m in _matches:
                    if m["broad_field"] == broad_field and m["subfield"] == subfield:
                        st.session_state["_selected_display"] = m["display_name"]
                        break
                else:
                    st.session_state["_selected_display"] = (
                        f"{subfield}  ({broad_field})" if subfield else broad_field
                    )
            else:
                st.session_state["_selected_display"] = (
                    f"{subfield}  ({broad_field})" if subfield else broad_field
                )
            st.session_state["wizard_page"] = "ce_analysis"
            st.rerun()

    _render_ce_step_indicator(2)
    st.markdown("</div>", unsafe_allow_html=True)


# ── New Page: CE Analysis ────────────────────────────────────────


def render_ce_analysis_page():
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Back to Career Exploration", use_container_width=True, key="ce_back"):
            st.session_state["wizard_page"] = "career_exploration"
            st.rerun()
        if st.button("Clear cache & refresh", use_container_width=True, key="ce_clear_cache"):
            st.cache_data.clear()
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_ce_analysis"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("ce_analysis")

    # ── Header ─────────────────────────────────────────────────
    st.title("Analysis")
    if cip_code and cip_name:
        st.info(f"**CIP {cip_code}** — {cip_name}  |  Broad field: **{broad_field}**")
    else:
        st.info(f"Field of study: **{field_display}**")

    # ── Fetch NOC distribution data ───────────────────────────
    noc_result = None
    try:
        with st.spinner("Querying occupation (NOC) distribution data..."):
            noc_result = fetch_noc_distribution(cip_code, broad_field, education, geo)
    except Exception as e:
        st.error(f"Error loading NOC distribution: {e}")
        if st.button("Clear cache and retry", key="ce_retry_noc"):
            st.cache_data.clear()
            st.rerun()
        return

    if not noc_result:
        st.warning("No occupation distribution data available.")
        if st.button("Retry", key="ce_retry_noc2"):
            st.cache_data.clear()
            st.rerun()
        return

    # ── Occupations Matching Your Field of Study ─────────────
    st.header("Occupations Matching Your Field of Study")
    st.caption(
        "Graduate Occupations by NOC 2021 Code and Proportion"
    )

    detail_dist = noc_result.get("detail_distribution") or []
    if not detail_dist:
        st.info("No specific occupation data available for this field/province combination.")
        return

    # Build rows
    all_rows = []
    for idx, entry in enumerate(detail_dist, 1):
        full_name = entry["noc"]
        parts = full_name.split(" ", 1)
        noc_code = parts[0] if len(parts) > 1 and parts[0].isdigit() else ""
        noc_name = parts[1] if len(parts) > 1 and parts[0].isdigit() else full_name
        pct = entry.get("percentage", 0)
        cnt = entry.get("count")
        all_rows.append({
            "idx": idx,
            "noc_code": noc_code,
            "noc_name": noc_name,
            "full_name": full_name,
            "pct": pct,
            "count": cnt,
        })

    # ── Keyword search ────────────────────────────────────────
    search_q = st.text_input(
        "Search occupations by keyword",
        placeholder="e.g. software, nurse, teacher...",
        key="ce_occ_search",
    )

    if search_q and search_q.strip():
        kw = search_q.strip().lower()
        filtered = [r for r in all_rows if kw in r["noc_name"].lower() or kw in r["noc_code"]]
    else:
        filtered = all_rows

    # ── Build DataFrame for data_editor ───────────────────────
    # Track which full_names were previously selected so search preserves choices
    if "_ce_sel_names" not in st.session_state:
        # Default: top 6 valid NOC-5 codes
        defaults = set()
        for r in all_rows:
            if len(r["noc_code"]) == 5 and len(defaults) < 6:
                defaults.add(r["full_name"])
        st.session_state["_ce_sel_names"] = defaults
    prev_sel = st.session_state["_ce_sel_names"]

    records = []
    for r in filtered:
        records.append({
            "Sel": r["full_name"] in prev_sel,
            "#": r["idx"],
            "NOC": r["noc_code"],
            "Occupation": r["noc_name"],
            "Pct": r["pct"],
            "Count": r["count"] if r["count"] is not None else None,
            "_full_name": r["full_name"],
        })
    df_all = pd.DataFrame(records)

    st.markdown(
        "<p style='font-size:0.82rem;color:#64748B;margin-bottom:2px;'>"
        "Select up to 6 occupations for detailed analysis (default: top 6)</p>",
        unsafe_allow_html=True,
    )

    if not records:
        st.info("No occupations match your search.")
        selected_names = prev_sel
    else:
        edited = st.data_editor(
            df_all,
            column_config={
                "Sel": st.column_config.CheckboxColumn("", width="small"),
                "#": st.column_config.NumberColumn("#", width="small"),
                "NOC": st.column_config.TextColumn("NOC", width="small"),
                "Occupation": st.column_config.TextColumn("Occupation", width="large"),
                "Pct": st.column_config.NumberColumn("%", format="%.1f%%", width="small"),
                "Count": st.column_config.NumberColumn("Count", width="small"),
                "_full_name": None,
            },
            hide_index=True,
            use_container_width=True,
            disabled=["#", "NOC", "Occupation", "Pct", "Count"],
            height=min(36 * len(records) + 38, 600),
            key="ce_occ_table",
        )

        # Collect selected: start from previous, update with visible rows
        selected_names = set(prev_sel)
        visible_names = {r["_full_name"] for _, r in edited.iterrows()}
        # Remove deselected visible rows, add newly selected ones
        for _, row in edited.iterrows():
            if row["Sel"]:
                selected_names.add(row["_full_name"])
            else:
                selected_names.discard(row["_full_name"])
        st.session_state["_ce_sel_names"] = selected_names

    # ── Build top_noc_codes from selection ────────────────────
    top_noc_codes = []
    for r in all_rows:
        if r["full_name"] in selected_names and len(r["noc_code"]) == 5:
            top_noc_codes.append({"code": r["noc_code"], "name": r["full_name"]})

    # ── Warn if more than 5 selected ─────────────────────────
    n_sel = len(top_noc_codes)
    if n_sel > 6:
        st.toast(f"You selected {n_sel} occupations — maximum is 6. Please deselect some.", icon="\u26a0\ufe0f")
        top_noc_codes = top_noc_codes[:6]
        n_sel = 6

    # Keep selection in sync so downstream pages always see the latest
    st.session_state["ce_top_nocs"] = top_noc_codes

    # Write consolidated career state for Competence Comparison page (multi-page app)
    st.session_state["career"] = {
        "all_field_nocs": top_noc_codes,
        "selected_nocs":  top_noc_codes,
        "geo":      st.session_state.get("geo",      "Canada"),
        "cip_code": st.session_state.get("cip_code", ""),
        "cip_name": st.session_state.get("cip_name", ""),
    }

    # ── Show selected occupations ─────────────────────────────
    st.divider()
    if n_sel > 0:
        with st.container(border=True):
            st.markdown(
                f"<div style='font-size:0.82rem;font-weight:600;color:#64748B;"
                f"margin-bottom:6px;'>Selected Occupations ({n_sel}/6)</div>",
                unsafe_allow_html=True,
            )
            cols_per_row = 3
            for row_start in range(0, n_sel, cols_per_row):
                row_nocs = top_noc_codes[row_start:row_start + cols_per_row]
                cols = st.columns(cols_per_row)
                for j, noc in enumerate(row_nocs):
                    with cols[j]:
                        tag_col, btn_col = st.columns([5, 1])
                        with tag_col:
                            st.markdown(
                                f"<div style='background:#EEF2FF;color:#4338CA;"
                                f"border:1px solid #C7D2FE;border-radius:16px;"
                                f"padding:5px 12px;font-size:0.78rem;font-weight:500;"
                                f"white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
                                f"line-height:1.4;'>"
                                f"{noc['name']}</div>",
                                unsafe_allow_html=True,
                            )
                        with btn_col:
                            if st.button("\u2715", key=f"del_{noc['code']}",
                                         help=f"Remove {noc['name']}"):
                                st.session_state["_ce_sel_names"].discard(noc["name"])
                                st.rerun()

        st.markdown("")
        if st.button(
            "Detailed Headcount  \u2192",
            type="primary",
            use_container_width=True,
            key="ce_headcount_btn",
        ):
            st.session_state["wizard_page"] = "ce_headcount"
            st.rerun()
    else:
        st.warning("Please select at least one occupation to continue.")


# ── New Page: CE Detailed Headcount ──────────────────────────────


def render_ce_headcount_page():
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Back to Analysis", use_container_width=True, key="headcount_back"):
            st.session_state["wizard_page"] = "ce_analysis"
            st.rerun()
        if st.button("Clear cache & refresh", use_container_width=True, key="hc_clear_cache"):
            st.cache_data.clear()
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_headcount"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("headcount")

    st.title("Detailed Headcount")
    st.caption(
        "Employment headcount breakdown (Total / Male / Female) for your selected "
        "occupations that graduates in this field enter."
    )

    # ── Fetch NOC distribution data ───────────────────────────
    noc_result = None
    try:
        with st.spinner("Querying occupation (NOC) distribution data..."):
            noc_result = fetch_noc_distribution(cip_code, broad_field, education, geo)
    except Exception as e:
        st.error(f"Error loading NOC distribution: {e}")
        if st.button("Clear cache and retry", key="hc_retry_noc"):
            st.cache_data.clear()
            st.rerun()
        return

    if not noc_result:
        st.warning("No occupation distribution data available.")
        if st.button("Retry", key="hc_retry_noc2"):
            st.cache_data.clear()
            st.rerun()
        return

    all_entries = noc_result.get("detail_distribution") or noc_result.get("submajor_distribution") or []

    # Filter to user-selected occupations
    selected_nocs = st.session_state.get("ce_top_nocs", [])
    if selected_nocs:
        sel_codes = {n["code"] for n in selected_nocs}
        top_entries = [e for e in all_entries if e["noc"].split(" ", 1)[0] in sel_codes]
    else:
        top_entries = all_entries

    if top_entries:
        try:
            with st.spinner("Querying gender breakdown for top occupations..."):
                gender_data = fetch_noc_gender_breakdown(
                    top_entries, cip_code, broad_field, education, top_n=len(top_entries), geo=geo
                )
        except Exception as e:
            st.error(f"Error loading gender breakdown: {e}")
            st.code(traceback.format_exc())
            gender_data = []

        if gender_data:
            # Fetch OaSIS descriptions + unit profiles for all top NOCs
            noc_desc_data = {}
            noc_profiles = {}
            noc_codes_to_fetch = []
            for item in gender_data:
                code = item["noc"].split(" ", 1)[0]
                if len(code) == 5 and code.isdigit():
                    noc_codes_to_fetch.append((code, item["noc"]))

            if noc_codes_to_fetch:
                with st.spinner("Fetching occupation details from OaSIS / NOC..."):
                    for code, full_name in noc_codes_to_fetch:
                        try:
                            info = fetch_noc_description(code)
                            if info and (info.get("description") or info.get("sub_profiles")):
                                noc_desc_data[full_name] = info
                        except Exception:
                            pass
                        try:
                            noc_profiles[code] = fetch_noc_unit_profile(code)
                        except Exception:
                            pass

            # Profile sections to show (no Exclusions)
            _DETAIL_SECTIONS = [
                ("example_titles", "Example Titles"),
                ("main_duties", "Main Duties"),
                ("employment_requirements", "Employment Requirements"),
                ("additional_information", "Additional Information"),
            ]

            for i, item in enumerate(gender_data, 1):
                noc_name = item["noc"]
                noc_code = noc_name.split(" ", 1)[0]
                total = item["count_total"]
                male = item["count_male"]
                female = item["count_female"]

                total_str = f"{total:,}" if total is not None else "N/A"
                male_str = f"{male:,}" if male is not None else "N/A"
                female_str = f"{female:,}" if female is not None else "N/A"

                st.markdown(f"**{i}. {noc_name}**")

                # OaSIS description (with fallback chain)
                desc = None
                info = noc_desc_data.get(noc_name)
                if info:
                    desc = info.get("description")
                    if not desc:
                        # Fallback 1: first sub-profile description
                        for sp in info.get("sub_profiles") or []:
                            if sp.get("description"):
                                desc = sp["description"]
                                break
                if not desc:
                    # Fallback 2: summarize main duties from NOC Structure page
                    profile_fb = noc_profiles.get(noc_code, {})
                    duties = profile_fb.get("main_duties") or []
                    if duties:
                        desc = "; ".join(duties[:3])
                        if len(duties) > 3:
                            desc += "; ..."
                if desc:
                    st.markdown(
                        f"<div style='background:#F8FAFC; border-left:3px solid #6366F1; "
                        f"padding:10px 14px; margin:6px 0 10px; border-radius:0 8px 8px 0; "
                        f"color:#475569; font-size:0.9rem; line-height:1.5;'>"
                        f"{desc}</div>",
                        unsafe_allow_html=True,
                    )

                # Headcount
                st.markdown(
                    f"&nbsp;&nbsp;&nbsp;&nbsp;"
                    f"Total: **{total_str}**&emsp;|&emsp;"
                    f"Male: **{male_str}**&emsp;|&emsp;"
                    f"Female: **{female_str}**"
                )

                # Inline "View Details" expander
                profile = noc_profiles.get(noc_code, {})
                has_profile = any(profile.get(k) for k, _ in _DETAIL_SECTIONS)
                if has_profile:
                    with st.expander("View Details"):
                        for field_key, field_label in _DETAIL_SECTIONS:
                            items = profile.get(field_key) or []
                            if items:
                                st.markdown(
                                    f"<div style='font-weight:600;color:#4338CA;"
                                    f"font-size:0.84rem;margin:8px 0 4px;'>"
                                    f"{field_label}</div>",
                                    unsafe_allow_html=True,
                                )
                                items_html = "".join(
                                    f"<li style='margin-bottom:2px;'>{it}</li>"
                                    for it in items
                                )
                                st.markdown(
                                    f"<ul style='margin:0;padding-left:18px;"
                                    f"font-size:0.84rem;line-height:1.5;color:#475569;'>"
                                    f"{items_html}</ul>",
                                    unsafe_allow_html=True,
                                )

                if i < len(gender_data):
                    st.markdown("---")
        else:
            st.info("Gender breakdown data not available for these occupations.")
    else:
        st.info("No occupation data available to show headcount breakdown.")

    # ── Navigation buttons ────────────────────────────────────
    top_noc_codes = st.session_state.get("ce_top_nocs", [])
    if top_noc_codes:
        st.divider()
        btn_col1, btn_col2 = st.columns(2)
        with btn_col1:
            if st.button(
                "View Required Skills",
                type="primary",
                use_container_width=True,
                key="hc_skills_btn",
            ):
                st.session_state["wizard_page"] = "ce_skills"
                st.rerun()
        with btn_col2:
            if st.button(
                "View Income Analysis",
                type="primary",
                use_container_width=True,
                key="hc_wages_btn",
            ):
                st.session_state["wizard_page"] = "ce_wages"
                st.rerun()


# ── New Page: CE Job Analysis ────────────────────────────────────


def render_ce_job_analysis_page():
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    top_nocs = st.session_state.get("ce_top_nocs", [])

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Back to Analysis", use_container_width=True, key="job_back_analysis"):
            st.session_state["wizard_page"] = "ce_analysis"
            st.rerun()
        if st.button("Back to Career Exploration", use_container_width=True, key="job_back_ce"):
            st.session_state["wizard_page"] = "career_exploration"
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_job"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("job")

    # ── Header ─────────────────────────────────────────────────
    st.title("Career Analysis — Job Title Profiles")
    if cip_code and cip_name:
        st.info(f"**CIP {cip_code}** — {cip_name}")
    st.caption(
        "Detailed unit group profiles for the top occupations that graduates "
        "in this field enter. Data from the National Occupational Classification (NOC)."
    )

    if not top_nocs:
        st.warning("No occupation data available. Please go back and run the analysis first.")
        return

    # ── Fetch all profiles ────────────────────────────────────
    profiles = {}
    with st.spinner("Fetching unit group profiles from NOC..."):
        for noc in top_nocs:
            profiles[noc["code"]] = fetch_noc_unit_profile(noc["code"])

    # ── Profile sections to display ───────────────────────────
    PROFILE_ROWS = [
        ("example_titles", "Example Titles"),
        ("main_duties", "Main Duties"),
        ("employment_requirements", "Employment Requirements"),
        ("additional_information", "Additional Information"),
        ("exclusions", "Exclusions"),
    ]

    # ── Build comparison table ────────────────────────────────
    # Column headers: one per NOC
    noc_codes = [n["code"] for n in top_nocs]
    noc_labels = []
    for n in top_nocs:
        p = profiles.get(n["code"], {})
        title = p.get("title") or n["name"].split(" ", 1)[-1] if " " in n["name"] else n["name"]
        noc_labels.append(f"**{n['code']}**<br>{title}")

    # Render as styled HTML table
    # Build header
    header_cells = "".join(
        f"<th style='background:linear-gradient(135deg,#6366F1,#8B5CF6); color:white; "
        f"padding:12px 10px; font-size:0.82rem; font-weight:600; text-align:center; "
        f"min-width:180px; border-right:1px solid rgba(255,255,255,0.2);'>"
        f"{profiles.get(n['code'], {}).get('title') or n['name']}<br>"
        f"<span style='font-weight:400; opacity:0.85;'>NOC {n['code']}</span></th>"
        for n in top_nocs
    )

    # Build rows
    rows_html = ""
    for field_key, field_label in PROFILE_ROWS:
        cells = ""
        for n in top_nocs:
            p = profiles.get(n["code"], {})
            items = p.get(field_key) or []

            if items:
                items_html = "".join(
                    f"<li style='margin-bottom:3px;'>{item}</li>" for item in items
                )
                cell_content = f"<ul style='margin:0; padding-left:16px; font-size:0.82rem; line-height:1.45;'>{items_html}</ul>"
            else:
                cell_content = "<span style='color:#94A3B8; font-style:italic; font-size:0.82rem;'>N/A</span>"

            cells += (
                f"<td style='padding:10px 12px; vertical-align:top; "
                f"border-bottom:1px solid #E2E8F0; border-right:1px solid #F1F5F9;'>"
                f"{cell_content}</td>"
            )

        rows_html += (
            f"<tr>"
            f"<td style='padding:10px 12px; font-weight:600; color:#4338CA; "
            f"background:#F8FAFC; vertical-align:top; white-space:nowrap; "
            f"border-bottom:1px solid #E2E8F0; border-right:1px solid #E2E8F0; "
            f"font-size:0.85rem;'>{field_label}</td>"
            f"{cells}</tr>"
        )

    table_html = (
        f"<div style='overflow-x:auto; border:1px solid #E2E8F0; border-radius:12px; "
        f"box-shadow:0 1px 3px rgba(0,0,0,0.04);'>"
        f"<table style='width:100%; border-collapse:collapse; table-layout:fixed;'>"
        f"<thead><tr>"
        f"<th style='background:#1E293B; color:white; padding:12px; font-size:0.82rem; "
        f"font-weight:600; text-align:left; min-width:140px; "
        f"border-right:1px solid rgba(255,255,255,0.15);'>Profile</th>"
        f"{header_cells}"
        f"</tr></thead>"
        f"<tbody>{rows_html}</tbody>"
        f"</table></div>"
    )

    st.markdown(table_html, unsafe_allow_html=True)


# ── New Page: CE Skills ──────────────────────────────────────────


def render_ce_skills_page():
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    top_nocs = st.session_state.get("ce_top_nocs", [])

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Back to Analysis", use_container_width=True, key="skills_back_analysis"):
            st.session_state["wizard_page"] = "ce_analysis"
            st.rerun()
        if st.button("Back to Career Exploration", use_container_width=True, key="skills_back_ce"):
            st.session_state["wizard_page"] = "career_exploration"
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_skills"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("skills")

    # ── Header ─────────────────────────────────────────────────
    st.title("Career Exploration — Required Skills")
    if cip_code and cip_name:
        st.info(f"**CIP {cip_code}** — {cip_name}  |  Location: **{geo}**")
    st.caption(
        "Skills, work styles, and knowledge requirements for the top occupations. "
        "Data from Job Bank Canada (jobbank.gc.ca)."
    )

    if not top_nocs:
        st.warning("No occupation data available. Please go back and run the analysis first.")
        return

    # ── Fetch skills for all NOCs ─────────────────────────────
    all_skills = {}
    with st.spinner("Fetching skills data from Job Bank..."):
        for noc in top_nocs:
            all_skills[noc["code"]] = fetch_jobbank_skills(noc["code"], geo)

    # Check if we got any data
    has_data = any(
        s.get("skills") or s.get("work_styles") or s.get("knowledge")
        for s in all_skills.values()
    )
    if not has_data:
        st.warning("Could not retrieve skills data from Job Bank for these occupations.")
        return

    # ── Build comparison tables for each section ──────────────
    SECTIONS = [
        ("skills", "Skills", "Proficiency / Complexity Level"),
        ("work_styles", "Work Styles", "Importance"),
        ("knowledge", "Knowledge", "Knowledge Level"),
    ]

    # Build header cells (same for all tables)
    header_cells = ""
    for n in top_nocs:
        s = all_skills.get(n["code"], {})
        title = s.get("title") or n["name"].split(" ", 1)[-1] if " " in n["name"] else n["name"]
        header_cells += (
            f"<th style='background:linear-gradient(135deg,#6366F1,#8B5CF6); color:white; "
            f"padding:5px 4px; font-size:0.7rem; font-weight:600; text-align:center; "
            f"min-width:90px; border-right:1px solid rgba(255,255,255,0.2);'>"
            f"{title}<br>"
            f"<span style='font-weight:400; opacity:0.8; font-size:0.65rem;'>NOC {n['code']}</span></th>"
        )

    for section_key, section_title, level_label in SECTIONS:
        st.header(section_title)
        st.caption(f"Comparison of {section_title.lower()} across occupations — {level_label}")

        # Collect all unique skill names across NOCs for this section
        all_names = []
        seen = set()
        for n in top_nocs:
            s = all_skills.get(n["code"], {})
            for item in s.get(section_key, []):
                if item["name"] not in seen:
                    seen.add(item["name"])
                    all_names.append(item["name"])

        if not all_names:
            st.info(f"No {section_title.lower()} data available.")
            st.divider()
            continue

        # Build skill lookup per NOC: name → level
        noc_lookups = {}
        for n in top_nocs:
            s = all_skills.get(n["code"], {})
            lookup = {}
            for item in s.get(section_key, []):
                lookup[item["name"]] = item["level"]
            noc_lookups[n["code"]] = lookup

        # Color maps: red (highest) → gray (lowest)
        # Skills & Work Styles: 1-5;  Knowledge: 1-3
        _COLORS_5 = {
            5: "#DC2626",   # red
            4: "#EA580C",   # orange
            3: "#D97706",   # amber
            2: "#8B6C4F",   # brown
            1: "#9CA3AF",   # gray
        }
        _COLORS_3 = {
            3: "#DC2626",   # red
            2: "#8B6C4F",   # brown
            1: "#9CA3AF",   # gray
        }
        is_knowledge = section_key == "knowledge"
        color_map = _COLORS_3 if is_knowledge else _COLORS_5
        max_score = 3 if is_knowledge else 5

        def _badge(value):
            """Return HTML for a colored number badge."""
            clr = color_map.get(round(value), "#9CA3AF")
            display = str(int(value))
            return (
                f"<span style='display:inline-block; min-width:22px; text-align:center; "
                f"background:{clr}; color:#FFF; padding:2px 6px; border-radius:5px; "
                f"font-size:0.78rem; font-weight:700; line-height:1.3;'>{display}</span>"
            )

        def _avg_bar(value):
            """Return HTML for Avg column: bar + number."""
            clr = color_map.get(round(value), "#9CA3AF")
            pct = value / max_score * 100
            display = f"{value:.1f}" if value != int(value) else str(int(value))
            return (
                f"<div style='display:flex; align-items:center; gap:5px; min-width:90px;'>"
                f"<div style='flex:1; background:#E5E7EB; border-radius:4px; height:10px; overflow:hidden;'>"
                f"<div style='width:{pct:.0f}%; height:100%; background:{clr}; "
                f"border-radius:4px;'></div></div>"
                f"<span style='font-size:0.78rem; font-weight:700; color:{clr}; "
                f"min-width:24px; text-align:right;'>{display}</span></div>"
            )

        # Build rows
        n_total = len(top_nocs)
        rows_html = ""
        for skill_name in all_names:
            noc_cells = ""
            scores = []
            for n in top_nocs:
                level = noc_lookups[n["code"]].get(skill_name)
                if level:
                    num_int = int(level[0]) if level[0].isdigit() else 0
                    scores.append(num_int)
                    cell_content = _badge(num_int)
                else:
                    scores.append(0)
                    cell_content = "<span style='color:#CBD5E1; font-size:0.75rem;'>N/A</span>"
                noc_cells += (
                    f"<td style='padding:3px 4px; text-align:center; vertical-align:middle; "
                    f"border-bottom:1px solid #E2E8F0; border-right:1px solid #F1F5F9;'>"
                    f"{cell_content}</td>"
                )

            # Average cell — always divide by total NOC count
            if n_total > 0:
                avg = sum(scores) / n_total
                avg_content = _avg_bar(avg)
            else:
                avg_content = "<span style='color:#CBD5E1; font-size:0.75rem;'>—</span>"
            avg_cell = (
                f"<td style='padding:3px 8px; vertical-align:middle; "
                f"border-bottom:1px solid #E2E8F0; border-right:2px solid #E2E8F0; "
                f"background:#F1F5F9;'>{avg_content}</td>"
            )

            rows_html += (
                f"<tr>"
                f"<td style='padding:3px 8px; font-weight:500; color:#1E293B; "
                f"background:#FAFBFC; vertical-align:middle; "
                f"border-bottom:1px solid #E2E8F0; border-right:1px solid #E2E8F0; "
                f"font-size:0.8rem; line-height:1.3;'>{skill_name}</td>"
                f"{avg_cell}{noc_cells}</tr>"
            )

        # Avg column header (right after label)
        avg_header = (
            "<th style='background:#374151; color:#FDE68A; "
            "padding:6px 8px; font-size:0.8rem; font-weight:700; text-align:center; "
            "min-width:110px; border-right:2px solid rgba(255,255,255,0.3);'>Avg</th>"
        )

        # Fixed column widths for consistency across all 3 tables
        n_nocs = len(top_nocs)
        col_defs = (
            "<colgroup>"
            "<col style='width:200px;'/>"   # label
            "<col style='width:130px;'/>"   # avg
            + "".join(f"<col style='width:80px;'/>" for _ in range(n_nocs))
            + "</colgroup>"
        )

        table_html = (
            f"<div style='overflow-x:auto; border:1px solid #E2E8F0; border-radius:12px; "
            f"box-shadow:0 1px 3px rgba(0,0,0,0.04); margin-bottom:8px;'>"
            f"<table style='width:100%; border-collapse:collapse; table-layout:fixed;'>"
            f"{col_defs}"
            f"<thead><tr>"
            f"<th style='background:#1E293B; color:white; padding:6px 8px; font-size:0.8rem; "
            f"font-weight:600; text-align:left; "
            f"border-right:1px solid rgba(255,255,255,0.15);'>{level_label}</th>"
            f"{avg_header}{header_cells}"
            f"</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table></div>"
        )

        st.markdown(table_html, unsafe_allow_html=True)

        # Legend — colored bars
        if is_knowledge:
            legend_items = [
                ("3", "#DC2626", "Advanced"),
                ("2", "#8B6C4F", "Intermediate"),
                ("1", "#9CA3AF", "Basic"),
            ]
        else:
            legend_items = [
                ("5", "#DC2626", "Highest"),
                ("4", "#EA580C", "High"),
                ("3", "#D97706", "Moderate"),
                ("2", "#8B6C4F", "Low"),
                ("1", "#9CA3AF", "Basic"),
            ]
        legend_html = "".join(
            f"<span style='display:inline-flex; align-items:center; margin-right:16px;'>"
            f"<span style='display:inline-block; width:24px; height:10px; "
            f"background:{clr}; border-radius:3px; margin-right:5px;'></span>"
            f"<span style='color:#475569; font-size:0.75rem;'>{num} {label}</span></span>"
            for num, clr, label in legend_items
        )
        st.markdown(
            f"<div style='margin-bottom:16px;'>{legend_html}</div>",
            unsafe_allow_html=True,
        )
        st.divider()


# ── New Page: Holland Code × Career Explorer Skills Comparison ────


def render_holland_skills_page():
    _scroll_to_top()

    best_codes   = st.session_state.get("holland_best_nocs", [])
    worth_codes  = st.session_state.get("holland_worth_nocs", [])
    best_titles  = st.session_state.get("holland_best_titles", {})
    worth_titles = st.session_state.get("holland_worth_titles", {})
    ce_top_nocs  = st.session_state.get("ce_top_nocs", [])
    geo          = st.session_state.get("geo", "Canada")

    with st.sidebar:
        st.markdown(
            '<div style="font-size:.72rem;font-weight:700;letter-spacing:.08em;'
            'text-transform:uppercase;color:#9CA3AF;margin-bottom:10px">'
            'Holland Code × Career Explorer</div>',
            unsafe_allow_html=True,
        )
        if st.button("← Back to Career Explorer", use_container_width=True, key="hsk_back"):
            st.session_state["wizard_page"] = "career_exploration"
            st.rerun()
        _holland_sidebar_button("holland_skills")

    st.title("Holland Code × Career Explorer — Skills Comparison")
    st.caption(
        "Job skills for your Holland Code career matches (Best Fit & Worth Exploring) "
        "compared with your field-of-study occupations."
    )

    if not best_codes and not worth_codes:
        st.warning(
            "No Holland Code NOC data found. "
            "Please complete the **Holland Code Test** in the sidebar first."
        )
        return

    # ── Build ordered NOC lists ───────────────────────────────
    def _make_noc_list(codes, titles_dict):
        return [{"code": c, "name": titles_dict.get(c, "")} for c in codes if c]

    best_nocs  = _make_noc_list(best_codes,  best_titles)
    worth_nocs = _make_noc_list(worth_codes, worth_titles)

    # ── Group legend banner ───────────────────────────────────
    groups = []
    if best_nocs:
        groups.append(('<span style="background:#D1FAE5;color:#065F46;border:1px solid #6EE7B7;'
                       'border-radius:6px;padding:3px 10px;font-size:.73rem;font-weight:700">'
                       '● Best Fit</span>', len(best_nocs)))
    if worth_nocs:
        groups.append(('<span style="background:#FEF3C7;color:#92400E;border:1px solid #FCD34D;'
                       'border-radius:6px;padding:3px 10px;font-size:.73rem;font-weight:700">'
                       '● Worth Exploring</span>', len(worth_nocs)))
    if ce_top_nocs:
        groups.append(('<span style="background:#EDE9FE;color:#4C1D95;border:1px solid #C4B5FD;'
                       'border-radius:6px;padding:3px 10px;font-size:.73rem;font-weight:700">'
                       '● Your Field of Study</span>', len(ce_top_nocs)))
    legend_html = " &nbsp; ".join(f'{badge} <span style="color:#6B7280;font-size:.73rem">({n} NOCs)</span>'
                                   for badge, n in groups)
    st.markdown(f'<div style="margin-bottom:20px">{legend_html}</div>', unsafe_allow_html=True)

    # ── Fetch skills ─────────────────────────────────────────
    all_ordered_nocs = best_nocs + worth_nocs + ce_top_nocs
    # deduplicate while preserving order
    seen_codes: set = set()
    unique_nocs = []
    for n in all_ordered_nocs:
        if n["code"] not in seen_codes:
            seen_codes.add(n["code"])
            unique_nocs.append(n)

    all_skills: dict = {}
    with st.spinner("Fetching skills data from Job Bank…"):
        for noc in unique_nocs:
            all_skills[noc["code"]] = fetch_jobbank_skills(noc["code"], geo)

    has_data = any(
        s.get("skills") or s.get("work_styles") or s.get("knowledge")
        for s in all_skills.values()
    )
    if not has_data:
        st.warning("Could not retrieve skills data from Job Bank for these occupations.")
        return

    # ── Build styled column headers ───────────────────────────
    def _col_header(noc, group_color, group_text_color, group_border):
        s = all_skills.get(noc["code"], {})
        title = s.get("title") or noc["name"] or noc["code"]
        return (
            f"<th style='background:{group_color};color:{group_text_color};"
            f"padding:5px 4px;font-size:0.68rem;font-weight:700;text-align:center;"
            f"min-width:90px;border-right:1px solid {group_border};border-bottom:2px solid {group_border};'>"
            f"{title}<br>"
            f"<span style='font-weight:500;opacity:0.85;font-size:0.62rem;'>NOC {noc['code']}</span></th>"
        )

    header_cells = ""
    for noc in best_nocs:
        header_cells += _col_header(noc, "#D1FAE5", "#065F46", "#6EE7B7")
    for noc in worth_nocs:
        header_cells += _col_header(noc, "#FEF3C7", "#92400E", "#FCD34D")
    for noc in ce_top_nocs:
        header_cells += _col_header(noc, "#EDE9FE", "#4C1D95", "#C4B5FD")

    # Group spanning row
    def _group_span(label, n_cols, bg, color, border):
        return (
            f"<th colspan='{n_cols}' style='background:{bg};color:{color};"
            f"padding:5px 8px;font-size:0.68rem;font-weight:700;text-align:center;"
            f"border-right:2px solid {border};border-bottom:1px solid {border};'>{label}</th>"
        )

    group_header = "<th style='background:#1E293B;'></th>"  # skill name col spacer
    group_header += "<th style='background:#374151;color:#FDE68A;padding:6px 8px;font-size:0.8rem;font-weight:700;text-align:center;min-width:110px;border-right:2px solid rgba(255,255,255,.3);'>Avg</th>"  # avg col spacer
    if best_nocs:
        group_header += _group_span("Best Fit", len(best_nocs), "#059669", "#fff", "#6EE7B7")
    if worth_nocs:
        group_header += _group_span("Worth Exploring", len(worth_nocs), "#D97706", "#fff", "#FCD34D")
    if ce_top_nocs:
        group_header += _group_span("Your Field of Study", len(ce_top_nocs), "#6366F1", "#fff", "#C4B5FD")

    # ── Color maps ────────────────────────────────────────────
    _COLORS_5 = {5: "#DC2626", 4: "#EA580C", 3: "#D97706", 2: "#8B6C4F", 1: "#9CA3AF"}
    _COLORS_3 = {3: "#DC2626", 2: "#8B6C4F", 1: "#9CA3AF"}

    def _badge(value, color_map):
        clr = color_map.get(round(value), "#9CA3AF")
        return (
            f"<span style='display:inline-block;min-width:22px;text-align:center;"
            f"background:{clr};color:#FFF;padding:2px 6px;border-radius:5px;"
            f"font-size:0.78rem;font-weight:700;line-height:1.3;'>{int(value)}</span>"
        )

    def _avg_bar(value, max_score, color_map):
        clr = color_map.get(round(value), "#9CA3AF")
        pct = value / max_score * 100
        display = f"{value:.1f}" if value != int(value) else str(int(value))
        return (
            f"<div style='display:flex;align-items:center;gap:5px;min-width:90px;'>"
            f"<div style='flex:1;background:#E5E7EB;border-radius:4px;height:10px;overflow:hidden;'>"
            f"<div style='width:{pct:.0f}%;height:100%;background:{clr};border-radius:4px;'></div></div>"
            f"<span style='font-size:0.78rem;font-weight:700;color:{clr};min-width:24px;text-align:right;'>{display}</span></div>"
        )

    SECTIONS = [
        ("skills",      "Skills",      "Proficiency / Complexity Level"),
        ("work_styles", "Work Styles", "Importance"),
        ("knowledge",   "Knowledge",   "Knowledge Level"),
    ]

    n_total = len(best_nocs) + len(worth_nocs) + len(ce_top_nocs)

    for section_key, section_title, level_label in SECTIONS:
        st.header(section_title)
        st.caption(f"Comparison of {section_title.lower()} — {level_label}")

        is_knowledge = section_key == "knowledge"
        color_map = _COLORS_3 if is_knowledge else _COLORS_5
        max_score = 3 if is_knowledge else 5

        # Collect all unique skill names
        all_names = []
        seen_names: set = set()
        for n in unique_nocs:
            for item in all_skills.get(n["code"], {}).get(section_key, []):
                if item["name"] not in seen_names:
                    seen_names.add(item["name"])
                    all_names.append(item["name"])

        if not all_names:
            st.info(f"No {section_title.lower()} data available.")
            st.divider()
            continue

        # Build lookup per NOC
        noc_lookups: dict = {}
        for n in unique_nocs:
            lookup = {}
            for item in all_skills.get(n["code"], {}).get(section_key, []):
                lookup[item["name"]] = item["level"]
            noc_lookups[n["code"]] = lookup

        rows_html = ""
        for skill_name in all_names:
            noc_cells = ""
            scores = []
            for noc in best_nocs + worth_nocs + ce_top_nocs:
                level = noc_lookups.get(noc["code"], {}).get(skill_name)
                if level:
                    num_int = int(level[0]) if level[0].isdigit() else 0
                    scores.append(num_int)
                    cell_content = _badge(num_int, color_map)
                else:
                    scores.append(0)
                    cell_content = "<span style='color:#CBD5E1;font-size:0.75rem;'>N/A</span>"
                noc_cells += (
                    f"<td style='padding:3px 4px;text-align:center;vertical-align:middle;"
                    f"border-bottom:1px solid #E2E8F0;border-right:1px solid #F1F5F9;'>"
                    f"{cell_content}</td>"
                )

            avg = sum(scores) / n_total if n_total > 0 else 0
            avg_cell = (
                f"<td style='padding:3px 8px;vertical-align:middle;"
                f"border-bottom:1px solid #E2E8F0;border-right:2px solid #E2E8F0;"
                f"background:#F1F5F9;'>{_avg_bar(avg, max_score, color_map)}</td>"
            )

            rows_html += (
                f"<tr>"
                f"<td style='padding:3px 8px;font-weight:500;color:#1E293B;background:#FAFBFC;"
                f"vertical-align:middle;border-bottom:1px solid #E2E8F0;border-right:1px solid #E2E8F0;"
                f"font-size:0.8rem;line-height:1.3;'>{skill_name}</td>"
                f"{avg_cell}{noc_cells}</tr>"
            )

        n_nocs = len(best_nocs) + len(worth_nocs) + len(ce_top_nocs)
        col_defs = (
            "<colgroup>"
            "<col style='width:200px;'/>"
            "<col style='width:130px;'/>"
            + "".join("<col style='width:80px;'/>" for _ in range(n_nocs))
            + "</colgroup>"
        )
        avg_header = (
            "<th style='background:#374151;color:#FDE68A;"
            "padding:6px 8px;font-size:0.8rem;font-weight:700;text-align:center;"
            "min-width:110px;border-right:2px solid rgba(255,255,255,0.3);'>Avg</th>"
        )

        table_html = (
            f"<div style='overflow-x:auto;border:1px solid #E2E8F0;border-radius:12px;"
            f"box-shadow:0 1px 3px rgba(0,0,0,0.04);margin-bottom:8px;'>"
            f"<table style='width:100%;border-collapse:collapse;table-layout:fixed;'>"
            f"{col_defs}"
            f"<thead>"
            f"<tr>{group_header}</tr>"
            f"<tr>"
            f"<th style='background:#1E293B;color:white;padding:6px 8px;font-size:0.8rem;"
            f"font-weight:600;text-align:left;border-right:1px solid rgba(255,255,255,0.15);'>{level_label}</th>"
            f"{avg_header}{header_cells}"
            f"</tr></thead>"
            f"<tbody>{rows_html}</tbody>"
            f"</table></div>"
        )
        st.markdown(table_html, unsafe_allow_html=True)

        if is_knowledge:
            legend_items = [("3", "#DC2626", "Advanced"), ("2", "#8B6C4F", "Intermediate"), ("1", "#9CA3AF", "Basic")]
        else:
            legend_items = [("5", "#DC2626", "Highest"), ("4", "#EA580C", "High"), ("3", "#D97706", "Moderate"), ("2", "#8B6C4F", "Low"), ("1", "#9CA3AF", "Basic")]
        legend_html = "".join(
            f"<span style='display:inline-flex;align-items:center;margin-right:16px;'>"
            f"<span style='display:inline-block;width:24px;height:10px;background:{clr};"
            f"border-radius:3px;margin-right:5px;'></span>"
            f"<span style='color:#475569;font-size:0.75rem;'>{num} {label}</span></span>"
            for num, clr, label in legend_items
        )
        st.markdown(f"<div style='margin-bottom:16px;'>{legend_html}</div>", unsafe_allow_html=True)
        st.divider()


# ── New Page: CE Wages / Income Analysis ─────────────────────────


def render_ce_wages_page():
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field

    top_nocs = st.session_state.get("ce_top_nocs", [])

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        hc = st.session_state.get("holland_code")
        if hc:
            st.write(f"**Holland Code:** {hc}")
        st.divider()
        if st.button("Back to Analysis", use_container_width=True, key="wages_back_analysis"):
            st.session_state["wizard_page"] = "ce_analysis"
            st.rerun()
        if st.button("Back to Career Exploration", use_container_width=True, key="wages_back_ce"):
            st.session_state["wizard_page"] = "career_exploration"
            st.rerun()
        if hc:
            if st.button("Interest-Based Analysis", use_container_width=True, key="interest_wages"):
                st.session_state["wizard_page"] = "ce_interest_analysis"
                st.rerun()
        _holland_sidebar_button("wages")

    # ── Header ─────────────────────────────────────────────────
    st.title("Career Exploration — Income Analysis")
    if cip_code and cip_name:
        st.info(f"**CIP {cip_code}** — {cip_name}  |  Location: **{geo}**")
    st.caption(
        "Hourly wage data (Low / Median / High) for the top occupations. "
        "Data from Job Bank Canada (jobbank.gc.ca)."
    )

    if not top_nocs:
        st.warning("No occupation data available. Please go back and run the analysis first.")
        return

    # ── Fetch wages for all NOCs ──────────────────────────────
    all_wages = {}
    with st.spinner("Fetching wage data from Job Bank..."):
        for noc in top_nocs:
            all_wages[noc["code"]] = fetch_jobbank_wages(noc["code"], geo)

    has_data = any(w.get("wages") for w in all_wages.values())
    if not has_data:
        st.warning("Could not retrieve wage data from Job Bank for these occupations.")
        return

    # ── Wage Comparison Table ─────────────────────────────────
    st.header("Wage Comparison ($/hour)")
    st.caption(f"Hourly wages for the top occupations in **{geo}**.")

    # Build HTML table
    n_nocs = len(top_nocs)
    col_defs = (
        "<colgroup>"
        "<col style='width:200px;'/>"
        + "".join(f"<col style='width:{max(100, 500 // n_nocs)}px;'/>" for _ in range(n_nocs))
        + "</colgroup>"
    )

    # Header row
    header_cells = "<th style='text-align:left; padding:8px 10px; background:#F1F5F9; " \
                   "color:#334155; font-size:0.82rem; border-bottom:2px solid #CBD5E1;'>Occupation</th>"
    for noc in top_nocs:
        code = noc["code"]
        title = all_wages[code].get("title") or noc["name"].split(" ", 1)[-1] if " " in noc["name"] else code
        # Truncate long titles
        if len(title) > 25:
            title = title[:23] + "…"
        header_cells += (
            f"<th style='text-align:center; padding:8px 6px; background:#F1F5F9; "
            f"color:#334155; font-size:0.78rem; border-bottom:2px solid #CBD5E1;'>"
            f"<div style='font-weight:700;'>{code}</div>"
            f"<div style='font-weight:400; color:#64748B; font-size:0.72rem;'>{title}</div></th>"
        )

    # Wage color helper
    def _wage_cell(value):
        if value is None:
            return "<td style='text-align:center; padding:6px; color:#9CA3AF;'>—</td>"
        return (
            f"<td style='text-align:center; padding:6px; font-weight:600; "
            f"font-size:0.88rem; color:#1E293B;'>${value:.2f}</td>"
        )

    rows_html = ""
    for label, key in [("Low", "low"), ("Median", "median"), ("High", "high")]:
        # Row background colors
        if key == "low":
            bg = "#FEF2F2"
            label_color = "#9CA3AF"
        elif key == "median":
            bg = "#F0FDF4"
            label_color = "#16A34A"
        else:
            bg = "#EFF6FF"
            label_color = "#2563EB"

        row = (
            f"<tr style='background:{bg};'>"
            f"<td style='padding:8px 10px; font-weight:600; font-size:0.85rem; "
            f"color:{label_color};'>{label}</td>"
        )
        for noc in top_nocs:
            wages = all_wages[noc["code"]].get("wages", {})
            row += _wage_cell(wages.get(key))
        row += "</tr>"
        rows_html += row

    # Annual estimate row (median × 2080 hours)
    annual_row = (
        "<tr style='background:#FFF7ED; border-top:2px solid #CBD5E1;'>"
        "<td style='padding:8px 10px; font-weight:600; font-size:0.85rem; "
        "color:#EA580C;'>Est. Annual<br/><span style=\"font-size:0.7rem; font-weight:400; "
        "color:#94A3B8;\">(Median × 2,080 hrs)</span></td>"
    )
    for noc in top_nocs:
        wages = all_wages[noc["code"]].get("wages", {})
        med = wages.get("median")
        if med is not None:
            annual = med * 2080
            annual_row += (
                f"<td style='text-align:center; padding:6px; font-weight:700; "
                f"font-size:0.88rem; color:#EA580C;'>${annual:,.0f}</td>"
            )
        else:
            annual_row += "<td style='text-align:center; padding:6px; color:#9CA3AF;'>—</td>"
    annual_row += "</tr>"
    rows_html += annual_row

    table_html = (
        f"<table style='width:100%; border-collapse:collapse; table-layout:fixed; "
        f"border:1px solid #E2E8F0; border-radius:8px; overflow:hidden;'>"
        f"{col_defs}"
        f"<thead><tr>{header_cells}</tr></thead>"
        f"<tbody>{rows_html}</tbody></table>"
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Community Breakdown (expandable) ──────────────────────
    has_community = any(all_wages[n["code"]].get("community") for n in top_nocs)
    if has_community:
        st.divider()
        st.subheader("Regional Wage Breakdown")
        st.caption("Detailed wage data by community/region. Regions with no data indicate the occupation may not be present there.")

        # Full province list for Canada-level view
        _ALL_PROVINCES = [
            "Newfoundland and Labrador", "Prince Edward Island", "Nova Scotia",
            "New Brunswick", "Quebec", "Ontario", "Manitoba", "Saskatchewan",
            "Alberta", "British Columbia", "Yukon", "Northwest Territories", "Nunavut",
        ]

        _na_cell = (
            "<td style='text-align:center;padding:5px;font-size:0.82rem;"
            "color:#94A3B8;font-style:italic;' colspan='3'>"
            "No data — occupation may not be present in this region</td>"
        )

        for noc in top_nocs:
            community = all_wages[noc["code"]].get("community", [])
            # Build lookup: area name → data
            comm_lookup = {c["area"]: c for c in community}

            with st.expander(f"{noc['name']}", expanded=False):
                comm_rows = ""

                # If geo is Canada, ensure all provinces appear
                if geo == "Canada":
                    # First show provinces that have data (in data order)
                    shown = set()
                    for c in community:
                        shown.add(c["area"])
                        comm_rows += (
                            f"<tr>"
                            f"<td style='padding:5px 8px;font-size:0.82rem;color:#334155;'>{c['area']}</td>"
                            f"<td style='text-align:center;padding:5px;font-size:0.82rem;'>${c['low']:.2f}</td>"
                            f"<td style='text-align:center;padding:5px;font-size:0.82rem;"
                            f"font-weight:600;color:#16A34A;'>${c['median']:.2f}</td>"
                            f"<td style='text-align:center;padding:5px;font-size:0.82rem;'>${c['high']:.2f}</td>"
                            f"</tr>"
                        )
                    # Then append missing provinces
                    for prov in _ALL_PROVINCES:
                        if prov not in shown:
                            comm_rows += (
                                f"<tr style='background:#FAFAFA;'>"
                                f"<td style='padding:5px 8px;font-size:0.82rem;color:#94A3B8;'>{prov}</td>"
                                f"{_na_cell}</tr>"
                            )
                else:
                    if community:
                        for c in community:
                            comm_rows += (
                                f"<tr>"
                                f"<td style='padding:5px 8px;font-size:0.82rem;color:#334155;'>{c['area']}</td>"
                                f"<td style='text-align:center;padding:5px;font-size:0.82rem;'>${c['low']:.2f}</td>"
                                f"<td style='text-align:center;padding:5px;font-size:0.82rem;"
                                f"font-weight:600;color:#16A34A;'>${c['median']:.2f}</td>"
                                f"<td style='text-align:center;padding:5px;font-size:0.82rem;'>${c['high']:.2f}</td>"
                                f"</tr>"
                            )
                    else:
                        comm_rows = (
                            "<tr><td colspan='4' style='padding:10px;text-align:center;"
                            "color:#94A3B8;font-style:italic;font-size:0.82rem;'>"
                            "No regional wage data available for this occupation</td></tr>"
                        )

                comm_table = (
                    "<table style='width:100%; border-collapse:collapse;'>"
                    "<thead><tr>"
                    "<th style='text-align:left; padding:5px 8px; font-size:0.78rem; "
                    "background:#F1F5F9; color:#64748B;'>Community</th>"
                    "<th style='text-align:center; padding:5px; font-size:0.78rem; "
                    "background:#F1F5F9; color:#64748B;'>Low</th>"
                    "<th style='text-align:center; padding:5px; font-size:0.78rem; "
                    "background:#F1F5F9; color:#64748B;'>Median</th>"
                    "<th style='text-align:center; padding:5px; font-size:0.78rem; "
                    "background:#F1F5F9; color:#64748B;'>High</th>"
                    "</tr></thead>"
                    f"<tbody>{comm_rows}</tbody></table>"
                )
                st.markdown(comm_table, unsafe_allow_html=True)

    # ── Quadrant Bubble Chart ─────────────────────────────────
    st.divider()
    st.header("Occupation Quadrant — Employment Count vs Income")
    st.caption(
        "Each bubble represents a specific occupation (5-digit NOC). "
        "X-axis: employment count (more people → further right). "
        "Y-axis: median income for age 25-64 (higher → more income). "
        "Bubble size: employment share (larger bubble = higher proportion of graduates)."
    )

    # Re-fetch NOC distribution for the quadrant chart
    noc_result = None
    try:
        with st.spinner("Querying occupation data for quadrant chart..."):
            noc_result = fetch_noc_distribution(cip_code, broad_field, education, geo)
    except Exception as e:
        st.error(f"Error loading occupation data: {e}")
        if st.button("Clear cache and retry", key="quad_retry_noc"):
            st.cache_data.clear()
            st.rerun()

    if noc_result and noc_result.get("detail_distribution"):
        try:
            with st.spinner("Querying income data for occupation quadrant..."):
                quadrant_data = fetch_noc_income_for_quadrant(
                    noc_result["detail_distribution"],
                    cip_code,
                    broad_field,
                    education,
                )
            if quadrant_data:
                # Mark the top 5 NOCs with a distinct color
                top_codes = {n["code"] for n in top_nocs}
                st.plotly_chart(
                    noc_quadrant_bubble(
                        quadrant_data,
                        oasis_noc_set=top_codes,
                        highlight_label="Your Selected Occupations",
                    ),
                    use_container_width=True,
                )

                # Compact quadrant legend
                q1, q2, q3, q4, q5 = st.columns(5)
                q1.markdown(
                    '<span style="color:#10B981;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Many + High Pay</span>',
                    unsafe_allow_html=True,
                )
                q2.markdown(
                    '<span style="color:#6366F1;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Few + High Pay</span>',
                    unsafe_allow_html=True,
                )
                q3.markdown(
                    '<span style="color:#F59E0B;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Many + Lower Pay</span>',
                    unsafe_allow_html=True,
                )
                q4.markdown(
                    '<span style="color:#F43F5E;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Few + Lower Pay</span>',
                    unsafe_allow_html=True,
                )
                q5.markdown(
                    '<span style="color:#0EA5E9;font-size:1.2rem;">&#9679;</span> '
                    '<span style="font-size:0.82rem;">Your Selected Occupations</span>',
                    unsafe_allow_html=True,
                )
                st.caption("Bubble size = share of graduates.")
            else:
                st.info("Could not retrieve income data for the occupation quadrant chart.")
        except Exception as e:
            st.error(f"Error loading quadrant data: {e}")
            st.code(traceback.format_exc())
    else:
        st.info("Occupation distribution data not available for the quadrant chart.")


# ── Holland Code RIASEC Test Data ──────────────────────────────────

HOLLAND_QUESTIONS = {
    "R": ["Test the quality of parts before shipment", "Lay brick or tile", "Work on an offshore oil-drilling rig", "Assemble electronic parts", "Operate a grinding machine in a factory", "Fix a broken faucet", "Assemble products in a factory", "Install flooring in houses"],
    "I": ["Study the structure of the human body", "Study animal behavior", "Do research on plants or animals", "Develop a new medical treatment or procedure", "Conduct biological research", "Study whales and other types of marine life", "Work in a biology lab", "Make a map of the bottom of an ocean"],
    "A": ["Conduct a musical choir", "Direct a play", "Design artwork for magazines", "Write a song", "Write books or plays", "Play a musical instrument", "Perform stunts for a movie or television show", "Design sets for plays"],
    "S": ["Give career guidance to people", "Do volunteer work at a non-profit organization", "Help people who have problems with drugs or alcohol", "Teach an individual an exercise routine", "Help people with family-related problems", "Supervise the activities of children at a camp", "Teach children how to read", "Help elderly people with their daily activities"],
    "E": ["Sell restaurant franchises to individuals", "Sell merchandise at a department store", "Manage the operations of a hotel", "Operate a beauty salon or barber shop", "Manage a department within a large company", "Manage a clothing store", "Sell houses", "Run a toy store"],
    "C": ["Generate the monthly payroll checks for an office", "Inventory supplies using a hand-held computer", "Use a computer program to generate customer bills", "Maintain employee records", "Compute and record statistical and other numerical data", "Operate a calculator", "Handle customers bank transactions", "Keep shipping and receiving records"],
}

HOLLAND_TYPE_INFO = {
    "R": {"name": "Realistic",     "color": "#EF4444", "traits": "Practical, hands-on, physical, mechanical, tool-oriented", "description": "You prefer working with things — tools, machines, plants, or animals. You value practical, tangible results.", "careers": "Mechanic, Electrician, Engineer, Pilot, Carpenter, Forestry Technician"},
    "I": {"name": "Investigative", "color": "#3B82F6", "traits": "Analytical, curious, intellectual, scientific, methodical",  "description": "You enjoy researching, analyzing, and solving complex problems. You thrive on learning and discovery.",       "careers": "Scientist, Researcher, Doctor, Data Analyst, Economist, Pharmacist"},
    "A": {"name": "Artistic",      "color": "#A855F7", "traits": "Creative, expressive, original, imaginative, independent",  "description": "You value self-expression and creativity. You prefer unstructured environments where you can innovate.",    "careers": "Designer, Writer, Musician, Actor, Photographer, Art Director"},
    "S": {"name": "Social",        "color": "#10B981", "traits": "Helpful, empathetic, cooperative, patient, supportive",     "description": "You enjoy helping, teaching, counselling, and serving others. You are drawn to roles that make a difference.", "careers": "Teacher, Counsellor, Nurse, Social Worker, Therapist, HR Specialist"},
    "E": {"name": "Enterprising",  "color": "#F59E0B", "traits": "Ambitious, energetic, persuasive, competitive, confident",  "description": "You like leading, persuading, and managing. You enjoy taking risks and making things happen.",             "careers": "Manager, Entrepreneur, Sales Director, Lawyer, Real Estate Agent, Marketing Executive"},
    "C": {"name": "Conventional",  "color": "#6366F1", "traits": "Organized, detail-oriented, systematic, efficient, reliable", "description": "You prefer structured environments with clear rules. You excel at organizing data and following procedures.", "careers": "Accountant, Auditor, Administrative Assistant, Bank Teller, Bookkeeper, Tax Preparer"},
}

RIASEC_ORDER = ["R", "I", "A", "S", "E", "C"]

_HC_SCALE_LABELS = ["1 – Dislike", "2 – Slightly", "3 – Neutral", "4 – Somewhat", "5 – Enjoy"]

_HC_TYPE_NAMES = {"R": "Realistic", "I": "Investigative", "A": "Artistic", "S": "Social", "E": "Enterprising", "C": "Conventional"}

_HC_ADJACENT_PAIRS = {frozenset(("R", "I")), frozenset(("I", "A")), frozenset(("A", "S")), frozenset(("S", "E")), frozenset(("E", "C")), frozenset(("C", "R"))}
_HC_OPPOSITE_PAIRS = {frozenset(("R", "S")), frozenset(("I", "E")), frozenset(("A", "C"))}
_HC_HEX_ANGLES = {"R": -90, "I": -30, "A": 30, "S": 90, "E": 150, "C": 210}

_HC_DIMENSION_DETAILS = {
    "R": {"tasks": "Operating tools, machinery, and equipment; outdoor physical work; hands-on repair and construction", "env": "Factories, construction sites, labs, outdoors — emphasis on tangible, physical work", "behavior": "Prefers concrete tasks with visible outcomes; values efficiency and practicality"},
    "I": {"tasks": "Research, analysis, experimentation, data interpretation, theoretical modelling", "env": "Laboratories, research institutions, academia — emphasis on independent thinking and deep inquiry", "behavior": "Highly curious; enjoys asking questions and solving complex problems; values evidence and logic"},
    "A": {"tasks": "Creative work, design, performance, writing, and visual arts", "env": "Studios, theatres, design firms, freelance settings — emphasis on autonomy and creative freedom", "behavior": "Pursues originality and aesthetic expression; dislikes repetitive rules; values personal voice"},
    "S": {"tasks": "Teaching, counselling, nursing, social services, and team collaboration", "env": "Schools, hospitals, community organizations, non-profits — emphasis on human connection", "behavior": "Attuned to others' needs; skilled at listening and communication; values cooperation"},
    "E": {"tasks": "Managing, selling, negotiating, entrepreneurship, and project leadership", "env": "Companies, sales teams, executive roles, start-ups — emphasis on influence and results", "behavior": "Enjoys leading and persuading; willing to take risks; pursues achievement and status"},
    "C": {"tasks": "Data entry, file management, financial accounting, and process execution", "env": "Offices, financial institutions, administrative departments — emphasis on order and procedure", "behavior": "Detail-oriented and precise; prefers structured, rule-governed work styles"},
}

_HC_SVGS = {
    "R": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    "I": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>',
    "A": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    "S": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
    "E": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/></svg>',
    "C": '<svg width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="{c}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="9" x2="9" y2="21"/><line x1="15" y1="9" x2="15" y2="21"/></svg>',
}

_HC_SYSTEM_PROMPT = """You are a rigorous Holland Code / RIASEC career interest assessment interpreter with deep expertise in the Canadian NOC (National Occupational Classification) system. Your task is not to predict destiny, but to clearly explain the interest structure and provide verifiable, actionable exploration suggestions grounded in real career data.

Global constraints:
1. Interest ≠ ability. Never make deterministic judgements.
2. Do not merely list job titles — explain core tasks, work environment, daily activities, and why each career fits the user's specific interest structure.
3. When scores are close, explicitly flag the uncertainty and note what needs further validation.
4. Language must be professional, clear, and measured. Avoid generic encouragement or filler phrases.
5. Output entirely in English.
6. Do not include any internal reasoning or thinking process — output only the final report.
7. Each layer must be detailed, specific, and substantive. Avoid vague generalisations.
8. All career direction discussions must draw on the provided NOC occupation data."""

# ── Holland helper functions ───────────────────────────────────────

import math as _math
import re as _re


def _hc_icon(letter, size=24, color=None):
    c = color or HOLLAND_TYPE_INFO[letter]["color"]
    return _HC_SVGS[letter].format(s=size, c=c)


def _hc_hex_pt(letter, radius, cx, cy):
    rad = _math.radians(_HC_HEX_ANGLES[letter])
    return cx + radius * _math.cos(rad), cy + radius * _math.sin(rad)


def _build_hex_svg(size, top3, scores, show_labels=False):
    cx = cy = size / 2
    R = size * 0.36
    hex_pts = " ".join(f"{_hc_hex_pt(t, R, cx, cy)[0]:.1f},{_hc_hex_pt(t, R, cx, cy)[1]:.1f}" for t in RIASEC_ORDER)
    score_pts = " ".join(f"{_hc_hex_pt(t, R * min(scores.get(t, 0), 5) / 5, cx, cy)[0]:.1f},{_hc_hex_pt(t, R * min(scores.get(t, 0), 5) / 5, cx, cy)[1]:.1f}" for t in RIASEC_ORDER)
    lines = ""
    for i in range(len(top3)):
        for j in range(i + 1, len(top3)):
            a, b = top3[i], top3[j]
            x1, y1 = _hc_hex_pt(a, R, cx, cy)
            x2, y2 = _hc_hex_pt(b, R, cx, cy)
            pair = frozenset((a, b))
            if pair in _HC_ADJACENT_PAIRS:
                lines += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#10B981" stroke-width="2" stroke-opacity="0.7"/>'
            elif pair in _HC_OPPOSITE_PAIRS:
                lines += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#F59E0B" stroke-width="1.5" stroke-dasharray="4,3" stroke-opacity="0.8"/>'
            else:
                lines += f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#9CA3AF" stroke-width="1" stroke-opacity="0.4"/>'
    nodes = ""
    for t in RIASEC_ORDER:
        x, y = _hc_hex_pt(t, R, cx, cy)
        is_top = t in top3
        color = HOLLAND_TYPE_INFO[t]["color"]
        r_dot = 11 if is_top else 6
        nodes += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r_dot}" fill="{color if is_top else "#E5E7EB"}" stroke="{(color + "50") if is_top else "#D1D5DB"}" stroke-width="2"/>'
        if is_top:
            nodes += f'<text x="{x:.1f}" y="{y + 1:.1f}" text-anchor="middle" dominant-baseline="middle" fill="white" font-size="9" font-weight="700" font-family="Inter,sans-serif">{t}</text>'
        if show_labels:
            lx, ly = _hc_hex_pt(t, R + 22, cx, cy)
            fc = color if is_top else "#9CA3AF"
            fw = "700" if is_top else "500"
            fs = 10 if is_top else 9
            nodes += f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle" dominant-baseline="middle" fill="{fc}" font-size="{fs}" font-weight="{fw}" font-family="Inter,sans-serif">{HOLLAND_TYPE_INFO[t]["name"]}</text>'
    return (
        f'<div style="display:flex;justify-content:center">'
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg">'
        f'<polygon points="{hex_pts}" fill="none" stroke="#E5E7EB" stroke-width="1.5"/>'
        f'<polygon points="{score_pts}" fill="rgba(99,102,241,0.08)" stroke="#6366F1" stroke-width="1.5" stroke-opacity="0.6"/>'
        f'{lines}{nodes}</svg></div>'
    )


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
        for j in range(i + 1, len(top3)):
            pair = frozenset((top3[i], top3[j]))
            if pair in _HC_ADJACENT_PAIRS:
                complements.append(f"{_HC_TYPE_NAMES[top3[i]]} and {_HC_TYPE_NAMES[top3[j]]} are adjacent — mutually reinforcing")
            elif pair in _HC_OPPOSITE_PAIRS:
                tensions.append(f"{_HC_TYPE_NAMES[top3[i]]} and {_HC_TYPE_NAMES[top3[j]]} are opposites — potential internal tension")
    certainties, uncertainties = [], []
    if gap_12 >= 1.0:
        certainties.append(f"Primary interest ({_HC_TYPE_NAMES[ranked[0]]}) is clearly dominant")
    else:
        uncertainties.append(f"Gap between 1st and 2nd is small ({gap_12:.1f}); needs further validation")
    if gap_23 <= 0.3:
        uncertainties.append(f"2nd and 3rd interests are very close ({gap_23:.1f}); ranking may shift by context")
    else:
        certainties.append("Top-3 code ordering is relatively stable")
    return {
        "sorted_types": [{"type": t, "name": _HC_TYPE_NAMES[t], "score": round(scores[t], 2)} for t in ranked],
        "top3": top3, "top3_names": [_HC_TYPE_NAMES[t] for t in top3],
        "gaps": {"gap_1_2": round(gap_12, 2), "gap_2_3": round(gap_23, 2), "gap_top3_max": round(gap_top3, 2), "gap_high_low": round(gap_hl, 2)},
        "structure_type": stype, "structure_desc": sdesc,
        "complements": complements, "tensions": tensions, "certainties": certainties, "uncertainties": uncertainties,
    }


def _hc_build_prompt(scores, rule, noc_data, stage, scenario, background):
    scores_str = " / ".join(f"{_HC_TYPE_NAMES[t]}={scores[t]:.2f}" for t in RIASEC_ORDER)
    top3_str = "".join(rule["top3"])
    dim_block = ""
    for t in RIASEC_ORDER:
        d = _HC_DIMENSION_DETAILS[t]
        dim_block += f"  - {_HC_TYPE_NAMES[t]}: tasks={d['tasks']}; env={d['env']}; behavior={d['behavior']}\n"
    noc_block = ""
    if noc_data and noc_data.get("success") and noc_data.get("matches"):
        noc_block = f"\n[OaSIS Matched NOC Occupations]\nTop-3 code {top3_str}:\n\n"
        for i, m in enumerate(noc_data["matches"], 1):
            code, title = m["code"], m["title"]
            noc_block += f"{i}. NOC {code} — {title}\n"
            desc = noc_data.get("descriptions", {}).get(code)
            if desc:
                if desc.get("example_titles"):
                    noc_block += f"   Titles: {', '.join(desc['example_titles'])}\n"
                if desc.get("main_duties"):
                    noc_block += "   Duties:\n"
                    for d2 in desc["main_duties"]:
                        noc_block += f"     - {d2}\n"
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


def _hc_get_api_config():
    try:
        base_url = st.secrets.get("QWEN_BASE_URL", "http://113.108.105.54:3000/v1")
        api_key = st.secrets.get("QWEN_API_KEY", "9e7d5b627e4ac73da50e5c1182a81b02bd43e34e16992c49b0ccc968ae4ad9b2")
    except Exception:
        import os as _os
        base_url = _os.environ.get("QWEN_BASE_URL", "http://113.108.105.54:3000/v1")
        api_key = _os.environ.get("QWEN_API_KEY", "9e7d5b627e4ac73da50e5c1182a81b02bd43e34e16992c49b0ccc968ae4ad9b2")
    return base_url, api_key


def _hc_qwen_stream(scores, rule, noc_data, stage, scenario, background):
    try:
        from openai import OpenAI as _OAI
    except ImportError:
        yield "openai package not installed. Run: pip install openai"
        return
    base_url, api_key = _hc_get_api_config()
    client = _OAI(base_url=base_url, api_key=api_key)
    prompt = _hc_build_prompt(scores, rule, noc_data, stage, scenario, background)
    stream = client.chat.completions.create(
        model="Qwen/Qwen3-32B", max_tokens=8000, stream=True,
        messages=[{"role": "system", "content": _HC_SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def _parse_layers(text):
    parts = _re.split(r'(?=##\s*Layer\s*\d)', text, flags=_re.IGNORECASE)
    layers = [""] * 5
    for i in range(5):
        m = next((p for p in parts if _re.match(rf'##\s*Layer\s*{i + 1}', p, _re.IGNORECASE)), None)
        if m:
            layers[i] = m.strip()
    return layers


# ── Interest-Based Analysis Page ──────────────────────────────────


def render_ce_interest_analysis_page():
    """Show occupation matches based on Holland Code interests vs CIP field."""
    _scroll_to_top()

    broad_field = st.session_state.get("broad_field") or "Total"
    subfield = st.session_state.get("subfield")
    cip_code = st.session_state.get("cip_code")
    cip_name = st.session_state.get("cip_name")
    education = st.session_state.get("education", "Bachelor's degree")
    geo = st.session_state.get("geo", "Canada")
    field_display = subfield or broad_field
    holland_code = st.session_state.get("holland_code", "")
    i1 = st.session_state.get("oasis_interest_1", "")
    i2 = st.session_state.get("oasis_interest_2", "")
    i3 = st.session_state.get("oasis_interest_3", "")

    # ── Sidebar ───────────────────────────────────────────────
    with st.sidebar:
        st.header("Your Profile")
        name = st.session_state.get("user_name", "")
        if name:
            st.write(f"**Name:** {name}")
        st.write(f"**Age:** {st.session_state.get('user_age', '—')}")
        st.write(f"**Gender:** {st.session_state.get('user_gender', '—')}")
        if cip_code and cip_name:
            st.write(f"**Major:** {cip_name} (CIP {cip_code})")
            st.write(f"**Broad field:** {broad_field}")
        else:
            st.write(f"**Field:** {field_display}")
        st.write(f"**Education:** {education}")
        st.write(f"**Province:** {geo}")
        if holland_code:
            st.write(f"**Holland Code:** {holland_code}")
        st.divider()
        if st.button("Back to Analysis", use_container_width=True, key="interest_back"):
            st.session_state["wizard_page"] = "ce_analysis"
            st.rerun()
        if st.button("Back to Career Exploration", use_container_width=True, key="interest_back_ce"):
            st.session_state["wizard_page"] = "career_exploration"
            st.rerun()
        _holland_sidebar_button("interest")

    # ── Header ─────────────────────────────────────────────────
    st.title("Interest-Based Career Analysis")
    if holland_code and i1 and i2 and i3:
        st.info(f"**Holland Code: {holland_code}** — {i1} > {i2} > {i3}")
    else:
        st.warning("No Holland Code results found. Please take the Holland Code Career Test first.")
        st.link_button(
            "▶  Take Holland Code Career Test",
            url=_HOLLAND_APP_URL,
            use_container_width=True,
            type="primary",
            key="interest_take_test",
        )
        return

    # ── Fetch OaSIS matches ────────────────────────────────────
    oasis_result = st.session_state.get("oasis_result")
    if not oasis_result or not oasis_result.get("success"):
        with st.spinner("Querying OaSIS interest-based occupation matches..."):
            oasis_result = fetch_oasis_matches(i1, i2, i3)
            st.session_state["oasis_result"] = oasis_result

    if not oasis_result.get("success"):
        st.error(f"OaSIS query failed: {oasis_result.get('error', 'Unknown error')}")
        if st.button("Retry", key="interest_retry_oasis"):
            st.session_state.pop("oasis_result", None)
            st.rerun()
        return

    oasis_matches = oasis_result.get("matches", [])
    oasis_noc_set = set(oasis_result.get("noc_codes", []))

    # ── Fetch NOC distribution (CIP-based) ─────────────────────
    noc_result = None
    try:
        with st.spinner("Querying occupation (NOC) distribution data..."):
            noc_result = fetch_noc_distribution(cip_code, broad_field, education, geo)
    except Exception:
        noc_result = None

    cip_noc_map = {}  # code -> {noc, percentage}
    if noc_result and noc_result.get("detail_distribution"):
        for occ in noc_result["detail_distribution"]:
            code = occ["noc"].split(" ", 1)[0]
            cip_noc_map[code] = occ

    cip_noc_set = set(cip_noc_map.keys())

    # ── Compare sets ───────────────────────────────────────────
    overlap_codes = oasis_noc_set & cip_noc_set
    interest_only_codes = oasis_noc_set - cip_noc_set
    field_only_codes = cip_noc_set - oasis_noc_set

    # ── Section 1: Best Match (overlap) ────────────────────────
    st.header("Best Match — Interest + Field Alignment")
    st.caption(
        "These occupations match both your Holland Code interests AND are common career "
        "paths for graduates in your field of study."
    )

    if overlap_codes:
        for code in sorted(overlap_codes):
            cip_entry = cip_noc_map.get(code, {})
            oasis_entry = next((m for m in oasis_matches if m.get("code") == code), {})
            noc_name = cip_entry.get("noc", oasis_entry.get("title", code))
            pct = cip_entry.get("percentage", 0)
            st.markdown(
                f'<div style="background:#ECFDF5;border:1px solid #A7F3D0;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:8px;">'
                f'<span style="font-weight:600;color:#065F46">{noc_name}</span>'
                + (f'<span style="float:right;color:#047857;font-size:0.85rem">'
                   f'{pct:.1f}% of graduates</span>' if pct else '')
                + '</div>',
                unsafe_allow_html=True,
            )
        st.success(f"**{len(overlap_codes)}** occupation(s) align with both your interests and field of study.")
    else:
        st.info(
            "No direct overlap found between your interest-matched occupations and "
            "typical career paths for your field. This is normal — explore the sections below "
            "for alternative career directions."
        )

    # ── Section 2: Interest-Based Alternatives ─────────────────
    st.header("Interest-Based Alternatives")
    st.caption(
        "These occupations match your Holland Code interests but are not typical "
        "career paths for your field. Consider these as alternative directions."
    )

    if interest_only_codes:
        interest_entries = [m for m in oasis_matches if m.get("code") in interest_only_codes]
        if not interest_entries:
            interest_entries = [{"code": c, "title": c} for c in sorted(interest_only_codes)]
        for entry in interest_entries[:20]:
            code = entry.get("code", "")
            title = entry.get("title", code)
            st.markdown(
                f'<div style="background:#EEF2FF;border:1px solid #C7D2FE;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:8px;">'
                f'<span style="font-weight:600;color:#3730A3">{code} {title}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
        if len(interest_only_codes) > 20:
            st.caption(f"Showing 20 of {len(interest_only_codes)} interest-matched occupations.")
    else:
        st.info("All interest-matched occupations overlap with your field of study.")

    # ── Section 3: Traditional Field Paths ─────────────────────
    st.header("Traditional Field Paths")
    st.caption(
        "These are the most common career paths for graduates in your field, "
        "even though they don't match your Holland Code interests."
    )

    if field_only_codes:
        # Sort by percentage descending
        sorted_field = sorted(
            field_only_codes,
            key=lambda c: cip_noc_map.get(c, {}).get("percentage", 0),
            reverse=True,
        )
        for code in sorted_field[:15]:
            entry = cip_noc_map.get(code, {})
            noc_name = entry.get("noc", code)
            pct = entry.get("percentage", 0)
            st.markdown(
                f'<div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:8px;'
                f'padding:10px 14px;margin-bottom:8px;">'
                f'<span style="font-weight:600;color:#9A3412">{noc_name}</span>'
                + (f'<span style="float:right;color:#C2410C;font-size:0.85rem">'
                   f'{pct:.1f}% of graduates</span>' if pct else '')
                + '</div>',
                unsafe_allow_html=True,
            )
        if len(field_only_codes) > 15:
            st.caption(f"Showing 15 of {len(field_only_codes)} field-specific occupations.")
    else:
        st.info("All field-specific occupations match your interests — great alignment!")

    # ── Summary ────────────────────────────────────────────────
    st.divider()
    total_oasis = len(oasis_noc_set)
    total_cip = len(cip_noc_set)
    st.markdown(
        f'<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:8px;'
        f'padding:14px;text-align:center;">'
        f'<span style="font-size:0.9rem;color:#475569;">'
        f'Interest matches: <strong>{total_oasis}</strong> &nbsp;|&nbsp; '
        f'Field occupations: <strong>{total_cip}</strong> &nbsp;|&nbsp; '
        f'Overlap: <strong>{len(overlap_codes)}</strong>'
        f'</span></div>',
        unsafe_allow_html=True,
    )


# ── Holland Code Career Test Pages ────────────────────────────────


def _render_holland_progress(current_step):
    """Render a progress dots bar for the Holland test (steps 1-6)."""
    # For step 7 (results), we still show full dots
    effective_step = min(current_step, 6)
    dots_html = '<div style="display:flex;align-items:center;gap:6px;margin-bottom:12px">'
    for i in range(6):
        if i < effective_step - 1:
            bg = "#111827"
        elif i == effective_step - 1:
            bg = "#6B7280"
        else:
            bg = "#E5E7EB"
        dots_html += f'<div style="height:4px;flex:1;border-radius:2px;background:{bg};transition:background .35s"></div>'
    dots_html += '</div>'
    step_names = {1: "Realistic", 2: "Investigative", 3: "Artistic", 4: "Social", 5: "Enterprising", 6: "Conventional"}
    label = step_names.get(effective_step, "Results")
    if current_step == 7:
        dots_html += f'<div style="display:flex;justify-content:space-between;font-size:.78rem;color:#9CA3AF;font-weight:500;margin-bottom:28px"><span style="color:#374151;font-weight:600">Results</span><span>Complete</span></div>'
    else:
        dots_html += f'<div style="display:flex;justify-content:space-between;font-size:.78rem;color:#9CA3AF;font-weight:500;margin-bottom:28px"><span style="color:#374151;font-weight:600">{label}</span><span>Step {current_step} of 6</span></div>'
    st.markdown(dots_html, unsafe_allow_html=True)


_HC_SCALE_CSS = """
<style>
.stRadio, .stRadio > div { margin-top: 0 !important; width: 100% !important; }
.stRadio [role="radiogroup"] { display: grid !important; grid-template-columns: repeat(5, 1fr) !important; gap: 6px !important; width: 100% !important; box-sizing: border-box !important; }
.stRadio [role="radiogroup"] label { width: 100% !important; box-sizing: border-box !important; display: flex !important; align-items: center !important; justify-content: center !important; text-align: center !important; border: 1px solid #E5E7EB !important; border-radius: 8px !important; padding: 10px 4px !important; margin: 0 !important; cursor: pointer !important; background: #fff !important; font-family: 'Inter', sans-serif !important; font-size: 0.62rem !important; font-weight: 500 !important; color: #6B7280 !important; transition: all .14s !important; overflow: hidden !important; position: relative !important; }
.stRadio [role="radiogroup"] label > div:first-child { position: absolute !important; width: 1px !important; height: 1px !important; overflow: hidden !important; opacity: 0 !important; }
.stRadio [role="radiogroup"] label > div:last-child { width: 100% !important; text-align: center !important; font-size: 0.62rem !important; line-height: 1.25 !important; }
.stRadio [role="radiogroup"] label:has(input:checked) { background: #111827 !important; color: #fff !important; border-color: #111827 !important; font-weight: 600 !important; }
.stRadio [role="radiogroup"] label:has(input:checked) p, .stRadio [role="radiogroup"] label:has(input:checked) span, .stRadio [role="radiogroup"] label:has(input:checked) div { color: #fff !important; }
.stRadio [role="radiogroup"] label:not(:has(input:checked)):hover { background: #F9FAFB !important; color: #374151 !important; border-color: #D1D5DB !important; }
</style>
"""


def _holland_scale_selector(key, q_num, question):
    """Render a question card with a horizontal radio scale, storing into _holland_answers."""
    # Initialize default using _ans_ key (bug-fix: check _ans_ prefix)
    if f"_ans_{key}" not in st.session_state:
        saved = st.session_state.get("_holland_answers", {}).get(key, 3)
        st.session_state[f"_ans_{key}"] = saved
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
        format_func=lambda x: _HC_SCALE_LABELS[x - 1],
        horizontal=True,
        key=f"_ans_{key}",
        label_visibility="collapsed",
    )


def _render_holland_question_page(step):
    """Render one question page (step 1-6), each with 8 questions of one RIASEC type."""
    st.markdown(_HC_SCALE_CSS, unsafe_allow_html=True)

    type_letter = RIASEC_ORDER[step - 1]
    type_info = HOLLAND_TYPE_INFO[type_letter]
    questions = HOLLAND_QUESTIONS[type_letter]

    _render_holland_progress(step)

    # Quiz hero card
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:18px;margin-bottom:28px;padding:22px 24px;background:#fff;border:1px solid #E5E7EB;border-radius:16px">'
        f'<div style="width:52px;height:52px;border-radius:14px;background:{type_info["color"]}12;display:flex;align-items:center;justify-content:center;flex-shrink:0">{_hc_icon(type_letter, 26, type_info["color"])}</div>'
        f'<div><div style="font-size:1.2rem;font-weight:700;color:#111827;letter-spacing:-.02em">{type_info["name"]}</div>'
        f'<div style="font-size:.83rem;color:#9CA3AF;margin-top:3px">Rate how much you\'d enjoy each activity — 1 (Dislike) to 5 (Enjoy)</div></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Questions with custom scale selector
    answers = st.session_state.get("_holland_answers", {})
    for i, q in enumerate(questions):
        key = f"{type_letter}_{i}"
        if f"_ans_{key}" not in st.session_state:
            st.session_state[f"_ans_{key}"] = answers.get(key, 3)
        q_num = (step - 1) * 8 + i + 1
        _holland_scale_selector(key, q_num, q)
        st.markdown('<div style="height:2px"></div>', unsafe_allow_html=True)

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    col_back, col_next = st.columns(2, gap="small")
    with col_back:
        if step > 1:
            back_label = "← Back"
        else:
            back_label = "← Exit Test"
        if st.button(back_label, use_container_width=True, key="hc_back"):
            if step > 1:
                st.session_state["_holland_step"] = step - 1
            else:
                prev = st.session_state.get("_holland_prev_page", "career_exploration")
                st.session_state["wizard_page"] = prev
            st.rerun()
    with col_next:
        next_label = "View Results →" if step == 6 else "Continue →"
        if st.button(next_label, type="primary", use_container_width=True, key="hc_next"):
            # Save answers from _ans_ keys into _holland_answers
            ans = st.session_state.get("_holland_answers", {})
            for i in range(8):
                k = f"{type_letter}_{i}"
                ans[k] = st.session_state.get(f"_ans_{k}", 3)
            st.session_state["_holland_answers"] = ans
            if step < 6:
                st.session_state["_holland_step"] = step + 1
            else:
                st.session_state["_holland_step"] = 7
            st.rerun()


def _render_holland_results():
    """Step 7: show RIASEC results with hexagon SVG, radar chart, Holland Code, and descriptions."""
    st.markdown(_HC_SCALE_CSS, unsafe_allow_html=True)

    answers = st.session_state.get("_holland_answers", {})
    scores = {}
    for t in RIASEC_ORDER:
        vals = [answers.get(f"{t}_{i}", 3) for i in range(8)]
        scores[t] = sum(vals) / len(vals)

    ranked = sorted(RIASEC_ORDER, key=lambda t: scores[t], reverse=True)
    top3 = ranked[:3]
    holland_code = "".join(top3)

    # Auto-save Holland Code and interests to session state
    st.session_state["holland_code"] = holland_code
    st.session_state["_holland_scores"] = scores
    st.session_state["_holland_top3"] = top3
    for i, t in enumerate(top3, 1):
        st.session_state[f"oasis_interest_{i}"] = HOLLAND_TYPE_INFO[t]["name"]

    _render_holland_progress(7)

    # Hero
    st.markdown(
        f'<div style="padding:8px 0 32px">'
        f'<div style="font-size:.72rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:#6B7280;margin-bottom:10px">Your Results</div>'
        f'<h1 style="font-size:2rem;font-weight:700;letter-spacing:-.03em;color:#111827;margin-bottom:6px">Holland Code: <span style="letter-spacing:.05em">{holland_code}</span></h1>'
        f'<p style="font-size:.9rem;color:#9CA3AF">Based on your responses across 48 activities</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Code chips
    chips_html = '<div style="background:#fff;border:1px solid #E5E7EB;border-radius:20px;padding:28px 24px;margin-bottom:28px;text-align:center"><div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin-bottom:20px">Your Personality Code</div><div style="display:flex;justify-content:center;gap:12px;flex-wrap:wrap">'
    for t in top3:
        info = HOLLAND_TYPE_INFO[t]
        chips_html += (
            f'<div style="display:flex;flex-direction:column;align-items:center;gap:8px;padding:18px 22px;border-radius:16px;min-width:88px;background:{info["color"]}0d;border:1.5px solid {info["color"]}35">'
            f'{_hc_icon(t, 24, info["color"])}'
            f'<div style="font-size:1.6rem;font-weight:700;color:{info["color"]};line-height:1">{t}</div>'
            f'<div style="font-size:.7rem;font-weight:600;color:#9CA3AF">{info["name"]}</div>'
            f'</div>'
        )
    chips_html += '</div></div>'
    st.markdown(chips_html, unsafe_allow_html=True)

    # Radar chart
    st.markdown('<div style="background:#fff;border:1px solid #E5E7EB;border-radius:20px;padding:24px;margin-bottom:28px">', unsafe_allow_html=True)
    fig = holland_radar_chart(scores)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
    st.markdown('</div>', unsafe_allow_html=True)

    # Deep Analysis CTA
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1e1b4b 0%,#312e81 100%);border-radius:20px;padding:28px;margin-bottom:28px;color:#fff">'
        '<div style="font-size:1.1rem;font-weight:700;margin-bottom:8px">Ready for Deep Analysis?</div>'
        '<div style="font-size:.83rem;opacity:.75;line-height:1.6;margin-bottom:20px">Get a 5-layer AI-powered interpretation — dimensions, code identity, score structure, internal tensions, and career mapping grounded in real NOC data.</div>'
        '</div>',
        unsafe_allow_html=True,
    )


    # Top 3 cards
    st.markdown('<div style="font-size:.7rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#9CA3AF;margin:8px 0 14px">Your Top 3 Types</div>', unsafe_allow_html=True)
    for rank, t in enumerate(top3, 1):
        info = HOLLAND_TYPE_INFO[t]
        traits_list = "".join(
            f'<span style="font-size:.71rem;font-weight:500;color:#6B7280;background:#F9FAFB;border:1px solid #E5E7EB;border-radius:6px;padding:3px 9px;margin:2px">{tr.strip()}</span>'
            for tr in info["traits"].split(",")
        )
        st.markdown(
            f'<div style="background:#fff;border:1px solid #E5E7EB;border-left:3px solid {info["color"]};border-radius:16px;padding:22px;margin-bottom:12px">'
            f'<div style="display:flex;align-items:center;gap:14px;margin-bottom:12px">'
            f'<div style="width:44px;height:44px;border-radius:12px;background:{info["color"]}12;display:flex;align-items:center;justify-content:center;flex-shrink:0">{_hc_icon(t, 22, info["color"])}</div>'
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
            info = HOLLAND_TYPE_INFO[t]
            pct = int((scores[t] / 5) * 100)
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid #F9FAFB">'
                f'<div style="width:28px;height:28px;border-radius:7px;background:{info["color"]}10;display:flex;align-items:center;justify-content:center">{_hc_icon(t, 14, info["color"])}</div>'
                f'<div style="font-size:.82rem;font-weight:600;color:#374151;min-width:105px">{info["name"]}</div>'
                f'<div style="flex:1;height:5px;background:#F3F4F6;border-radius:3px;overflow:hidden"><div style="width:{pct}%;height:100%;background:{info["color"]};border-radius:3px"></div></div>'
                f'<div style="font-size:.82rem;font-weight:700;color:{info["color"]};min-width:32px;text-align:right">{scores[t]:.1f}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
    col_ret, col_back = st.columns(2)
    with col_ret:
        if st.button("↺  Retake Test", use_container_width=True, key="hc_retake"):
            st.session_state["_holland_step"] = 1
            st.session_state["_holland_answers"] = {}
            st.rerun()
    with col_back:
        if st.button("← Back to Explorer", use_container_width=True, key="hc_done"):
            prev = st.session_state.get("_holland_prev_page", "career_exploration")
            st.session_state["wizard_page"] = prev
            st.rerun()


def _holland_sidebar_button(page_key: str = ""):
    """Show Holland Code test button after the user has selected 6 NOC occupations."""
    if len(st.session_state.get("ce_top_nocs", [])) < 6:
        return
    st.divider()
    st.markdown(
        "<div style='font-size:.72rem;font-weight:700;color:#F59E0B;"
        "text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px'>"
        "Next Step</div>"
        "<div style='font-size:.78rem;color:#94A3B8;margin-bottom:10px'>"
        "6 occupations selected. Discover how your personality aligns with these careers.</div>",
        unsafe_allow_html=True,
    )
    if st.button("Take Holland Code Test →", type="primary", use_container_width=True,
                 key=f"holland_btn_{page_key}"):
        st.switch_page("pages/2_Holland_Code.py")


# ── Router ────────────────────────────────────────────────────────


def main(default_page: str = "career_exploration"):
    # ── Handle Holland Code incoming URL params ────────────────
    params = st.query_params
    if "holland_best" in params and "wizard_page" not in st.session_state:
        best_raw  = params.get("holland_best", "")
        worth_raw = params.get("holland_worth", "")
        best_titles_raw  = params.get("holland_best_titles", "")
        worth_titles_raw = params.get("holland_worth_titles", "")

        best_codes  = [c.strip() for c in best_raw.split(",")  if c.strip()]
        worth_codes = [c.strip() for c in worth_raw.split(",") if c.strip()]

        # Build code→title dicts from pipe-delimited title strings
        best_title_list  = best_titles_raw.split("|")  if best_titles_raw  else []
        worth_title_list = worth_titles_raw.split("|") if worth_titles_raw else []
        best_titles_dict  = {c: t for c, t in zip(best_codes,  best_title_list)}
        worth_titles_dict = {c: t for c, t in zip(worth_codes, worth_title_list)}

        st.session_state["holland_best_nocs"]    = best_codes
        st.session_state["holland_worth_nocs"]   = worth_codes
        st.session_state["holland_best_titles"]  = best_titles_dict
        st.session_state["holland_worth_titles"] = worth_titles_dict
        st.session_state["wizard_page"] = "holland_skills"

    if "wizard_page" not in st.session_state:
        st.session_state["wizard_page"] = default_page

    page = st.session_state["wizard_page"]
    if page == "holland_skills":
        render_holland_skills_page()
    elif page == "deep_analysis":
        render_deep_analysis_page()
    elif page == "cip_distribution":
        render_cip_distribution_page()
    elif page == "ce_analysis":
        render_ce_analysis_page()
    elif page == "ce_headcount":
        render_ce_headcount_page()
    elif page == "ce_job_analysis":
        render_ce_job_analysis_page()
    elif page == "ce_skills":
        render_ce_skills_page()
    elif page == "ce_wages":
        render_ce_wages_page()
    elif page == "ce_interest_analysis":
        render_ce_interest_analysis_page()
    elif page == "analysis":
        render_analysis_page()
    elif page == "career_exploration":
        render_career_exploration_page()
    else:
        render_profile_page()


if __name__ == "__main__":
    main()

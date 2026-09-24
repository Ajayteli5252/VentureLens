"""
Streamlit front-end for the Multi-Agent Startup Idea Validator.
Run with: streamlit run app.py
"""

import html
import re
import streamlit as st
from crew import run_validation

st.set_page_config(page_title="VentureLens", page_icon="🔭", layout="centered")

# Custom CSS for warm cream background, serif typography, and loading animations matching the design
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400..700;1,6..72,400&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');

    /* Global App Background & Container */
    .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #F5F1EA !important;
        color: #2C2623 !important;
        font-family: 'Plus Jakarta Sans', -apple-system, sans-serif !important;
    }

    [data-testid="stMainBlockContainer"] {
        max-width: 820px !important;
        padding-top: 2rem !important;
        padding-bottom: 3.5rem !important;
    }

    /* Keyframe Animations */
    @keyframes fadeIn {
        from {
            opacity: 0;
            transform: translateY(8px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    @keyframes pulseDot {
        0%, 80%, 100% {
            transform: scale(0.65);
            opacity: 0.35;
        }
        40% {
            transform: scale(1.15);
            opacity: 1;
        }
    }

    @keyframes pulseGlowGreen {
        0% {
            box-shadow: 0 0 0 0 rgba(30, 127, 92, 0.4);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(30, 127, 92, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(30, 127, 92, 0);
        }
    }

    @keyframes pulseGlowRed {
        0% {
            box-shadow: 0 0 0 0 rgba(179, 38, 30, 0.4);
        }
        70% {
            box-shadow: 0 0 0 10px rgba(179, 38, 30, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(179, 38, 30, 0);
        }
    }

    /* Hero Section Card matching the screenshot */
    .vl-hero-card {
        background-color: #FAF7F2;
        border: 1px solid #E4DDD2;
        border-radius: 16px;
        padding: 32px 28px;
        margin-bottom: 24px;
        box-shadow: 0 4px 20px rgba(60, 45, 30, 0.03);
        position: relative;
    }

    .vl-variant-tag {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 13px;
        color: #8E877F;
        font-weight: 400;
        margin-bottom: 20px;
    }

    .vl-brand-row {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
    }

    .vl-brand-title {
        font-family: 'Newsreader', Georgia, serif;
        font-size: 52px;
        font-weight: 600;
        color: #2C2623;
        letter-spacing: -0.5px;
        line-height: 1;
    }

    .vl-accent-line {
        width: 48px;
        height: 3px;
        background-color: #C87A54;
        border-radius: 2px;
        margin: 14px auto 16px auto;
    }

    .vl-brand-subtitle {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 17px;
        color: #726A62;
        line-height: 1.55;
        text-align: center;
        max-width: 520px;
        margin: 0 auto;
    }

    /* Animated Loader Matching Screenshot */
    .vl-loading-box {
        text-align: center;
        padding: 24px 16px;
        margin: 20px 0;
        animation: fadeIn 0.4s ease-out;
    }

    .vl-validating-label {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 13.5px;
        color: #8E877F;
        letter-spacing: 0.2px;
        margin-bottom: 14px;
    }

    .vl-dots-row {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 7px;
    }

    .vl-dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background-color: #C87A54;
        display: inline-block;
        animation: pulseDot 1.4s infinite ease-in-out both;
    }

    .vl-dot:nth-child(1) { animation-delay: -0.32s; }
    .vl-dot:nth-child(2) { animation-delay: -0.16s; }
    .vl-dot:nth-child(3) { animation-delay: 0s; }

    .vl-loading-text {
        font-family: 'Plus Jakarta Sans', sans-serif;
        font-size: 16px;
        font-weight: 500;
        color: #2C2623;
        margin-left: 10px;
        letter-spacing: 0.2px;
    }

    /* Textarea Styling */
    .stTextArea textarea {
        background-color: #FAF7F2 !important;
        border-radius: 12px !important;
        border: 1px solid #DCD6CA !important;
        color: #2C2623 !important;
        padding: 16px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 15px !important;
        transition: all 0.25s ease !important;
    }

    .stTextArea textarea:focus {
        border-color: #C87A54 !important;
        box-shadow: 0 0 0 3px rgba(200, 122, 84, 0.15) !important;
        background-color: #FFFFFF !important;
    }

    /* Primary Rounded Full-Width Button */
    div.stButton > button {
        width: 100% !important;
        border-radius: 12px !important;
        background-color: #2C2623 !important;
        color: #FAF7F2 !important;
        border: 1px solid #2C2623 !important;
        padding: 14px 24px !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-size: 15px !important;
        font-weight: 600 !important;
        letter-spacing: 0.3px !important;
        transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 4px 14px rgba(44, 38, 35, 0.12) !important;
        cursor: pointer !important;
    }

    div.stButton > button:hover:not(:disabled) {
        background-color: #C87A54 !important;
        border-color: #C87A54 !important;
        color: #FFFFFF !important;
        box-shadow: 0 6px 20px rgba(200, 122, 84, 0.25) !important;
        transform: translateY(-2px) !important;
    }

    div.stButton > button:active:not(:disabled) {
        transform: translateY(0px) !important;
    }

    div.stButton > button:disabled {
        opacity: 0.55 !important;
        cursor: not-allowed !important;
        box-shadow: none !important;
    }

    /* Streamlit Expander / Status styling */
    [data-testid="stStatusWidget"], [data-testid="stExpander"] {
        background-color: #FAF7F2 !important;
        border: 1px solid #E4DDD2 !important;
        border-radius: 12px !important;
    }

    /* Result Cards */
    .score-card {
        border-radius: 14px;
        border: 1px solid #E2DCD0;
        padding: 22px 20px;
        background-color: #FAF7F2;
        text-align: center;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        min-height: 125px;
        box-sizing: border-box;
        animation: fadeIn 0.4s ease-out;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    }

    .score-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.05);
    }

    .score-label {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8E877F;
        margin-bottom: 6px;
    }

    .score-value {
        font-family: 'Newsreader', Georgia, serif;
        font-size: 46px;
        font-weight: 700;
        line-height: 1.1;
    }

    .score-max {
        font-size: 20px;
        font-weight: 500;
        opacity: 0.6;
    }

    .badge-card {
        border-radius: 14px;
        border: 1px solid #E2DCD0;
        padding: 22px 20px;
        background-color: #FAF7F2;
        display: flex;
        flex-direction: column;
        justify-content: center;
        align-items: center;
        min-height: 125px;
        box-sizing: border-box;
        animation: fadeIn 0.4s ease-out;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    }

    .badge-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.05);
    }

    .badge-label {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8E877F;
        margin-bottom: 10px;
    }

    .rec-pill {
        display: inline-block;
        padding: 10px 32px;
        border-radius: 9999px;
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 1.5px;
        color: #ffffff;
        text-align: center;
    }

    .rec-pill-go {
        background-color: #1E7F5C;
        box-shadow: 0 4px 14px rgba(30, 127, 92, 0.35);
        animation: pulseGlowGreen 2.5s infinite;
    }

    .rec-pill-nogo {
        background-color: #B3261E;
        box-shadow: 0 4px 14px rgba(179, 38, 30, 0.35);
        animation: pulseGlowRed 2.5s infinite;
    }

    .justification-card {
        border-radius: 14px;
        border: 1px solid #E2DCD0;
        padding: 24px 28px;
        background-color: #FAF7F2;
        margin-top: 18px;
        animation: fadeIn 0.5s ease-out;
        box-sizing: border-box;
        transition: box-shadow 0.2s ease;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.02);
    }

    .justification-card:hover {
        box-shadow: 0 6px 16px rgba(0, 0, 0, 0.05);
    }

    .justification-title {
        font-size: 12px;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 1px;
        color: #8E877F;
        margin-bottom: 10px;
    }

    .justification-text {
        font-size: 15.5px;
        line-height: 1.7;
        color: #2C2623;
        margin: 0;
    }

    .vl-footer-caption {
        font-size: 13px;
        color: #8E877F;
        text-align: center;
        margin-top: 16px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Hero Header matching the exact design in the image
st.markdown(
    """
    <div class="vl-hero-card">
        <div class="vl-brand-row">
            <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#C87A54" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round" style="display:inline-block; vertical-align:middle; margin-bottom: 2px;">
                <circle cx="10.5" cy="10.5" r="6.8"></circle>
                <line x1="15.8" y1="15.8" x2="21" y2="21"></line>
            </svg>
            <span class="vl-brand-title">VentureLens</span>
        </div>
        <div class="vl-accent-line"></div>
        <div class="vl-brand-subtitle">
            Multi-agent AI that researches, debates, and scores<br>your startup idea.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

idea = st.text_area(
    "Describe your business/startup idea",
    placeholder="e.g. Portable EV battery health and degradation prediction device",
    height=120,
    label_visibility="collapsed",
)

if st.button("Validate Idea", type="primary", disabled=not idea.strip(), use_container_width=True):
    loading_placeholder = st.empty()
    # Render the animated "while validating • • • Comparing..." loading animation
    loading_placeholder.markdown(
        """
        <div class="vl-loading-box">
            <div class="vl-validating-label">while validating</div>
            <div class="vl-dots-row">
                <span class="vl-dot"></span>
                <span class="vl-dot"></span>
                <span class="vl-dot"></span>
                <span class="vl-loading-text">Comparing...</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    status_container = st.empty()
    with status_container.status(
        "Agents are researching, debating, and scoring your idea…",
        expanded=True,
    ) as status:
        st.write("🔄 Starting validation pipeline…")
        st.write("⏳ This can take 2-3 minutes (requests are paced to stay within rate limits)")
        st.write("🔁 If a model hiccups, automatic retries with backoff will kick in")
        try:
            result = run_validation(idea.strip())
            status.update(label="✅ Validation complete!", state="complete")
        except Exception as e:
            status.update(label="❌ Validation failed", state="error")
            st.error(f"Something went wrong: {e}")
            result = None

    # Clear the custom loading animation once finished
    loading_placeholder.empty()

    if result:
        st.success("Validation complete")

        # Parse verdict fields with regex
        score_match = re.search(r"Score[:\s*]+([\d.]+)\s*/\s*10", result, re.IGNORECASE)
        rec_match = re.search(r"Recommendation[:\s*]+(Go|No-?Go)\b", result, re.IGNORECASE)
        just_match = re.search(r"Justification[:\s*]+([\s\S]+)", result, re.IGNORECASE)

        parsed_successfully = False
        if score_match and rec_match and just_match:
            try:
                score = float(score_match.group(1))
                rec_raw = rec_match.group(1).strip()
                recommendation = "NO-GO" if "no" in rec_raw.lower() else "GO"
                justification = just_match.group(1).strip()
                if justification:
                    parsed_successfully = True
            except (ValueError, TypeError):
                parsed_successfully = False

        if parsed_successfully:
            # Color logic
            if score >= 7.0:
                score_color = "#1E7F5C"
            elif score >= 5.0:
                score_color = "#B8860B"
            else:
                score_color = "#B3261E"

            score_display = f"{score:g}"
            badge_class = "rec-pill-go" if recommendation == "GO" else "rec-pill-nogo"
            safe_justification = html.escape(justification).replace("\n", "<br>")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(
                    f"""
                    <div class="score-card">
                        <div class="score-label">Overall Score</div>
                        <div class="score-value" style="color: {score_color};">
                            {score_display}<span class="score-max">/10</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            with col2:
                st.markdown(
                    f"""
                    <div class="badge-card">
                        <div class="badge-label">Recommendation</div>
                        <div class="rec-pill {badge_class}">
                            {recommendation}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            st.markdown(
                f"""
                <div class="justification-card" style="border-left: 4px solid {score_color};">
                    <div class="justification-title">Investment Verdict Justification</div>
                    <div class="justification-text">{safe_justification}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(result)

st.divider()
st.caption(
    "Pipeline: Coordinator → Market / Competitor / Financial / Risk agents "
    "(parallel) → Comparator/Debate agent → Investor-Verdict agent"
)

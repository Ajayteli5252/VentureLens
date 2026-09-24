"""
Streamlit front-end for the Multi-Agent Startup Idea Validator.
Run with: streamlit run app.py
"""

import streamlit as st
from crew import run_validation

st.set_page_config(page_title="Startup Idea Validator", page_icon="🚀")

st.title("🚀 Multi-Agent Startup Idea Validator")
st.caption("7 CrewAI agents research, debate, and score your business idea.")

idea = st.text_area(
    "Describe your business/startup idea",
    placeholder="e.g. Portable EV battery health and degradation prediction device",
    height=120,
)

if st.button("Validate Idea", type="primary", disabled=not idea.strip()):
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

    if result:
        st.success("Validation complete")
        st.markdown(result)

st.divider()
st.caption(
    "Pipeline: Coordinator → Market / Competitor / Financial / Risk agents "
    "(parallel) → Comparator/Debate agent → Investor-Verdict agent"
)

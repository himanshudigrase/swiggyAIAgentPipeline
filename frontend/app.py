"""
AI Agent Evaluation Pipeline — Streamlit Dashboard

Multi-page dashboard covering:
1. 📥 Ingest Conversation
2. 📊 Evaluation Results
3. 💡 Improvement Suggestions
4. 🏷️ Annotator Feedback
5. 🔬 Meta-Evaluation
"""

import os
import json
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────
API_BASE = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(
    page_title="AI Agent Eval Pipeline",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #1e1e2e, #2d2d45);
        border: 1px solid #3d3d5c;
        border-radius: 12px;
        padding: 16px;
        text-align: center;
        margin: 4px;
    }
    .score-high { color: #4ade80; font-size: 2rem; font-weight: bold; }
    .score-med  { color: #fbbf24; font-size: 2rem; font-weight: bold; }
    .score-low  { color: #f87171; font-size: 2rem; font-weight: bold; }
    .issue-error   { background: #3b1111; border-left: 4px solid #f87171; padding: 8px; border-radius: 4px; margin: 4px 0; }
    .issue-warning { background: #2d2200; border-left: 4px solid #fbbf24; padding: 8px; border-radius: 4px; margin: 4px 0; }
    .suggestion-card {
        background: #1e2d1e;
        border: 1px solid #4ade80;
        border-radius: 8px;
        padding: 14px;
        margin: 8px 0;
    }
    .badge-high   { background:#7f1d1d; color:#fca5a5; padding:2px 8px; border-radius:9999px; font-size:0.75rem; }
    .badge-medium { background:#78350f; color:#fcd34d; padding:2px 8px; border-radius:9999px; font-size:0.75rem; }
    .badge-low    { background:#1e3a1e; color:#86efac; padding:2px 8px; border-radius:9999px; font-size:0.75rem; }
    .stButton button { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def api(method: str, path: str, **kwargs):
    try:
        resp = getattr(requests, method)(f"{API_BASE}{path}", timeout=15, **kwargs)
        return resp.json(), resp.status_code
    except Exception as e:
        return {"error": str(e)}, 500


def score_color(score):
    if score is None:
        return "⚪"
    if score >= 0.8:
        return "🟢"
    if score >= 0.6:
        return "🟡"
    return "🔴"


def fmt_score(score):
    if score is None:
        return "N/A"
    return f"{score:.2f}"


# ── Sidebar Navigation ─────────────────────────────────────────────────────────
st.sidebar.title("🤖 Eval Pipeline")
st.sidebar.markdown("---")
page = st.sidebar.radio(
    "Navigate",
    ["📥 Ingest Conversation", "📊 Evaluation Results", "💡 Improvement Suggestions",
     "🏷️ Annotator Feedback", "🔬 Meta-Evaluation"],
)

# Check API health
health, code = api("get", "/health")
if code == 200:
    st.sidebar.success("✅ API Connected")
else:
    st.sidebar.error("❌ API Unreachable")

st.sidebar.markdown("---")
st.sidebar.markdown(f"**API**: `{API_BASE}`")
st.sidebar.markdown("[📖 Swagger Docs](%s/docs)" % API_BASE)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 1: Ingest Conversation
# ══════════════════════════════════════════════════════════════════════════════
if page == "📥 Ingest Conversation":
    st.title("📥 Ingest Conversation")
    st.markdown("Submit a conversation for automated evaluation. The evaluation runs asynchronously in the background.")

    # Sample payload
    SAMPLE = {
        "conversation_id": f"conv_{datetime.now().strftime('%H%M%S')}",
        "agent_version": "v2.3.1",
        "turns": [
            {"turn_id": 1, "role": "user", "content": "I need to book a flight to NYC next week", "timestamp": "2024-01-15T10:30:00Z"},
            {"turn_id": 2, "role": "assistant", "content": "I'd be happy to help you book a flight to NYC...",
             "tool_calls": [{"tool_name": "flight_search", "parameters": {"destination": "NYC", "date_range": "2024-01-22/2024-01-28"}, "result": {"status": "success", "flights": ["AA123", "UA456"]}, "latency_ms": 450}],
             "timestamp": "2024-01-15T10:30:02Z"}
        ],
        "feedback": {
            "user_rating": 4,
            "ops_review": {"quality": "good", "notes": "Correct tool usage"},
            "annotations": [{"type": "tool_accuracy", "label": "correct", "annotator_id": "ann_001"}]
        },
        "metadata": {"total_latency_ms": 1200, "mission_completed": True}
    }

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("JSON Input")
        if st.button("📋 Load Sample Conversation"):
            st.session_state["conv_json"] = json.dumps(SAMPLE, indent=2)

        default_json = st.session_state.get("conv_json", json.dumps(SAMPLE, indent=2))
        conv_json = st.text_area("Paste conversation JSON:", value=default_json, height=400, key="input_json")

    with col2:
        st.subheader("Submit")
        st.info("💡 Click **Load Sample** to pre-fill the form with an example based on the assignment schema.")

        if st.button("🚀 Ingest & Evaluate", type="primary", use_container_width=True):
            try:
                payload = json.loads(conv_json)
                result, code = api("post", "/ingest", json=payload)
                if code in (200, 202):
                    st.success(f"✅ **{result.get('status', 'queued').upper()}** — `{result.get('conversation_id')}`")
                    st.info(result.get("message", ""))
                    st.json(result)
                else:
                    st.error(f"❌ Error {code}: {result}")
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")

        st.markdown("**Or batch-ingest multiple conversations:**")
        batch_json = st.text_area("Batch JSON (must be `{\"conversations\": [...]}`):", height=100, placeholder='{"conversations": [{...}, {...}]}')
        if st.button("📦 Batch Ingest", use_container_width=True):
            try:
                payload = json.loads(batch_json)
                result, code = api("post", "/ingest/batch", json=payload)
                if code in (200, 202):
                    st.success(f"✅ Queued: {result.get('queued')}, Duplicates: {result.get('duplicates')}")
                else:
                    st.error(f"❌ Error {code}: {result}")
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 2: Evaluation Results
# ══════════════════════════════════════════════════════════════════════════════
elif page == "📊 Evaluation Results":
    st.title("📊 Evaluation Results")

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        version_filter = st.text_input("Filter by agent version (optional):", placeholder="e.g. v2.3.1")
    with col2:
        page_num = st.number_input("Page", min_value=1, value=1)
    with col3:
        st.write("")
        st.write("")
        refresh = st.button("🔄 Refresh", use_container_width=True)

    params = {"page": page_num, "page_size": 20}
    if version_filter:
        params["agent_version"] = version_filter

    data, code = api("get", "/evaluations", params=params)

    if code != 200:
        st.error(f"API error: {data}")
    else:
        items = data.get("items", [])
        total = data.get("total", 0)

        st.markdown(f"**{total} evaluations found** (showing page {page_num})")

        if not items:
            st.info("No evaluations yet. Ingest a conversation first!")
        else:
            # Summary metrics
            scores = [i["scores"] for i in items]
            avg_overall = sum(s.get("overall") or 0 for s in scores) / len(scores)
            avg_quality = sum(s.get("response_quality") or 0 for s in scores) / len(scores)
            avg_tool = sum(s.get("tool_accuracy") or 0 for s in scores) / len(scores)
            avg_coh = sum(s.get("coherence") or 0 for s in scores) / len(scores)

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Avg Overall", fmt_score(avg_overall), delta=None)
            m2.metric("Avg Response Quality", fmt_score(avg_quality))
            m3.metric("Avg Tool Accuracy", fmt_score(avg_tool))
            m4.metric("Avg Coherence", fmt_score(avg_coh))

            # Chart
            df = pd.DataFrame([{
                "ID": i["conversation_id"][:15] + "...",
                "Overall": i["scores"].get("overall"),
                "Quality": i["scores"].get("response_quality"),
                "Tool": i["scores"].get("tool_accuracy"),
                "Coherence": i["scores"].get("coherence"),
            } for i in items])
            fig = px.bar(df.melt(id_vars="ID"), x="ID", y="value", color="variable",
                        barmode="group", title="Scores per Conversation",
                        color_discrete_sequence=px.colors.qualitative.Pastel)
            fig.update_layout(yaxis_range=[0, 1], template="plotly_dark", height=300)
            st.plotly_chart(fig, use_container_width=True)

            # Detail rows
            for item in items:
                cid = item["conversation_id"]
                scores = item["scores"]
                issues = item.get("issues_detected") or []
                with st.expander(f"{score_color(scores.get('overall'))} `{cid}` — overall: {fmt_score(scores.get('overall'))} | agent: {item.get('agent_version', 'N/A')}"):
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Quality", fmt_score(scores.get("response_quality")))
                    c2.metric("Tool Accuracy", fmt_score(scores.get("tool_accuracy")))
                    c3.metric("Coherence", fmt_score(scores.get("coherence")))
                    c4.metric("Issues", len(issues))

                    if item.get("tool_evaluation"):
                        st.markdown("**Tool Evaluation:**")
                        st.json(item["tool_evaluation"])

                    if issues:
                        st.markdown("**Issues Detected:**")
                        for issue in issues:
                            sev = issue.get("severity", "info")
                            css = "issue-error" if sev == "error" else "issue-warning"
                            st.markdown(f'<div class="{css}">⚠️ [{sev.upper()}] {issue.get("description")}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 3: Improvement Suggestions
# ══════════════════════════════════════════════════════════════════════════════
elif page == "💡 Improvement Suggestions":
    st.title("💡 Improvement Suggestions")
    st.markdown("Auto-generated suggestions from the **Self-Update Engine**, based on detected failure patterns.")

    col1, col2 = st.columns([3, 1])
    with col1:
        type_filter = st.selectbox("Filter by type:", ["All", "prompt", "tool"])
    with col2:
        st.write("")
        st.write("")
        if st.button("⚡ Generate Now", type="primary", use_container_width=True):
            with st.spinner("Scanning evaluations and generating suggestions..."):
                result, code = api("post", "/suggestions/generate", json={"window": 100})
                if code == 200:
                    st.success(f"Generated {result.get('total', 0)} suggestion(s)")
                else:
                    st.error(f"Error: {result}")

    params = {}
    if type_filter != "All":
        params["suggestion_type"] = type_filter

    data, code = api("get", "/suggestions", params=params)

    if code != 200:
        st.error(f"API error: {data}")
    elif not data.get("items"):
        st.info("No suggestions yet. Click **Generate Now** to scan recent evaluations.")
    else:
        st.markdown(f"**{data.get('total', 0)} suggestions found**")
        for s in data["items"]:
            conf = s.get("confidence", 0)
            conf_color = "🟢" if conf >= 0.7 else ("🟡" if conf >= 0.5 else "🔴")
            type_icon = "📝" if s.get("suggestion_type") == "prompt" else "🔧"
            with st.expander(f"{type_icon} [{s.get('suggestion_type', '?').upper()}] {s.get('target', 'General')} — Confidence: {conf_color} {conf:.0%}"):
                st.markdown(f"**Suggestion:**\n\n> {s.get('suggestion_text')}")
                st.markdown(f"**Rationale:** {s.get('rationale', 'N/A')}")
                st.markdown(f"**Expected Impact:** {s.get('expected_impact', 'N/A')}")
                if s.get("failure_pattern"):
                    st.markdown(f"**Based on failure patterns:** `{s['failure_pattern']}`")
                st.caption(f"Status: {s.get('status')} | Created: {s.get('created_at', '')}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 4: Annotator Feedback
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🏷️ Annotator Feedback":
    st.title("🏷️ Annotator Feedback")
    st.markdown("Submit human annotations for conversations. Multiple annotators can label the same conversation — the system computes agreement metrics automatically.")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Submit Annotation")
        conv_id = st.text_input("Conversation ID:", placeholder="conv_abc123")
        annotator_id = st.text_input("Annotator ID:", placeholder="ann_001")
        ann_type = st.selectbox("Annotation Type:", ["tool_accuracy", "helpfulness", "factuality", "coherence"])
        label = st.selectbox("Label:", ["correct", "incorrect", "helpful", "not_helpful", "good", "poor"])
        confidence = st.slider("Confidence:", 0.0, 1.0, 0.9, 0.05)
        notes = st.text_area("Notes (optional):")

        if st.button("✅ Submit Annotation", type="primary", use_container_width=True):
            payload = {
                "conversation_id": conv_id,
                "annotator_id": annotator_id,
                "annotation_type": ann_type,
                "label": label,
                "confidence": confidence,
                "notes": notes or None,
            }
            result, code = api("post", "/feedback/annotate", json=payload)
            if code == 200:
                routing = result.get("routing_decision", "unknown")
                icon = "✅" if routing == "auto_labeled" else ("⚠️" if routing == "human_review" else "🔀")
                st.success(f"{icon} Annotation saved! Routing: **{routing}**")
                st.json(result)
            else:
                st.error(f"Error {code}: {result}")

    with col2:
        st.subheader("Agreement Report")
        check_conv = st.text_input("Check conversation:", placeholder="conv_abc123", key="agree_conv")
        check_type = st.selectbox("Annotation type:", ["tool_accuracy", "helpfulness", "factuality"], key="agree_type")
        if st.button("📊 Get Agreement Report", use_container_width=True):
            result, code = api("get", f"/feedback/{check_conv}", params={"annotation_type": check_type})
            if code == 200:
                kappa = result.get("cohen_kappa")
                pct = result.get("agreement_pct", 0)
                routing = result.get("routing_decision", "?")

                col_a, col_b = st.columns(2)
                col_a.metric("Agreement %", f"{pct*100:.1f}%")
                col_b.metric("Cohen's Kappa", f"{kappa:.2f}" if kappa is not None else "N/A")

                routing_icon = {"auto_labeled": "✅", "human_review": "⚠️", "tiebreaker": "🔀"}.get(routing, "❓")
                st.info(f"{routing_icon} **Routing decision:** {routing}")
                st.markdown(f"**Labels:** {result.get('labels', [])}")
                st.caption(f"Annotators: {result.get('num_annotators', 0)}")
            elif code == 404:
                st.warning("No annotations found for this conversation.")
            else:
                st.error(f"Error: {result}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE 5: Meta-Evaluation
# ══════════════════════════════════════════════════════════════════════════════
elif page == "🔬 Meta-Evaluation":
    st.title("🔬 Meta-Evaluation")
    st.markdown("""
    **How well do the automated evaluators agree with human annotations?**

    This is the *flywheel*: better evaluators → better evaluations → better agents.
    Low agreement means an evaluator needs recalibration.
    """)

    if st.button("🔄 Refresh Calibration Data"):
        st.cache_data.clear()

    tab1, tab2 = st.tabs(["📏 Evaluator Calibration", "🗺️ Failure Coverage"])

    with tab1:
        data, code = api("get", "/meta/calibration")
        if code != 200:
            st.error(f"API error: {data}")
        else:
            total = data.get("total_calibration_points", 0)
            st.metric("Total Calibration Points", total)

            if not data.get("metrics"):
                st.info("No calibration data yet. Submit annotations for conversations that have been evaluated.")
            else:
                df = pd.DataFrame(data["metrics"])
                fig = px.bar(df, x="evaluator_name", y="agreement_pct", color="metric",
                            title="LLM Evaluator Agreement with Human Annotations",
                            labels={"agreement_pct": "Agreement %"},
                            color_discrete_sequence=px.colors.qualitative.Set2)
                fig.update_layout(yaxis_range=[0, 1], template="plotly_dark")
                st.plotly_chart(fig, use_container_width=True)
                st.dataframe(df, use_container_width=True)

    with tab2:
        data, code = api("get", "/meta/coverage")
        if code != 200:
            st.error(f"API error: {data}")
        else:
            scanned = data.get("scanned_evaluations", 0)
            categories = data.get("issue_categories", {})

            st.metric("Conversations Scanned", scanned)

            if not categories:
                st.info("No failure categories detected in recent evaluations. Ingest more conversations to see patterns.")
            else:
                fig = px.pie(
                    names=list(categories.keys()),
                    values=list(categories.values()),
                    title="Failure Category Distribution (last 100 evals)",
                    hole=0.4,
                )
                fig.update_layout(template="plotly_dark")
                col_a, col_b = st.columns([2, 1])
                with col_a:
                    st.plotly_chart(fig, use_container_width=True)
                with col_b:
                    st.markdown("**Category Counts:**")
                    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                        st.markdown(f"- `{cat}`: **{count}**")
